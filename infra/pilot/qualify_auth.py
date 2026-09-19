"""One-shot real MI/JWT/HMAC probes on the existing pilot route; no model input."""

import asyncio
import base64
import hashlib
import hmac
from http.client import HTTPSConnection
import json
import logging
import os
import re
import time
from urllib.parse import urlsplit
from uuid import UUID

import httpx2
from azure.core.exceptions import ClientAuthenticationError
from azure.identity import ManagedIdentityCredential


PAYLOAD = {"food_description": "synthetic authentication qualification only; not a model acceptance case"}


def headers(token, identity, operation, secret, service, payload, issued=None):
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True, allow_nan=False).encode()
    envelope = {"tid": identity[0], "oid": identity[1], "operation": operation,
                "issued": int(time.time()) if issued is None else issued,
                "body": hashlib.sha256(canonical).hexdigest(), "aud": "fitness-gateway-pilot-v1"}
    encoded = base64.urlsafe_b64encode(json.dumps(envelope, sort_keys=True, separators=(",", ":")).encode()).decode()
    signature = hmac.new(secret.encode(), encoded.encode(), hashlib.sha256).hexdigest()
    return {"Authorization": "Bearer " + token, "X-Service-Token": service,
            "X-Pilot-Authorization": encoded + "." + signature, "X-Operation-Id": operation}


def probe(client, base, token, identity, secret, service, expected_valid):
    operation = str(UUID(int=(int(time.time() * 1000) << 80) | (7 << 76) | (2 << 62) | 1))
    valid = headers(token, identity, operation, secret, service, PAYLOAD)
    cases = [("valid_authentication", valid, PAYLOAD, expected_valid)]
    cases.append(("missing_workload", {**valid, "Authorization": ""}, PAYLOAD, 403))
    parts = token.split(".")
    signature = bytearray(base64.urlsafe_b64decode(parts[2] + "=" * (-len(parts[2]) % 4)))
    signature[0] ^= 1
    damaged = ".".join([*parts[:2], base64.urlsafe_b64encode(signature).decode().rstrip("=")])
    cases.append(("bad_jwt_signature", {**valid, "Authorization": "Bearer " + damaged}, PAYLOAD, 403))
    cases.append(("bad_service_secret", {**valid, "X-Service-Token": "synthetic-invalid"}, PAYLOAD, 403))
    cases.append(("bad_hmac", {**valid, "X-Pilot-Authorization": valid["X-Pilot-Authorization"].split(".")[0] + "." + "0" * 64}, PAYLOAD, 403))
    cases.append(("changed_body", valid, {"food_description": "different synthetic content"}, 403))
    cases.append(("changed_operation", {**valid, "X-Operation-Id": str(UUID(int=UUID(operation).int + 1))}, PAYLOAD, 403))
    cases.append(("expired_assertion", headers(token, identity, operation, secret, service, PAYLOAD, int(time.time()) - 120), PAYLOAD, 403))
    cases.append(("foreign_user", headers(token, (identity[0], "00000000-0000-4000-8000-000000000001"), operation, secret, service, PAYLOAD), PAYLOAD, 403))
    results = []
    for name, authorization, payload, expected in cases:
        response = client.post(base + "/v1/food-analysis", headers=authorization, json=payload)
        record = {"check": name, "status": response.status_code, "expected": expected, "passed": response.status_code == expected}
        results.append(record)
        print("AUTH_CHECK " + json.dumps(record), flush=True)
        if not record["passed"]:
            raise RuntimeError("Authentication qualification failed: " + name)
    return results


def probe_limits(client, base, token, identity, secret, service):
    operation = str(UUID(int=(int(time.time() * 1000) << 80) | (7 << 76) | (2 << 62) | 1))
    valid = headers(token, identity, operation, secret, service, PAYLOAD)
    limit = 4 * 1024 * 1024 + 64 * 1024
    cases = [
        ("unsupported_media_before_auth", {"Content-Type": "text/plain"}, b"{}", 415),
        ("declared_size_before_auth", {"Content-Type": "application/json"}, b" " * (limit + 1), 413),
        ("malformed_json", {**valid, "Content-Type": "application/json"}, b"{", 400),
        ("nonobject_json", {**valid, "Content-Type": "application/json"}, b"[]", 400),
        ("chunked_size", {**valid, "Content-Type": "application/json"}, iter([b" " * limit, b" "]), 413),
    ]
    results = []
    for name, authorization, content, expected in cases:
        response = client.post(base + "/v1/food-analysis", headers=authorization, content=content)
        record = {"check": name, "status": response.status_code, "expected": expected, "passed": response.status_code == expected}
        results.append(record)
        print("AUTH_CHECK " + json.dumps(record), flush=True)
        if not record["passed"]:
            raise RuntimeError("Boundary qualification failed: " + name)
    return results


def probe_slow_body(base, token, identity, secret, service):
    operation = str(UUID(int=(int(time.time() * 1000) << 80) | (7 << 76) | (2 << 62) | 1))
    valid = headers(token, identity, operation, secret, service, PAYLOAD)
    connection = HTTPSConnection(urlsplit(base).hostname, timeout=20)
    started = time.monotonic()
    try:
        connection.putrequest("POST", "/v1/food-analysis")
        for name, value in {**valid, "Content-Type": "application/json", "Transfer-Encoding": "chunked"}.items():
            connection.putheader(name, value)
        connection.endheaders()
        connection.send(b"1\r\n{\r\n")
        response = connection.getresponse()
        elapsed = time.monotonic() - started
        record = {"check": "slow_body_deadline", "status": response.status, "expected": 408,
                  "elapsed_seconds": round(elapsed, 2), "passed": response.status == 408 and elapsed < 20}
        print("AUTH_CHECK " + json.dumps(record), flush=True)
        if not record["passed"]:
            raise RuntimeError("Slow body deadline not established")
        return record
    finally:
        connection.close()


