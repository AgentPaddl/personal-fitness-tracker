"""One explicitly selected synthetic manifest case per execution, never retried."""

import asyncio
import hashlib
import json
import logging
import os
import secrets
import time
from uuid import UUID

import httpx2
from azure.identity import ManagedIdentityCredential

from app.pilot import canonical, digest
from app.pilot_table import AzureTableStore
from app.schemas.food_analysis import FoodAnalysisRequest, FoodAnalysisResponse
from qualify_auth import headers


CASES = ("T2", "T5", "T4", "T1", "L1", "L2", "P1", "R1", "R4", "P5")
PARTITION = "qualification-model-v1"
GATEWAY = "https://pft-pilot-20260919-gateway.gentleriver-150ab3f0.swedencentral.azurecontainerapps.io"


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
    operation = str(UUID(int=(int(time.time() * 1000) << 80) | (7 << 76) | (2 << 62) | secrets.randbits(62)))
    intent = {"case": case["id"], "payload_sha256": payload_hash, "operation": operation,
              "expected_attempts": expected_attempts, "created_at": int(time.time()), "state": "intent"}
    await receipts.commit([(case["id"], intent, None)])
    current, etag = await receipts.read(case["id"])
    if current != intent or not etag:
        raise RuntimeError("Durable dispatch intent not confirmed")
    result = {**intent, "state": "unknown", "http_status": None}
    try:
        response = await client.post(GATEWAY + "/v1/food-analysis",
            headers=headers(token, identity, operation, secret, service, case["payload"]), json=case["payload"])
        result["http_status"] = response.status_code
        if response.status_code == 200:
            result["response"] = FoodAnalysisResponse.model_validate(response.json()).model_dump(mode="json")
            result["state"] = "response_received"
        else:
            result["state"] = "http_failure"
    except Exception as error:
        result["error_type"] = type(error).__name__
    after, _ = await store.read("ledger")
    key = "op-" + digest(fingerprint_key.encode(), "operation", [identity, operation])
    operation_record, _ = await store.read(key)
    result.update(completed_at=int(time.time()), ledger_acceptance=after["acceptance"],
                  ledger_blocked=after["blocked"], active_count=len(after["active"]), operation_record=operation_record)
    await receipts.commit([(case["id"], result, etag)])
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