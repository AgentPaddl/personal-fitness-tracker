"""Single admission authority. Control records contain no request or result data."""

from __future__ import annotations

import asyncio
import base64
from contextvars import ContextVar
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from decimal import Decimal, ROUND_CEILING, ROUND_FLOOR
import hashlib
import hmac
import io
import json
import os
import time
from typing import Annotated, Protocol
from uuid import UUID

from PIL import Image
from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.errors import GatewayError
from app.providers.base import GenerationMetadata, StructuredGenerationRequest
from app.providers.pricing import PriceTable, resolve_profiles


class PilotError(GatewayError):
    def __init__(self, code="pilot_unavailable"):
        self.code = code
        self.http_status, message = {
            "pilot_unavailable": (503, "Analysis admission is unavailable. No automatic retry is permitted."),
            "pilot_forbidden": (403, "This identity is not authorized for the pilot."),
            "operation_required": (400, "A current UUIDv7 X-Operation-Id is required for pilot analysis."),
            "operation_conflict": (409, "This operation ID was already used with different content."),
            "operation_consumed": (409, "This operation was already accepted. Its result cannot be retrieved or automatically repeated."),
            "pilot_limit": (429, "The configured pilot usage limit has been reached."),
            "pilot_input": (413, "This input exceeds the configured pilot analysis limits."),
        }[code]
        super().__init__(message)


def enabled() -> bool:
    value = os.environ.get("AI_PILOT_ENABLED", "false")
    if value not in {"true", "false"}:
        raise PilotError()
    return value == "true"


def canonical(value) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True, allow_nan=False).encode()


def digest(secret: bytes, purpose: str, value) -> str:
    return hmac.new(secret, purpose.encode() + b"\0" + canonical(value), hashlib.sha256).hexdigest()


Positive = Annotated[int, Field(strict=True, gt=0)]
Money = Annotated[Decimal, Field(gt=0, allow_inf_nan=False)]


