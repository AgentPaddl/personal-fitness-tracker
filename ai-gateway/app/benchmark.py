"""Fixed public-data benchmark. Durable claims never expire into permission to retry."""

from __future__ import annotations

import argparse
import asyncio
import base64
from dataclasses import asdict
from decimal import Decimal
import hashlib
from importlib.metadata import version
import json
import os
from pathlib import Path
import secrets
import stat
import sys
import time
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.errors import GatewayError
from app.pilot import Coordinator, PilotError, PilotPolicy, canonical, digest
from app.providers.pricing import GPT_54_MINI, PriceTable
from app.schemas.food_analysis import FoodAnalysisEstimate, FoodAnalysisRequest
from app.use_cases.food_analysis import FoodAnalysisUseCase


MANIFEST_HASH = "e808a8ffc0545a213b37a82b36b3157abedafa69542abd88f2490b40ecf195c6"
ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "tests/fixtures"


def sha(value):
    return hashlib.sha256(canonical(value)).hexdigest()


class Approval(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    subscription_id: UUID
    tenant_id: UUID
    operator_id: UUID
    run_id: str = Field(pattern=r"^[a-z0-9][a-z0-9-]{0,23}$")
    account_name: str = Field(pattern=r"^pftbench[a-z0-9]{4,16}$")
    storage_name: str = Field(pattern=r"^pftbench[a-z0-9]{4,16}$")
    egress_ipv4: str
    created_at: int = Field(strict=True, gt=0)
    expires_at: int = Field(strict=True, gt=0)
    manifest_sha256: str
    price_version: str
    capacity: int = Field(strict=True, ge=1, le=10)
    total_budget_eur: Literal["10.00"] = "10.00"
    usd_to_eur_reserve: Literal["1.20"] = "1.20"
    tax_multiplier_reserve: Literal["1.50"] = "1.50"
    ancillary_reserve_eur: Literal["2.00"] = "2.00"
    billing_delay_risk_accepted: bool = Field(default=False, strict=True)

    @model_validator(mode="after")
    def fixed_scope(self):
        from ipaddress import IPv4Address
        if (not IPv4Address(self.egress_ipv4).is_global or self.manifest_sha256 != MANIFEST_HASH
                or self.price_version != GPT_54_MINI.price_version
                or not 0 < self.expires_at - self.created_at <= 86400):
            raise ValueError("Approval must bind the public dataset, price, IPv4 and <=24h window.")
        return self

    @property
    def resource_group(self):
        return f"rg-pft-mini-bench-{self.run_id}"

    @property
    def group_id(self):
        return f"/subscriptions/{self.subscription_id}/resourceGroups/{self.resource_group}"

    @property
    def account_id(self):
        return self.group_id + f"/providers/Microsoft.CognitiveServices/accounts/{self.account_name}"

    @property
    def storage_id(self):
        return self.group_id + f"/providers/Microsoft.Storage/storageAccounts/{self.storage_name}"

    @property
    def identity(self):
        return str(self.tenant_id), str(self.operator_id)

    def check_window(self):
        exposure = (Decimal("4.2174") * Decimal(self.usd_to_eur_reserve)
                    * Decimal(self.tax_multiplier_reserve) + Decimal(self.ancillary_reserve_eur))
        if (not self.billing_delay_risk_accepted or exposure > Decimal(self.total_budget_eur)
                or not self.created_at <= time.time() < self.expires_at):
            raise PilotError()


def load_cases():
    manifest = json.loads((FIXTURES / "gpt54-mini-benchmark.v1.json").read_text())
    if sha(manifest) != MANIFEST_HASH:
        raise PilotError()
    use_case = FoodAnalysisUseCase(None, 90, "food_text_v1", max_output_tokens=2000)
    cases = []
    for case in manifest["cases"]:
        payload = dict(case.get("payload", {}))
        if case["mode"] == "refinement":
            payload["refinement"] = {**case["refinement"], "current_estimate": manifest["baseline"]}
        if "asset" in case:
            asset = case["asset"]
            encoded = (FIXTURES / asset["file"]).read_bytes()
            if hashlib.sha256(encoded).hexdigest() != asset["sha256"]:
                raise PilotError()
            payload["image"] = {"media_type": "image/png" if case["mode"] == "label" else "image/jpeg",
                                "data_base64": base64.b64encode(encoded).decode()}
        request = use_case.build_generation_request(FoodAnalysisRequest.model_validate(payload))
        cases.append((case, request))
    return manifest, cases


def code_hash():
    files = {str(filename.relative_to(ROOT)): hashlib.sha256(filename.read_bytes()).hexdigest()
             for filename in sorted((ROOT / "app").rglob("*.py"))}
    packages = {name: version(name) for name in ("openai", "azure-data-tables", "azure-identity", "httpx2", "Pillow", "pydantic", "jsonschema")}
    return sha([files, packages, sys.version.split()[0], hashlib.sha256((ROOT / "requirements.txt").read_bytes()).hexdigest()])


def make_coordinator(store, approval):
    limits = {"minute": 1, "day": 18, "month": 18, "concurrent": 1,
              "daily_usd": "4.2174", "monthly_usd": "4.2174"}
    policy = PilotPolicy(
        version="public-benchmark-v1", person=limits, total=limits,
        operation_max_age_seconds=86400, retention_seconds=2678400,
        max_text_schema_bytes=65536, max_image_bytes=3145728, max_image_dimension=1024,
        max_output_tokens=2000, deployment_verified_until=approval.expires_at,
        benchmark={"run_id": approval.run_id, "manifest_sha256": MANIFEST_HASH,
                   "max_attempts": 18, "max_reserved_usd": "4.2174", "expires_at": approval.expires_at},
    )
    seed = hashlib.sha256(canonical(["public-benchmark-fingerprints-not-a-credential", approval.model_dump(mode="json")])).digest()
    prices = PriceTable(version=GPT_54_MINI.price_version, currency="USD", deployments={"mini-bench": GPT_54_MINI.price})
    return Coordinator(store, policy, seed, {approval.identity}, prices,
                       {"food_text_v1": "mini-bench", "food_image_v1": "mini-bench"},
                       profile_bindings={"mini-bench": GPT_54_MINI.identifier}, max_output_tokens=2000)


class RunState:
    def __init__(self, store, control, approval, cases):
        self.store, self.control, self.approval, self.cases = store, control, approval, cases
        self.binding = sha([approval.model_dump(mode="json"), code_hash(),
                            [(case["id"], sha(asdict(request))) for case, request in cases]])

    async def initialize(self):
        self.approval.check_window()
        changes = [("ledger", self.control.initial_ledger(), None),
                   ("benchmark", {"binding": self.binding, "state": "idle", "cursor": 0,
                                  "not_before": 0, "run_id": self.approval.run_id,
                                  "initialized": True,
                                  "approval_hash": sha(self.approval.model_dump(mode="json"))}, None)]
        for case, request in self.cases:
            identifier = UUID(int=(int(time.time() * 1000) << 80) | (7 << 76)
                              | (secrets.randbits(12) << 64) | (2 << 62) | secrets.randbits(62))
            changes.append(("case-" + case["id"], {"operation": str(identifier), "request_hash": sha(asdict(request)),
                                                  "state": "ready"}, None))
        await self.store.commit(changes)

    async def claim(self, expected_cursor=None):
        self.approval.check_window()
        run, run_etag = await self.store.read("benchmark")
        if (not run or run.get("binding") != self.binding or run.get("state") != "idle"
            or expected_cursor is not None and run["cursor"] != expected_cursor
                or time.time() < run["not_before"] or not 0 <= run["cursor"] < len(self.cases)):
            raise PilotError()
        case, request = self.cases[run["cursor"]]
        record, case_etag = await self.store.read("case-" + case["id"])
        if not record or record["state"] != "ready" or record["request_hash"] != sha(asdict(request)):
            raise PilotError()
        run["state"], record["state"] = "busy", "started"
        await self.store.commit([("benchmark", run, run_etag), ("case-" + case["id"], record, case_etag)])
        return case, request, record["operation"]

    async def finish(self, case_id, result, continue_run):
        run, run_etag = await self.store.read("benchmark")
        record, case_etag = await self.store.read("case-" + case_id)
        if (not run or run.get("binding") != self.binding or run["state"] != "busy"
                or self.cases[run["cursor"]][0]["id"] != case_id or not record or record["state"] != "started"):
            raise PilotError()
        record.update(state="finished", result_hash=sha(result))
        run["cursor"] += 1
        run["state"] = ("completed" if run["cursor"] == len(self.cases) else "idle") if continue_run else "halted"
        run["not_before"] = time.time() + 60
        await self.store.commit([("benchmark", run, run_etag), ("case-" + case_id, record, case_etag)])


class CaptureProvider:
    def __init__(self, provider):
        self.provider, self.metadata = provider, None
        self.started = None
        self.completed = False

    async def generate(self, request):
        self.started = time.perf_counter()
        try:
            result = await self.provider.generate(request)
            self.metadata = result.metadata
            self.completed = True
            return result
        except GatewayError as exc:
            self.metadata = exc.metadata
            raise


def result_directory(directory):
    directory = Path(directory)
    if directory.is_symlink() or ROOT.parent == directory.resolve() or ROOT.parent in directory.resolve().parents:
        raise PilotError()
    directory.mkdir(mode=0o700, parents=True, exist_ok=True)
    if stat.S_IMODE(directory.stat().st_mode) != 0o700:
        raise PilotError()
    return directory


def write_result(directory, filename, result):
    directory = result_directory(directory)
    destination = directory / filename
    descriptor = os.open(destination, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    with os.fdopen(descriptor, "wb") as output:
        output.write(canonical(result))
        output.flush()
        os.fsync(output.fileno())
    descriptor = os.open(directory, os.O_RDONLY)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


async def run_one(state, provider, attestation, output_dir):
    output_dir = result_directory(output_dir)
    run, _ = await state.store.read("benchmark")
    if not run or run.get("binding") != state.binding or run.get("state") != "idle":
        raise PilotError()
    for previous, _ in state.cases[:run["cursor"]]:
        saved, _ = await state.store.read("case-" + previous["id"])
        result_file = output_dir / f"{previous['id']}.json"
        if (not saved or saved.get("state") != "finished" or not result_file.is_file()
                or result_file.is_symlink() or sha(json.loads(result_file.read_text())) != saved.get("result_hash")):
            raise PilotError()
    next_id = state.cases[run["cursor"]][0]["id"]
    if (output_dir / f"{next_id}.json").exists():
        raise PilotError()
    if callable(attestation):
        attestation = await attestation()
    started = time.perf_counter()
    case, request, operation = await state.claim(expected_cursor=run["cursor"])
    capture = CaptureProvider(provider)
    metadata, estimate, error = None, None, None
    try:
        result = await state.control.generate(capture, request, state.approval.identity, operation,
                                             digest(state.control.secret, "request", asdict(request)))
        estimate = FoodAnalysisEstimate.model_validate(result.data).model_dump(mode="json")
    except Exception as exc:
        error = exc.code if isinstance(exc, GatewayError) else "benchmark_failure"
    metadata = capture.metadata
    operation_key = "op-" + digest(state.control.secret, "operation", [state.approval.identity, operation])
    try:
        operation_record, _ = await state.store.read(operation_key)
        ledger, _ = await state.store.read("ledger")
    except Exception:
        operation_record, ledger, error = None, None, "ledger_read_failed"
    known = bool(operation_record and operation_record.get("settled") and operation_record.get("usage_known"))
    safe = bool(known and not error and ledger and not ledger.get("blocked") and operation_record["state"] == "succeeded")
    if not safe and error is None:
        error = "accounting_unknown" if not known else "ledger_blocked"
    checks = None
    if estimate is not None and "expected" in case:
        checks = {field: abs(estimate[field] - expected) <= max(0 if field == "calories" else 1, expected * .05)
                  for field, expected in case["expected"].items()}
    finished = time.perf_counter()
    provider_invoked = capture.started is not None
    failure_stage = None if safe else (
        "accounting_read" if error == "ledger_read_failed" else
        "admission" if not provider_invoked else
        "post_provider" if capture.completed else "provider")
    record = {"case_id": case["id"], "operation_id": operation, "run_id": state.approval.run_id,
              "binding": state.binding, "request_hash": sha(asdict(request)), "manifest_hash": MANIFEST_HASH,
              "attestation": attestation, "status": "succeeded" if safe else "halted", "error": error,
              "provider_invoked": provider_invoked, "failure_stage": failure_stage,
              "schema_valid": estimate is not None, "estimate": estimate,
              "quality": {"arithmetic": checks, "human_scores": None, "usable": None,
                          "photo_numeric_ground_truth": False, "criterion": case["criterion"]},
              "total_ms": round((finished - started) * 1000, 3),
              "admission_ms": round(((capture.started if provider_invoked else finished) - started) * 1000, 3),
              "provider_ms": metadata.duration_ms if metadata else None,
              "cold_or_warm": "cold", "usage": asdict(metadata.usage) if metadata and metadata.usage else None,
              "usage_known": known, "profile": GPT_54_MINI.identifier, "price_version": GPT_54_MINI.price_version,
              "provider_status": metadata.status if metadata else None,
              "returned_model": metadata.returned_model if metadata else None,
              "service_tier": metadata.service_tier if metadata else None,
              "charged_usd": str(Decimal(operation_record["charged"]) / 1_000_000_000) if known else None,
              "reserve_exposure_usd": "0" if known else str(GPT_54_MINI.reserve_usd(request.max_output_tokens)),
              "retained_reserve_usd": "0" if known else str(Decimal(operation_record["reserved"]) / 1_000_000_000) if operation_record else None}
    write_result(output_dir, f"{case['id']}.json", record)
    await state.finish(case["id"], record, safe)
    return record


async def execute(args):
    manifest, cases = load_cases()
    if args.command == "check":
        print(json.dumps({"cases": len(cases), "manifest_sha256": sha(manifest), "code_sha256": code_hash()}))
        return
    if args.command == "review":
        result_file = Path(args.result)
        record = json.loads(result_file.read_text())
        if (record.get("manifest_hash") != MANIFEST_HASH
                or record.get("case_id") not in {case["id"] for case, _ in cases}):
            raise PilotError()
        review = {"result_hash": sha(record), "case_id": record["case_id"], "reviewed_at": int(time.time()),
                  "usable": args.usable == "yes", "portion_handling": args.portion,
                  "nutrition_plausibility": args.nutrition, "correction_adherence": args.correction,
                  "uncertainty": args.uncertainty}
        write_result(result_file.parent, f"{record['case_id']}.review.json", review)
        return
    approval = Approval.model_validate_json(Path(args.approval).read_text())
    from app.benchmark_azure import AzureBenchmark

    async with AzureBenchmark(approval) as azure:
        await azure.attest()
        store = azure.store()
        try:
            control = make_coordinator(store, approval)
            state = RunState(store, control, approval, cases)
            if args.command == "init":
                await state.initialize()
            else:
                provider = azure.provider(control)
                try:
                    record = await run_one(state, provider, azure.attest, Path(args.results) / approval.run_id)
                    print(json.dumps({"case_id": record["case_id"], "status": record["status"]}))
                    if record["status"] != "succeeded":
                        raise PilotError()
                finally:
                    await provider.aclose()
        finally:
            await store.close()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("check")
    review = commands.add_parser("review")
    review.add_argument("--result", required=True)
    review.add_argument("--usable", choices=("yes", "no"), required=True)
    for field in ("portion", "nutrition", "correction", "uncertainty"):
        review.add_argument("--" + field, type=int, choices=range(5))
    initialize = commands.add_parser("init")
    initialize.add_argument("--approval", required=True)
    run = commands.add_parser("next")
    run.add_argument("--approval", required=True)
    run.add_argument("--results", required=True)
    args = parser.parse_args()
    try:
        asyncio.run(execute(args))
    except (Exception, KeyboardInterrupt):
        parser.exit(1, "Benchmark stopped; no retry or replacement dispatch is authorized.\n")


if __name__ == "__main__":
    main()