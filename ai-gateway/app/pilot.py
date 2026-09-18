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
from app.providers.pricing import PriceTable


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

    @model_validator(mode="after")
    def retention_covers_admission(self):
        if self.retention_seconds <= self.operation_max_age_seconds + 300:
            raise ValueError("Retention must exceed the operation acceptance window.")
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


_permit: ContextVar[DispatchPermit | None] = ContextVar("pilot_dispatch", default=None)


def consume_permit(request: StructuredGenerationRequest):
    permit = _permit.get()
    if permit is None or permit.used or time.time() > permit.expires:
        raise PilotError()
    if hashlib.sha256(canonical(asdict(request))).hexdigest() != permit.request_digest:
        raise PilotError()
    permit.used = True


class Coordinator:
    def __init__(self, store: ControlStore, policy: PilotPolicy, secret: bytes,
                 allowlist: set[tuple[str, str]], prices: PriceTable, routes: dict[str, str],
                 clock=time.time):
        if len(secret) < 32 or not 1 <= len(allowlist) <= 2 or not routes:
            raise PilotError()
        self.store, self.policy, self.secret = store, policy, secret
        self.allowlist, self.prices, self.routes, self.clock = allowlist, prices, routes, clock
        self.policy_id = digest(secret, "policy", [policy.model_dump(mode="json"), sorted(allowlist),
                                                 prices.model_dump(mode="json"), routes])

    def initial_ledger(self):
        return {"policy": self.policy_id, "buckets": {}, "active": {}, "blocked": False, "last_time": 0}

    def bound(self, request: StructuredGenerationRequest) -> int:
        policy = self.policy
        price = self.prices.deployments.get(self.routes.get(request.model_purpose))
        if (self.clock() >= policy.deployment_verified_until or price is None
                or price.model != "gpt-4.1-mini-2025-04-14"
                or type(request.max_output_tokens) is not int
                or not 1 <= request.max_output_tokens <= policy.max_output_tokens
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
        return units((Decimal(1_047_576) * max(price.input_per_million, price.cached_input_per_million)
                      + request.max_output_tokens * price.output_per_million) / 1_000_000)

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
        return ledger, etag

    async def reserve(self, identity, operation, fingerprint, amount):
        now = self.clock()
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
                      "dispatch_before": now + 30, "buckets": [entry[0] for entry in keys]}
            try:
                await self.store.commit([("ledger", ledger, etag), (key, record, None)])
                return key
            except Conflict:
                continue
        raise PilotError()

    async def mark_dispatched(self, key):
        record, etag = await self.store.read(key)
        if not record or record["state"] != "pending" or self.clock() > record["dispatch_before"]:
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
            if metadata and metadata.returned_model is not None and metadata.returned_model != "gpt-4.1-mini-2025-04-14":
                ledger["blocked"] = True
            if usage and (type(usage.input_tokens) is int and usage.input_tokens > 1_047_576
                          or type(usage.output_tokens) is int and usage.output_tokens > self.policy.max_output_tokens):
                ledger["blocked"] = True
            if metadata and metadata.usage is not None and metadata.price_version == self.prices.version:
                counts = (usage.input_tokens, usage.output_tokens, usage.cached_input_tokens)
                if (all(type(count) is int and count >= 0 for count in counts)
                        and usage.cached_input_tokens <= usage.input_tokens
                        and (usage.reasoning_tokens is None or type(usage.reasoning_tokens) is int
                             and 0 <= usage.reasoning_tokens <= usage.output_tokens)):
                    cost = self.prices.estimate(metadata.requested_deployment, metadata.returned_model, usage)
                    if cost is not None:
                        actual = units(cost)
            charged = record["reserved"] if actual is None else actual
            if charged > record["reserved"]:
                ledger["blocked"] = True
            for bucket_key in record["buckets"]:
                if bucket_key in ledger["buckets"]:
                    ledger["buckets"][bucket_key]["cost"] += charged - record["reserved"]
            record.update(state=state, charged=charged, usage_known=actual is not None, settled=True)
            if state != "unknown":
                ledger["active"].pop(key, None)
            try:
                await self.store.commit([("ledger", ledger, ledger_etag), (key, record, etag)])
                return
            except Conflict:
                continue
        raise PilotError()

    async def generate(self, provider, request, identity, operation, fingerprint):
        try:
            amount = self.bound(request)
            key = await self.reserve(identity, operation, fingerprint, amount)
            await self.mark_dispatched(key)
        except PilotError:
            raise
        except Exception:
            raise PilotError() from None
        permit = DispatchPermit(hashlib.sha256(canonical(asdict(request))).hexdigest(), time.time() + 1)
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
            await self.settle(key, "succeeded", result.metadata)
        except Exception:
            raise PilotError() from None
        return result