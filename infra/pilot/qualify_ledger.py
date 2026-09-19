"""Model-free qualification against an isolated partition in the pilot table."""

import asyncio
import hashlib
import json
import os
import time
from uuid import UUID, uuid4

from app.config import Settings
from app.pilot import Coordinator, PilotError, canonical
from app.pilot_access import build_coordinator
from app.providers.base import GenerationMessage, StructuredGenerationRequest


async def expect_denial(awaitable, code):
    try:
        await awaitable
    except PilotError as error:
        if error.code == code:
            return
        raise AssertionError("Unexpected admission denial") from None
    raise AssertionError("Admission unexpectedly succeeded")


async def exercise(control):
    identity = next(iter(control.allowlist))
    now = control.clock()
    operation = str(UUID(int=(int(now * 1000) << 80) | (7 << 76) | (2 << 62) | 1))
    generation = StructuredGenerationRequest(next(iter(control.routes)),
        [GenerationMessage("user", "synthetic ledger qualification; never dispatched")],
        {"type": "object"}, 1, max_output_tokens=2000)
    amount, admission = control.bound(generation), control.admission(generation)
    key = await control.reserve(identity, operation, "synthetic", amount, admission)
    await expect_denial(control.reserve(identity, operation, "synthetic", amount, admission), "operation_consumed")
    await expect_denial(control.reserve(identity, operation, "changed", amount, admission), "operation_conflict")
    await expect_denial(control.reserve(identity, str(uuid4()), "synthetic", amount, admission), "operation_required")
    await expect_denial(control.reserve((identity[0], str(uuid4())), operation, "synthetic", amount, admission), "pilot_forbidden")
    await control.mark_dispatched(key)
    await control.settle(key, "unknown", None)
    restarted = Coordinator(control.store, control.policy, control.secret, control.allowlist,
        control.prices, control.routes, profile_bindings=control.profile_bindings,
        max_output_tokens=control.max_output_tokens)
    ledger, _ = await restarted._read_ledger()
    record, _ = await restarted.store.read(key)
    assert record["state"] == "unknown" and record["charged"] == amount
    assert record["usage_known"] is False and key in ledger["active"]
    assert ledger["acceptance"] == {"attempts": 1, "reserved": amount}
    await expect_denial(restarted.reserve(identity, operation, "synthetic", amount, admission), "operation_consumed")
    await expect_denial(restarted.settle(key, "succeeded", None), "pilot_unavailable")
    restarted.policy_id = "qualification-policy-drift"
    await expect_denial(restarted._read_ledger(), "pilot_unavailable")
    return {"duplicate_denied": True, "changed_body_denied": True,
            "invalid_operation_denied": True, "foreign_identity_denied": True,
            "unknown_hold_survives_restart": True, "double_settlement_denied": True,
            "policy_drift_denied": True, "model_attempts": 0}


async def main():
    if (os.environ.get("AI_API_ONLY_ENABLED") != "false"
            or os.environ.get("AI_PILOT_RESOURCE_GROUP") != "pft-pilot-20260919"
            or os.environ.get("AI_PILOT_TABLE_NAME") != "PilotLedger"):
        raise RuntimeError("Qualification requires the authorized AI-off pilot")
    control = build_coordinator(settings=Settings())
    original_partition = control.store.partition
    partition = "qualification-" + uuid4().hex
    try:
        before, before_etag = await control._read_ledger()
        assert not before["active"] and control.policy.acceptance is not None
        assert time.time() < control.policy.acceptance.expires_at
        control.store.partition = partition
        await control.store.commit([("ledger", control.initial_ledger(), None)])
        try:
            result = await exercise(control)
        finally:
            async for entity in control.store.client.query_entities(
                    "PartitionKey eq @partition", parameters={"partition": partition}, logging_enable=False):
                await control.store.client.delete_entity(partition, entity["RowKey"], logging_enable=False)
            control.store.partition = original_partition
        after, after_etag = await control._read_ledger()
        assert canonical(before) == canonical(after) and before_etag == after_etag
        result.update(checked_at=int(time.time()), pilot_ledger_unchanged=True,
                      pilot_attempts=after["acceptance"]["attempts"],
                      pilot_reserved_units=after["acceptance"]["reserved"],
                      pilot_ledger_sha256=hashlib.sha256(canonical(after)).hexdigest(),
                      qualification_partition_deleted=True)
        print("QUALIFICATION " + json.dumps(result, sort_keys=True), flush=True)
    finally:
        await control.store.close()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except Exception as error:
        print("QUALIFICATION FAILED " + type(error).__name__, flush=True)
        raise SystemExit(1) from None