class Limits(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    minute: Positive
    day: Positive
    month: Positive
    concurrent: Annotated[int, Field(strict=True, ge=1, le=20)]
    daily_usd: Money
    monthly_usd: Money


class BenchmarkRun(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    run_id: str = Field(pattern=r"^[A-Za-z0-9_-]{1,60}$")
    manifest_sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    max_attempts: Annotated[int, Field(strict=True, ge=1, le=18)]
    max_reserved_usd: Annotated[Decimal, Field(gt=0, le=Decimal("4.2174"), allow_inf_nan=False)]
    expires_at: Positive


class AcceptanceRun(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    max_attempts: Annotated[int, Field(strict=True, ge=1, le=16)]
    max_reserved_usd: Annotated[Decimal, Field(gt=0, le=Decimal("3.7488"), allow_inf_nan=False)]
    payload_sha256: list[Annotated[str, Field(pattern=r"^[a-f0-9]{64}$")]] = Field(min_length=1, max_length=10)
    expires_at: Positive


class OwnerUsage(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    daily_attempts: Annotated[int, Field(strict=True, ge=1, le=3)]
    max_attempts: Annotated[int, Field(strict=True, ge=1, le=12)]
    max_reserved_usd: Annotated[Decimal, Field(gt=0, le=Decimal("2.8116"), allow_inf_nan=False)]
    max_period_usd: Annotated[Decimal, Field(gt=0, le=Decimal("3.76500465"), allow_inf_nan=False)]
    expires_at: Positive


class PilotPolicy(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    version: str = Field(pattern=r"^[A-Za-z0-9_-]{1,60}$")
    person: Limits
    total: Limits
    operation_max_age_seconds: Annotated[int, Field(strict=True, ge=60, le=86400)]
    retention_seconds: Annotated[int, Field(strict=True, ge=2678400, le=2678400)]
    max_text_schema_bytes: Annotated[int, Field(strict=True, ge=1, le=65536)]
    max_image_bytes: Annotated[int, Field(strict=True, ge=1, le=3145728)]
    max_image_dimension: Annotated[int, Field(strict=True, ge=1, le=4096)]
    max_output_tokens: Annotated[int, Field(strict=True, ge=1, le=32768)]
    deployment_verified_until: Positive
    benchmark: BenchmarkRun | None = None
    acceptance: AcceptanceRun | None = Field(default=None, exclude_if=lambda value: value is None)
    owner_usage: OwnerUsage | None = Field(default=None, exclude_if=lambda value: value is None)

    @model_validator(mode="after")
    def retention_covers_admission(self):
        if self.retention_seconds <= self.operation_max_age_seconds + 300:
            raise ValueError("Retention must exceed the operation acceptance window.")
        if self.acceptance and (self.benchmark or self.acceptance.expires_at > self.deployment_verified_until):
            raise ValueError("Acceptance must be separate from benchmarks and within the pilot period.")
        if self.owner_usage and (not self.acceptance or self.acceptance.max_attempts != 16
                or self.acceptance.max_reserved_usd != Decimal("3.7488")
                or self.owner_usage.expires_at > self.acceptance.expires_at):
            raise ValueError("Owner usage requires the closed 16-attempt acceptance within its original period.")
        return self


def units(value: Decimal, rounding=ROUND_CEILING) -> int:
    return int((value * 1_000_000_000).to_integral_value(rounding=rounding))


def operation_id(value: str | None, now: float, max_age: int) -> str:
    try:
        parsed = UUID(value)
        created = (parsed.int >> 80) / 1000
        if parsed.version != 7 or not now - max_age <= created <= now + 30:
            raise ValueError()
        return str(parsed)
    except (ValueError, TypeError, AttributeError):
        raise PilotError("operation_required") from None


class Conflict(Exception):
    pass


class ControlStore(Protocol):
    async def read(self, key: str) -> tuple[dict | None, str | None]: ...
    async def commit(self, changes: list[tuple[str, dict, str | None]]) -> None: ...


@dataclass
class DispatchPermit:
    request_digest: str
    expires: float
    used: bool = False
    admission: dict | None = None


_permit: ContextVar[DispatchPermit | None] = ContextVar("pilot_dispatch", default=None)


def consume_permit(request: StructuredGenerationRequest, *, deployment=None, profile_id=None,
                   max_output_tokens=None, price_version=None):
    permit = _permit.get()
    if permit is None or permit.used or time.time() > permit.expires:
        raise PilotError()
    if hashlib.sha256(canonical(asdict(request))).hexdigest() != permit.request_digest:
        raise PilotError()
    if permit.admission and any(permit.admission[field] != value for field, value in (
        ("deployment", deployment), ("profile_id", profile_id),
        ("max_output_tokens", max_output_tokens), ("price_version", price_version),
    )):
        raise PilotError()
    permit.used = True


class Coordinator:
    def __init__(self, store: ControlStore, policy: PilotPolicy, secret: bytes,
                 allowlist: set[tuple[str, str]], prices: PriceTable, routes: dict[str, str],
                 clock=time.time, *, profile_bindings: dict[str, str] | None = None,
                 max_output_tokens: int | None = None):
        if len(secret) < 32 or not 1 <= len(allowlist) <= 2 or not routes:
            raise PilotError()
        self.store, self.policy, self.secret = store, policy, secret
        self.allowlist, self.prices, self.routes, self.clock = allowlist, prices, routes, clock
        self.profile_bindings = dict(profile_bindings or {})
        self.max_output_tokens = policy.max_output_tokens if max_output_tokens is None else max_output_tokens
        if type(self.max_output_tokens) is not int or not 1 <= self.max_output_tokens <= policy.max_output_tokens:
            raise PilotError()
        try:
            self.profiles = resolve_profiles(self.profile_bindings, routes, prices, self.max_output_tokens)
        except ValueError:
            raise PilotError() from None
        self.policy_id = digest(secret, "policy", [policy.model_dump(mode="json"), sorted(allowlist),
                                                 prices.model_dump(mode="json"), routes,
                                                 {key: {**asdict(profile), "price": profile.price.model_dump(mode="json")}
                                                  for key, profile in self.profiles.items()}, self.max_output_tokens])

    def initial_ledger(self):
        if self.policy.owner_usage:
            raise PilotError()
        benchmark = self.policy.benchmark
        ledger = {"policy": self.policy_id, "buckets": {}, "active": {}, "blocked": False, "last_time": 0,
            "benchmark": {"run_id": benchmark.run_id, "attempts": 0, "reserved": 0} if benchmark else None}
        if self.policy.acceptance:
            ledger["acceptance"] = {"attempts": 0, "reserved": 0}
        return ledger

    async def transition_to_owner_usage(self, revised_policy, operation_keys, *, ledger_sha256,
                                        expected_etag, operations_sha256, revised_policy_sha256):
        if os.environ.get("AI_API_ONLY_ENABLED") != "false":
            raise PilotError()
        revised_policy = PilotPolicy.model_validate(revised_policy.model_dump(mode="json"))
        previous = self.policy.model_dump(mode="json")
        owner = revised_policy.owner_usage
        if (self.policy.owner_usage or not self.policy.acceptance or not owner
                or len(self.allowlist) != 1 or self.policy.acceptance.max_attempts != 16
                or self.policy.acceptance.max_reserved_usd != Decimal("3.7488")
                or not self.clock() < owner.expires_at <= self.policy.acceptance.expires_at
                or any(previous[scope][field] != value for scope in ("person", "total")
                      for field, value in (("day", 16), ("month", 16),
                                  ("concurrent", 1 if scope == "person" else 2),
                                            ("daily_usd", "2.343"), ("monthly_usd", "2.343")))):
            raise PilotError()
        expected = self.policy.model_dump(mode="json")
        expected["owner_usage"] = owner.model_dump(mode="json")
        for scope in ("person", "total"):
            expected[scope].update(minute=1, concurrent=1, day=16 + owner.daily_attempts, month=16 + owner.max_attempts)
        if (revised_policy.model_dump(mode="json") != expected
                or hashlib.sha256(canonical(expected)).hexdigest() != revised_policy_sha256):
            raise PilotError()
        ledger, etag = await self._read_ledger()
        if (etag != expected_etag or not etag or ledger["active"] or ledger.get("owner_usage") is not None
                or self.clock() < ledger["last_time"]
                or hashlib.sha256(canonical(ledger)).hexdigest() != ledger_sha256
                or ledger["acceptance"] != {"attempts": 16, "reserved": 3748800000}
                or len(operation_keys) != 16 or len(set(operation_keys)) != 16):
            raise PilotError()
        records = {}
        for key in operation_keys:
            if (not isinstance(key, str) or not key.startswith("op-") or len(key) != 67
                    or any(character not in "0123456789abcdef" for character in key[3:])):
                raise PilotError()
            record, record_etag = await self.store.read(key)
            if (not record or not record_etag or record.get("settled") is not True
                    or record.get("state") not in {"succeeded", "failed", "unknown"}
                    or type(record.get("usage_known")) is not bool
                    or type(record.get("charged")) is not int
                    or not 0 <= record["charged"] <= 234300000
                    or record.get("reserved") != 234300000 or record.get("phase") is not None
                    or not record["usage_known"] and record["charged"] != record["reserved"]):
                raise PilotError()
            records[key] = record
        cost = sum(record["charged"] for record in records.values())
        if (hashlib.sha256(canonical(records)).hexdigest() != operations_sha256
                or sum(not record["usage_known"] for record in records.values()) != 4
                or cost != 953404650 or cost > units(owner.max_period_usd, ROUND_FLOOR)):
            raise PilotError()
        revised = Coordinator(self.store, revised_policy, self.secret, self.allowlist, self.prices,
                              self.routes, self.clock, profile_bindings=self.profile_bindings,
                              max_output_tokens=self.max_output_tokens)
        audit = {"previous_policy": self.policy_id, "revised_policy": revised.policy_id,
                 "previous_ledger_sha256": ledger_sha256, "operations_sha256": operations_sha256,
                 "revised_policy_sha256": revised_policy_sha256, "created": self.clock(),
                 "acceptance": dict(ledger["acceptance"]), "baseline_cost": cost, "holds": 4}
        ledger["policy"] = revised.policy_id
        ledger["owner_usage"] = {"attempts": 0, "reserved": 0, "period_cost": cost,
                                 "day": "", "day_attempts": 0, "day_reserved": 0}
        await self.store.commit([("ledger", ledger, etag), ("owner-transition-v1", audit, None)])
        return audit

    def bound(self, request: StructuredGenerationRequest) -> int:
        policy = self.policy
        deployment = self.routes.get(request.model_purpose)
        price = self.prices.deployments.get(deployment)
        try:
            profiles = resolve_profiles(self.profile_bindings, self.routes, self.prices, self.max_output_tokens)
        except ValueError:
            raise PilotError() from None
        profile = profiles.get(deployment)
        if (self.clock() >= policy.deployment_verified_until or price is None
            or policy.benchmark is not None and self.clock() >= policy.benchmark.expires_at
                or not profile and price.model != "gpt-4.1-mini-2025-04-14"
                or type(request.max_output_tokens) is not int
                or not 1 <= request.max_output_tokens <= self.max_output_tokens
                or not 0 < request.timeout_seconds <= 99):
            raise PilotError()
        content = [asdict(message) for message in request.messages]
        if len(canonical([content, request.output_json_schema])) > policy.max_text_schema_bytes:
            raise PilotError("pilot_input")
        if len(request.attachments) > 1:
            raise PilotError("pilot_input")
        try:
            for attachment in request.attachments:
                if (attachment.kind != "image" or attachment.media_type not in {"image/jpeg", "image/png"}
                        or len(attachment.data) > 4 * ((policy.max_image_bytes + 2) // 3)):
                    raise ValueError()
                decoded = base64.b64decode(attachment.data, validate=True)
                if not decoded or len(decoded) > policy.max_image_bytes:
                    raise ValueError()
                with Image.open(io.BytesIO(decoded)) as image:
                    if max(image.size) > policy.max_image_dimension:
                        raise ValueError()
        except Exception:
            raise PilotError("pilot_input") from None
        if profile:
            return units(profile.reserve_usd(request.max_output_tokens))
        return units((Decimal(1_047_576) * max(price.input_per_million, price.cached_input_per_million)
                      + request.max_output_tokens * price.output_per_million) / 1_000_000)

    def admission(self, request: StructuredGenerationRequest) -> dict:
        deployment = self.routes[request.model_purpose]
        profile = self.profiles.get(deployment)
        return {"deployment": deployment, "model": self.prices.deployments[deployment].model,
                "profile_id": profile.identifier if profile else None,
                "service_tier": profile.service_tier if profile else None,
                "price_version": self.prices.version,
                "max_input_tokens": profile.max_input_tokens if profile else 1_047_576,
                "max_output_tokens": request.max_output_tokens}

    def _keys(self, person: str, now: float):
        instant = datetime.fromtimestamp(now, timezone.utc)
        periods = {"minute": instant.strftime("%Y%m%d%H%M"), "day": instant.strftime("%Y%m%d"),
                   "month": instant.strftime("%Y%m")}
        return [(f"{scope}:{period}:{stamp}", getattr(limits, period),
                 units(limits.daily_usd if period == "day" else limits.monthly_usd, ROUND_FLOOR) if period != "minute" else None)
                for scope, limits in ((person, self.policy.person), ("total", self.policy.total))
                for period, stamp in periods.items()]

    async def _read_ledger(self):
        ledger, etag = await self.store.read("ledger")
        if ledger is None or ledger["policy"] != self.policy_id or ledger["blocked"]:
            raise PilotError()
        if self.policy.benchmark:
            run = ledger.get("benchmark")
            if (not isinstance(run, dict) or run.get("run_id") != self.policy.benchmark.run_id
                    or any(type(run.get(field)) is not int or run[field] < 0 for field in ("attempts", "reserved"))):
                raise PilotError()
        if self.policy.acceptance:
            run = ledger.get("acceptance")
            if (not isinstance(run, dict)
                    or any(type(run.get(field)) is not int or run[field] < 0 for field in ("attempts", "reserved"))):
                raise PilotError()
        if self.policy.owner_usage:
            run = ledger.get("owner_usage")
            audit, _ = await self.store.read("owner-transition-v1")
            if (len(self.allowlist) != 1 or not isinstance(run, dict) or not audit
                    or audit.get("revised_policy") != self.policy_id
                    or ledger.get("acceptance") != {"attempts": 16, "reserved": 3748800000}
                    or audit.get("acceptance") != ledger["acceptance"]
                    or audit.get("baseline_cost") != 953404650 or audit.get("holds") != 4
                    or any(type(run.get(field)) is not int or run[field] < 0 for field in
                           ("attempts", "reserved", "period_cost", "day_attempts", "day_reserved"))
                    or run["period_cost"] < audit["baseline_cost"] or not isinstance(run.get("day"), str)):
                raise PilotError()
        return ledger, etag

    async def reserve(self, identity, operation, fingerprint, amount, admission=None):
        now = self.clock()
        if self.profiles and admission is None:
            raise PilotError()
        if identity not in self.allowlist:
            raise PilotError("pilot_forbidden")
        operation = operation_id(operation, now, self.policy.operation_max_age_seconds)
        person = digest(self.secret, "person", identity)
        key = "op-" + digest(self.secret, "operation", [identity, operation])
        for attempt in range(3):
            ledger, etag = await self._read_ledger()
            existing, _ = await self.store.read(key)
            if existing:
                raise PilotError("operation_conflict" if existing["fingerprint"] != fingerprint else "operation_consumed")
            if now < ledger["last_time"]:
                raise PilotError()
            ledger["last_time"] = max(now, ledger["last_time"])
            acceptance = self.policy.acceptance
            owner = self.policy.owner_usage
            if owner:
                run = ledger["owner_usage"]
                day = datetime.fromtimestamp(now, timezone.utc).strftime("%Y%m%d")
                if run["day"] != day:
                    run.update(day=day, day_attempts=0, day_reserved=0)
                if (now >= owner.expires_at or type(amount) is not int or not 0 < amount <= 234300000
                        or run["attempts"] >= owner.max_attempts or run["day_attempts"] >= owner.daily_attempts
                        or run["reserved"] + amount > units(owner.max_reserved_usd, ROUND_FLOOR)
                        or run["day_reserved"] + amount > owner.daily_attempts * 234300000
                        or run["period_cost"] + amount > units(owner.max_period_usd, ROUND_FLOOR)):
                    raise PilotError("pilot_limit")
                run["attempts"] += 1
                run["reserved"] += amount
                run["day_attempts"] += 1
                run["day_reserved"] += amount
                run["period_cost"] += amount
            elif acceptance:
                run = ledger["acceptance"]
                if (now >= acceptance.expires_at or run["attempts"] >= acceptance.max_attempts
                        or run["reserved"] + amount > units(acceptance.max_reserved_usd, ROUND_FLOOR)):
                    raise PilotError("pilot_limit")
                run["attempts"] += 1
                run["reserved"] += amount
            benchmark = self.policy.benchmark
            if benchmark:
                run = ledger["benchmark"]
                if (now >= benchmark.expires_at or run["attempts"] >= benchmark.max_attempts
                        or run["reserved"] + amount > units(benchmark.max_reserved_usd, ROUND_FLOOR)):
                    raise PilotError("pilot_limit")
                run["attempts"] += 1
                run["reserved"] += amount
            active = ledger["active"]
            if (len(active) >= self.policy.total.concurrent
                    or sum(entry == person for entry in active.values()) >= self.policy.person.concurrent):
                raise PilotError("pilot_limit")
            keys = self._keys(person, now)
            current = {entry[0] for allowed in self.allowlist
                       for entry in self._keys(digest(self.secret, "person", allowed), now)}
            ledger["buckets"] = {key: value for key, value in ledger["buckets"].items() if key in current}
            for bucket_key, count_limit, cost_limit in keys:
                bucket = ledger["buckets"].setdefault(bucket_key, {"count": 0, "cost": 0, "created": now})
                if bucket["count"] + 1 > count_limit or (cost_limit is not None and bucket["cost"] + amount > cost_limit):
                    raise PilotError("pilot_limit")
                bucket["count"] += 1
                bucket["cost"] += amount
            active[key] = person
            record = {"fingerprint": fingerprint, "state": "pending", "reserved": amount,
                      "created": now, "expires": now + self.policy.retention_seconds,
                      "dispatch_before": now + 30, "buckets": [entry[0] for entry in keys],
                      "admission": admission}
            if owner:
                record["phase"] = "owner-v1"
            try:
                await self.store.commit([("ledger", ledger, etag), (key, record, None)])
                return key
            except Conflict:
                continue
        raise PilotError()

    async def mark_dispatched(self, key):
        record, etag = await self.store.read(key)
        if (not record or record["state"] != "pending" or self.clock() > record["dispatch_before"]
            or self.policy.benchmark is not None and self.clock() >= self.policy.benchmark.expires_at
            or self.policy.owner_usage is not None and self.clock() >= self.policy.owner_usage.expires_at
            or self.policy.acceptance is not None and self.clock() >= self.policy.acceptance.expires_at):
            raise PilotError()
        record["state"] = "unknown"
        await self.store.commit([(key, record, etag)])

    async def settle(self, key, state, metadata: GenerationMetadata | None):
        for attempt in range(3):
            ledger, ledger_etag = await self._read_ledger()
            record, etag = await self.store.read(key)
            if not record or record["state"] != "unknown" or record.get("settled"):
                raise PilotError()
            actual = None
            usage = metadata.usage if metadata else None
            admission = record.get("admission")
            expected_model = admission["model"] if admission else "gpt-4.1-mini-2025-04-14"
            input_bound = admission["max_input_tokens"] if admission else 1_047_576
            output_bound = admission["max_output_tokens"] if admission else self.policy.max_output_tokens
            identity_matches = metadata is not None and metadata.returned_model == expected_model
            if metadata and metadata.returned_model is not None and not identity_matches:
                ledger["blocked"] = True
            if metadata and admission and metadata.requested_deployment != admission["deployment"]:
                ledger["blocked"] = True
                identity_matches = False
            if metadata and admission and admission["profile_id"]:
                if (metadata.profile_id != admission["profile_id"]
                        or metadata.price_version != admission["price_version"]
                        or metadata.status == "profile_mismatch"
                        or metadata.service_tier is not None and metadata.service_tier != admission["service_tier"]):
                    ledger["blocked"] = True
                    identity_matches = False
                if metadata.service_tier != admission["service_tier"]:
                    identity_matches = False
            if usage and (type(usage.input_tokens) is int and usage.input_tokens > input_bound
                          or type(usage.output_tokens) is int and usage.output_tokens > output_bound):
                ledger["blocked"] = True
            if metadata and identity_matches and metadata.price_version == self.prices.version:
                cost = self.prices.estimate(metadata.requested_deployment, metadata.returned_model, usage)
                if cost is not None:
                    actual = units(cost)
            charged = record["reserved"] if actual is None else actual
            if charged > record["reserved"]:
                ledger["blocked"] = True
            if self.policy.owner_usage:
                if record.get("phase") != "owner-v1":
                    raise PilotError()
                ledger["owner_usage"]["period_cost"] += charged - record["reserved"]
                if actual is None or state == "unknown" or metadata and metadata.status == "rate_limited":
                    ledger["blocked"] = True
            for bucket_key in record["buckets"]:
                if bucket_key in ledger["buckets"]:
                    ledger["buckets"][bucket_key]["cost"] += charged - record["reserved"]
            record.update(state=state, charged=charged, usage_known=actual is not None, settled=True)
            if state != "unknown":
                ledger["active"].pop(key, None)
            try:
                await self.store.commit([("ledger", ledger, ledger_etag), (key, record, etag)])
                return ledger["blocked"]
            except Conflict:
                continue
        raise PilotError()

    async def generate(self, provider, request, identity, operation, fingerprint):
        try:
            amount = self.bound(request)
            admission = self.admission(request)
            key = await self.reserve(identity, operation, fingerprint, amount, admission)
            await self.mark_dispatched(key)
        except PilotError:
            raise
        except Exception:
            raise PilotError() from None
        permit = DispatchPermit(hashlib.sha256(canonical(asdict(request))).hexdigest(), time.time() + 1,
                    admission=admission)
        token = _permit.set(permit)
        try:
            async with asyncio.timeout(request.timeout_seconds):
                result = await provider.generate(request)
        except BaseException as exc:
            metadata = exc.metadata if isinstance(exc, GatewayError) else None
            try:
                await self.settle(key, "failed" if metadata and metadata.usage_known else "unknown", metadata)
            except BaseException:
                pass
            if not isinstance(exc, (GatewayError, asyncio.CancelledError, TimeoutError)):
                raise PilotError() from None
            raise
        finally:
            _permit.reset(token)
        try:
            blocked = await self.settle(key, "succeeded", result.metadata)
            if blocked and self.profiles:
                raise PilotError()
        except Exception:
            raise PilotError() from None
        return result