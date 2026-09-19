"""One-shot real MI/JWT/HMAC probes on the existing pilot route; no model input."""

import base64
import hashlib
import hmac
import json
import logging
import os
import time
from uuid import UUID

import httpx2
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


def main():
    base = os.environ["QUALIFICATION_GATEWAY"]
    if base != "https://pft-pilot-20260919-gateway.gentleriver-150ab3f0.swedencentral.azurecontainerapps.io":
        raise RuntimeError("Unapproved qualification target")
    expected = int(os.environ.get("QUALIFICATION_EXPECTED", "503"))
    if expected not in {403, 503}:
        raise RuntimeError("Qualification never expects generation success")
    logger = logging.Logger("qualification.identity")
    logger.disabled = True
    with ManagedIdentityCredential(client_id=os.environ["GATEWAY_BACKEND_CLIENT_ID"],
            logger=logger, logging_enable=False, retry_total=0, connection_timeout=3, read_timeout=5) as credential:
        token = credential.get_token("api://" + os.environ["GATEWAY_WORKLOAD_AUDIENCE"] + "/.default").token
        with httpx2.Client(timeout=30, follow_redirects=False) as client:
            results = probe(client, base, token,
                (os.environ["AI_PILOT_TENANT_ID"], os.environ["QUALIFICATION_OWNER_ID"]),
                os.environ["AI_PILOT_SIGNING_KEY"], os.environ["GATEWAY_SERVICE_TOKEN"], expected)
    print("AUTH_QUALIFICATION " + json.dumps({"checked_at": int(time.time()), "checks": results,
        "model_requests": 0, "path": "existing_gateway_analysis", "token_source": "explicit_backend_uami"}), flush=True)


if __name__ == "__main__":
    try:
        main()
    except Exception as error:
        print("AUTH_QUALIFICATION_FAILED " + type(error).__name__, flush=True)
        raise SystemExit(1) from None