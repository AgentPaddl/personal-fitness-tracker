"""One explicitly selected synthetic manifest case per execution, never retried."""

import asyncio
import hashlib
import json
import logging
import os
import secrets
import time
from copy import deepcopy
from uuid import UUID

import httpx2
from azure.identity import ManagedIdentityCredential

from app.pilot import Coordinator, canonical, digest
from app.pilot_table import AzureTableStore
from app.schemas.food_analysis import FoodAnalysisRequest, FoodAnalysisResponse
from qualify_auth import headers


CASES = ("T2", "T5", "T4", "T1", "L1", "L2", "P1", "R1", "R4", "P5", "L1", "L2", "P1", "P5")
PARTITION = "qualification-model-v1"
GATEWAY = "https://pft-pilot-20260919-gateway.gentleriver-150ab3f0.swedencentral.azurecontainerapps.io"


async def extend_acceptance(control, revised_policy, ledger_sha256, expected_etag, revised_policy_sha256):
    if os.environ.get("AI_API_ONLY_ENABLED") != "false":
        raise RuntimeError("Policy amendment requires disabled admission")
    previous = control.policy.model_dump(mode="json")
    expected = deepcopy(previous)
    if (not control.policy.acceptance or previous["acceptance"]["max_attempts"] != 10
            or previous["acceptance"]["max_reserved_usd"] != "2.343"
            or any(previous[scope][field] != 10 for scope in ("person", "total") for field in ("day", "month"))):
        raise RuntimeError("Only the original ten-attempt policy may be amended")
    expected["acceptance"].update(max_attempts=14, max_reserved_usd="3.2802")
    for scope in ("person", "total"):
        expected[scope].update(day=14, month=14)
    if (revised_policy.model_dump(mode="json") != expected
            or hashlib.sha256(canonical(expected)).hexdigest() != revised_policy_sha256):
        raise RuntimeError("Amendment differs from the reviewed four-attempt extension")
    ledger, etag = await control._read_ledger()
    if (etag != expected_etag or hashlib.sha256(canonical(ledger)).hexdigest() != ledger_sha256
            or ledger["active"] or ledger["acceptance"] != {"attempts": 10, "reserved": 2343000000}):
        raise RuntimeError("Ledger differs from the reviewed inactive ten-attempt state")
    revised = Coordinator(control.store, revised_policy, control.secret, control.allowlist, control.prices,
                          control.routes, profile_bindings=control.profile_bindings,
                          max_output_tokens=control.max_output_tokens)
    amendment = {"previous_policy": control.policy_id, "revised_policy": revised.policy_id,
                 "previous_ledger_sha256": ledger_sha256, "revised_policy_sha256": revised_policy_sha256,
                 "acceptance": deepcopy(ledger["acceptance"]), "additional_attempts": 4,
                 "additional_reserved_usd": "0.9372", "created_at": int(time.time())}
    ledger["policy"] = revised.policy_id
    await control.store.commit([("ledger", ledger, etag), ("acceptance-extension-14-v1", amendment, None)])
    return amendment


async def complete_terminal_429(store, receipt, identity, fingerprint_key, ledger_sha256, receipt_sha256):
    if (os.environ.get("AI_API_ONLY_ENABLED") != "false"
            or hashlib.sha256(canonical(receipt)).hexdigest() != receipt_sha256
            or receipt.get("case") not in CASES or receipt.get("http_status") != 429
            or receipt.get("state") != "http_failure"
            or "error_code" in receipt and receipt["error_code"] != "provider_rate_limited"
            or type(receipt.get("created_at")) is not int
            or type(receipt.get("completed_at")) is not int
            or not receipt["created_at"] <= receipt["completed_at"] <= time.time() - 120):
        raise RuntimeError("A reviewed terminal 429 receipt and disabled admission are required")
    ledger, ledger_etag = await store.read("ledger")
    key = "op-" + digest(fingerprint_key.encode(), "operation", [identity, receipt["operation"]])
    record, record_etag = await store.read(key)
    if (ledger is None or hashlib.sha256(canonical(ledger)).hexdigest() != ledger_sha256
            or ledger["blocked"] or ledger["acceptance"] != receipt["ledger_acceptance"]
            or ledger["active"].get(key) != digest(fingerprint_key.encode(), "person", identity)
            or record != receipt["operation_record"] or not record
            or record.get("state") != "unknown" or record.get("settled") is not True
            or record.get("usage_known") is not False
            or record.get("charged") != record.get("reserved") or record.get("reserved") != 234300000
            or record.get("execution_state") is not None):
        raise RuntimeError("Live ledger/operation differs from the reviewed completion evidence")
    del ledger["active"][key]
    record.update(execution_state="completed", completion_evidence_sha256=receipt_sha256,
                  execution_completed_at=receipt["completed_at"], slot_released_at=int(time.time()))
    await store.commit([("ledger", ledger, ledger_etag), (key, record, record_etag)])
    return {"slot_released": True, "state": record["state"], "usage_known": False,
            "charged": record["charged"], "acceptance": ledger["acceptance"],
            "completion_evidence_sha256": receipt_sha256}