def probe_foreign_workload(client, base, identity, secret, service, logger):
    with ManagedIdentityCredential(client_id=os.environ["AI_PILOT_GATEWAY_CLIENT_ID"],
            logger=logger, logging_enable=False, retry_total=0, connection_timeout=3, read_timeout=5) as credential:
        try:
            token = credential.get_token("api://" + os.environ["GATEWAY_WORKLOAD_AUDIENCE"] + "/.default").token
        except ClientAuthenticationError as error:
            if "AADSTS501051" not in str(error):
                print("AUTH_CHECK " + json.dumps({"check": "foreign_workload_token", "passed": False,
                    "error_codes": sorted(set(re.findall(r"AADSTS[0-9]+", str(error)))),
                    "http_status": getattr(error, "status_code", None)}), flush=True)
                raise RuntimeError("Foreign token denial was not an app-role denial") from None
            record = {"check": "foreign_workload", "boundary": "entra_app_role", "passed": True}
        else:
            operation = str(UUID(int=(int(time.time() * 1000) << 80) | (7 << 76) | (2 << 62) | 1))
            response = client.post(base + "/v1/food-analysis",
                headers=headers(token, identity, operation, secret, service, PAYLOAD), json=PAYLOAD)
            record = {"check": "foreign_workload", "boundary": "gateway", "status": response.status_code,
                      "expected": 403, "passed": response.status_code == 403}
        print("AUTH_CHECK " + json.dumps(record), flush=True)
        if not record["passed"]:
            raise RuntimeError("Foreign workload was not denied")
        return record


async def read_ledger():
    from app.pilot_table import AzureTableStore

    if (os.environ.get("AI_PILOT_RESOURCE_GROUP") != "pft-pilot-20260919"
            or os.environ.get("AI_PILOT_TABLE_NAME") != "PilotLedger"
            or os.environ.get("AI_PILOT_TABLE_ENDPOINT") != "https://pftposyuw3m453fx4.table.core.windows.net"):
        raise RuntimeError("Unapproved ledger target")
    store = AzureTableStore.connect(os.environ["AI_PILOT_TABLE_ENDPOINT"], os.environ["AI_PILOT_TABLE_NAME"])
    try:
        ledger, etag = await store.read("ledger")
        if ledger is None or ledger["active"] or ledger["acceptance"] != {"attempts": 0, "reserved": 0}:
            raise RuntimeError("Expected untouched acceptance ledger")
        return ledger, etag
    finally:
        await store.close()


def main():
    base = os.environ["QUALIFICATION_GATEWAY"]
    if base != "https://pft-pilot-20260919-gateway.gentleriver-150ab3f0.swedencentral.azurecontainerapps.io":
        raise RuntimeError("Unapproved qualification target")
    expected = int(os.environ.get("QUALIFICATION_EXPECTED", "503"))
    if expected not in {403, 503}:
        raise RuntimeError("Qualification never expects generation success")
    mode = os.environ.get("QUALIFICATION_MODE", "auth")
    if mode not in {"auth", "boundaries", "foreign"} or mode != "auth" and expected != 503:
        raise RuntimeError("Unapproved qualification mode")
    before = asyncio.run(read_ledger()) if mode != "auth" else None
    if before is not None:
        from app.pilot import canonical

        print("AUTH_CHECK " + json.dumps({"check": "pilot_ledger_before", "passed": True,
            "attempts": 0, "reserved": 0, "sha256": hashlib.sha256(canonical(before[0])).hexdigest()}), flush=True)
    logger = logging.Logger("qualification.identity")
    logger.disabled = True
    with ManagedIdentityCredential(client_id=os.environ["GATEWAY_BACKEND_CLIENT_ID"],
            logger=logger, logging_enable=False, retry_total=0, connection_timeout=3, read_timeout=5) as credential:
        token = credential.get_token("api://" + os.environ["GATEWAY_WORKLOAD_AUDIENCE"] + "/.default").token
        with httpx2.Client(timeout=30, follow_redirects=False) as client:
            identity = (os.environ["AI_PILOT_TENANT_ID"], os.environ["QUALIFICATION_OWNER_ID"])
            secret, service = os.environ["AI_PILOT_SIGNING_KEY"], os.environ["GATEWAY_SERVICE_TOKEN"]
            if mode == "auth":
                results = probe(client, base, token, identity, secret, service, expected)
            elif mode == "boundaries":
                results = probe_limits(client, base, token, identity, secret, service)
                results.append(probe_slow_body(base, token, identity, secret, service))
                results.append(probe_foreign_workload(client, base, identity, secret, service, logger))
            else:
                results = [probe_foreign_workload(client, base, identity, secret, service, logger)]
    if before is not None:
        after = asyncio.run(read_ledger())
        if before != after:
            raise RuntimeError("Pilot ledger changed")
        from app.pilot import canonical

        record = {"check": "pilot_ledger_unchanged", "passed": True, "attempts": 0, "reserved": 0,
                  "sha256": hashlib.sha256(canonical(after[0])).hexdigest()}
        results.append(record)
        print("AUTH_CHECK " + json.dumps(record), flush=True)
    print("AUTH_QUALIFICATION " + json.dumps({"checked_at": int(time.time()), "checks": results,
        "model_requests": 0, "path": "existing_gateway_analysis", "token_source": "explicit_backend_uami"}), flush=True)


if __name__ == "__main__":
    try:
        main()
    except Exception as error:
        print("AUTH_QUALIFICATION_FAILED " + type(error).__name__, flush=True)
        raise SystemExit(1) from None