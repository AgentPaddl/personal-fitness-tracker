"""Offline packaging and public deployment-output conversion. Never runs Azure CLI."""

import argparse
import base64
import hashlib
import json
from pathlib import Path
import re
import sys
from urllib.parse import urlsplit
from uuid import UUID
import zipfile

ROOT = Path(__file__).resolve().parents[2]
GATEWAY_ROLE_ID = "118e50f5-4c4d-4f26-9a08-d4859bd997de"
API_SCOPE_ID = "bb4a39c5-a4d1-4708-8540-f2fc5352d8c7"


def outputs(raw):
    data = raw.get("properties", {}).get("outputs", raw)
    required = ("apiBaseURL", "tenantId", "nativeClientId", "backendAudience", "gatewayAudience", "backendPrincipalId", "backendClientId", "resourceGroup")
    result = {name: data[name]["value"] for name in required}
    for name in required[1:-1]:
        if str(UUID(result[name])) != result[name]:
            raise ValueError("Invalid deployment identifier.")
    if not re.fullmatch(r"pft-pilot-[a-z0-9-]{3,40}", result["resourceGroup"]):
        raise ValueError("Not a separate pilot resource group.")
    url = urlsplit(result["apiBaseURL"])
    if (url.scheme != "https" or not url.hostname or not url.hostname.startswith("pft-pilot-")
            or not url.hostname.endswith(".azurewebsites.net") or url.path != "/api"
            or url.username or url.password or url.port not in (None, 443) or url.query or url.fragment):
        raise ValueError("Missing pilot backend deployment output.")
    return result


def ios_config(data):
    values = {"PILOT_API_BASE_URL": data["apiBaseURL"], "PILOT_ENTRA_TENANT_ID": data["tenantId"],
              "PILOT_ENTRA_CLIENT_ID": data["nativeClientId"],
              "PILOT_ENTRA_API_SCOPE": f"api://{data['backendAudience']}/FoodAnalysis.Access"}
    return "\n".join(f"{key} = {value.replace('://', ':/$()/')}" for key, value in values.items()) + "\n"


def entra_requests(data, gateway_service_principal):
    UUID(gateway_service_principal)
    return {
        "gatewayApplicationPatch": {"api": {"requestedAccessTokenVersion": 2},
            "identifierUris": [f"api://{data['gatewayAudience']}"],
            "optionalClaims": {"accessToken": [{"name": "idtyp", "source": None, "essential": True, "additionalProperties": []}]},
            "appRoles": [{"allowedMemberTypes": ["Application"], "description": "Invoke the private fitness gateway", "displayName": "Gateway Invoke", "id": GATEWAY_ROLE_ID, "isEnabled": True, "value": "Gateway.Invoke"}]},
        "gatewayServicePrincipalPatch": {"appRoleAssignmentRequired": True},
        "backendIdentityAppRoleAssignment": {"principalId": data["backendPrincipalId"], "resourceId": gateway_service_principal, "appRoleId": GATEWAY_ROLE_ID},
        "backendApplicationPatch": {"identifierUris": [f"api://{data['backendAudience']}"], "api": {"requestedAccessTokenVersion": 2, "oauth2PermissionScopes": [{
            "id": API_SCOPE_ID, "value": "FoodAnalysis.Access", "type": "Admin", "isEnabled": True,
            "adminConsentDisplayName": "Analyze private nutrition input", "adminConsentDescription": "Allow the two approved participants to submit nutrition input."}]}},
        "nativeApplicationPatch": {"isFallbackPublicClient": True, "publicClient": {"redirectUris": ["msauth.com.benedikt.Trainingsplan://auth"]},
            "requiredResourceAccess": [{"resourceAppId": data["backendAudience"], "resourceAccess": [{"id": API_SCOPE_ID, "type": "Scope"}]}]},
    }


def backend_package(destination):
    backend = ROOT / "backend"
    with zipfile.ZipFile(destination, "x", compression=zipfile.ZIP_DEFLATED) as archive:
        for source in sorted(backend.glob("*.py")) + sorted((backend / "api").glob("*.py")):
            archive.write(source, source.relative_to(backend).as_posix())
        archive.write(backend / "host.json", "host.json")
        requirements = (backend / "requirements.txt").read_text() + "\nazure-identity==1.25.3\n"
        archive.writestr("requirements.txt", requirements)


def acceptance_manifest():
    sys.path.insert(0, str(ROOT / "ai-gateway"))
    from app.schemas.food_analysis import FoodAnalysisRequest

    fixtures = ROOT / "ai-gateway/tests/fixtures"
    baseline = json.loads((fixtures / "gpt54-mini-benchmark.v1.json").read_text())
    selected = ("T2", "T5", "T4", "T1", "L1", "L2", "P1", "R1", "R4", "P5")
    cases = []
    for identifier in selected:
        case = next(case for case in baseline["cases"] if case["id"] == identifier)
        payload = dict(case.get("payload", {}))
        if "asset" in case:
            asset = fixtures / case["asset"]["file"]
            content = asset.read_bytes()
            if hashlib.sha256(content).hexdigest() != case["asset"]["sha256"]:
                raise ValueError("Acceptance asset does not match its reviewed public fixture.")
            payload["image"] = {"media_type": "image/png" if asset.suffix == ".png" else "image/jpeg",
                                "data_base64": base64.b64encode(content).decode("ascii")}
        if "refinement" in case:
            payload["refinement"] = {**case["refinement"], "current_estimate": baseline["baseline"]}
        normalized = FoodAnalysisRequest.model_validate(payload).model_dump(mode="json")
        serialized = json.dumps(normalized, sort_keys=True, separators=(",", ":"), ensure_ascii=True, allow_nan=False).encode()
        cases.append({"id": identifier, "payload": payload, "payload_sha256": hashlib.sha256(serialized).hexdigest(),
                      "criterion": case["criterion"], "expected": case.get("expected")})
    return {"version": "private-pilot-acceptance-v1", "max_attempts": 10, "max_reserved_usd": "2.343",
            "provenance": "Existing fabricated text/labels and reviewed CC0 images P1/P5 only. No benchmark ledger or allowance reused.",
            "cases": cases}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=["ios", "entra", "backend-package", "acceptance-manifest"])
    parser.add_argument("--outputs", type=Path)
    parser.add_argument("--gateway-service-principal")
    parser.add_argument("--destination", type=Path, required=True)
    args = parser.parse_args()
    if args.mode == "backend-package":
        backend_package(args.destination)
    elif args.mode == "acceptance-manifest":
        with args.destination.open("x") as target:
            json.dump(acceptance_manifest(), target, indent=2)
    else:
        data = outputs(json.loads(args.outputs.read_text()))
        content = ios_config(data) if args.mode == "ios" else json.dumps(entra_requests(data, args.gateway_service_principal), indent=2) + "\n"
        with args.destination.open("x") as target:
            target.write(content)


if __name__ == "__main__":
    main()