async def run_case(client, store, receipts, case, expected_attempts, allowed_hashes, token, identity, secret, service, fingerprint_key):
    normalized = FoodAnalysisRequest.model_validate(case["payload"]).model_dump(mode="json")
    payload_hash = hashlib.sha256(canonical(normalized)).hexdigest()
    if (type(expected_attempts) is not int or not 0 <= expected_attempts < len(CASES)
            or case["id"] != CASES[expected_attempts]
            or payload_hash != case["payload_sha256"] or payload_hash not in allowed_hashes):
        raise RuntimeError("Case is not the next approved manifest input")
    before, _ = await store.read("ledger")
    if (before is None or before["blocked"] or before["active"]
            or before["acceptance"] != {"attempts": expected_attempts, "reserved": expected_attempts * 234300000}):
        raise RuntimeError("Ledger is not ready for the next bounded attempt")
    if time.time() < before.get("last_time", 0) + 65:
        raise RuntimeError("Next distinct case requires at least 65 seconds since the last admission")
    receipt_key = case["id"] if expected_attempts < 10 else "correction-" + case["id"]
    operation = str(UUID(int=(int(time.time() * 1000) << 80) | (7 << 76) | (2 << 62) | secrets.randbits(62)))
    intent = {"case": case["id"], "payload_sha256": payload_hash, "operation": operation,
              "expected_attempts": expected_attempts, "created_at": int(time.time()), "state": "intent"}
    await receipts.commit([(receipt_key, intent, None)])
    current, etag = await receipts.read(receipt_key)
    if current != intent or not etag:
        raise RuntimeError("Durable dispatch intent not confirmed")
    result = {**intent, "state": "unknown", "http_status": None}
    try:
        response = await client.post(GATEWAY + "/v1/food-analysis",
            headers=headers(token, identity, operation, secret, service, case["payload"]), json=case["payload"])
        result["http_status"] = response.status_code
        request_id = response.headers.get("x-request-id")
        try:
            result["gateway_request_id"] = str(UUID(request_id)) if request_id else None
        except ValueError:
            result["gateway_request_id"] = None
        retry_after = response.headers.get("retry-after", "")
        result["gateway_retry_after_seconds"] = (
            int(retry_after) if retry_after.isascii() and retry_after.isdecimal() and len(retry_after) <= 5 else None)
        if response.status_code == 200:
            result["response"] = FoodAnalysisResponse.model_validate(response.json()).model_dump(mode="json")
            result["state"] = "response_received"
        else:
            result["state"] = "http_failure"
            try:
                code = response.json().get("error", {}).get("code")
                result["error_code"] = code if code in {"provider_rate_limited", "pilot_limit", "pilot_unavailable",
                    "provider_output_invalid", "provider_timeout", "provider_unavailable"} else None
            except (ValueError, AttributeError):
                result["error_code"] = None
    except Exception as error:
        result["error_type"] = type(error).__name__
    after, _ = await store.read("ledger")
    key = "op-" + digest(fingerprint_key.encode(), "operation", [identity, operation])
    operation_record, _ = await store.read(key)
    result.update(completed_at=int(time.time()), ledger_acceptance=after["acceptance"],
                  ledger_blocked=after["blocked"], active_count=len(after["active"]), operation_record=operation_record)
    await receipts.commit([(receipt_key, result, etag)])
    print("MODEL_CHECK " + json.dumps({name: result[name] for name in
        ("case", "state", "http_status", "ledger_acceptance", "ledger_blocked", "active_count")}), flush=True)
    if (after["blocked"] or after["active"] or after["acceptance"]["attempts"] != expected_attempts + 1
            or not operation_record or not operation_record.get("settled") or not operation_record.get("usage_known")
            or result["state"] != "response_received"):
        raise RuntimeError("Attempt needs operator review; no retry permitted")
    return result


async def execute():
    if (os.environ.get("AI_PILOT_RESOURCE_GROUP") != "pft-pilot-20260919"
            or os.environ.get("AI_PILOT_TABLE_NAME") != "PilotLedger"
            or os.environ.get("AI_PILOT_TABLE_ENDPOINT") != "https://pftposyuw3m453fx4.table.core.windows.net"
            or os.environ.get("QUALIFICATION_GATEWAY") != GATEWAY):
        raise RuntimeError("Unapproved acceptance target")
    store = AzureTableStore.connect(os.environ["AI_PILOT_TABLE_ENDPOINT"], os.environ["AI_PILOT_TABLE_NAME"])
    receipts = AzureTableStore.connect(os.environ["AI_PILOT_TABLE_ENDPOINT"], os.environ["AI_PILOT_TABLE_NAME"])
    receipts.partition = PARTITION
    try:
        case = json.loads(os.environ["QUALIFICATION_CASE_JSON"])
        logger = logging.Logger("acceptance.identity")
        logger.disabled = True
        with ManagedIdentityCredential(client_id=os.environ["GATEWAY_BACKEND_CLIENT_ID"],
                logger=logger, logging_enable=False, retry_total=0, connection_timeout=3, read_timeout=5) as credential:
            token = credential.get_token("api://" + os.environ["GATEWAY_WORKLOAD_AUDIENCE"] + "/.default").token
            async with httpx2.AsyncClient(timeout=110, follow_redirects=False) as client:
                await run_case(client, store, receipts, case, int(os.environ["QUALIFICATION_EXPECTED_ATTEMPTS"]),
                    json.loads(os.environ["QUALIFICATION_ALLOWED_HASHES"]), token,
                    (os.environ["AI_PILOT_TENANT_ID"], os.environ["QUALIFICATION_OWNER_ID"]),
                    os.environ["AI_PILOT_SIGNING_KEY"], os.environ["GATEWAY_SERVICE_TOKEN"],
                    os.environ["AI_PILOT_FINGERPRINT_KEY"])
    finally:
        await store.close()
        await receipts.close()


if __name__ == "__main__":
    try:
        asyncio.run(execute())
    except Exception as error:
        print("MODEL_CHECK_FAILED " + type(error).__name__, flush=True)
        raise SystemExit(1) from None