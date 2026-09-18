from pathlib import Path

import asyncio
import time
from types import SimpleNamespace

import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import rsa

from app.workload_auth import ApiIngress, MAX_BODY_BYTES, WorkloadVerifier

TENANT = "00000000-0000-4000-8000-000000000001"
AUDIENCE = "00000000-0000-4000-8000-000000000002"
PRINCIPAL = "00000000-0000-4000-8000-000000000003"
CLIENT = "00000000-0000-4000-8000-000000000004"


@pytest.mark.parametrize("mutation", [None, "tid", "oid", "azp", "aud", "iss", "exp", "nbf", "roles", "user", "signature", "algorithm"])
def test_workload_requires_exact_signed_app_identity(mutation):
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    keys = SimpleNamespace(get_signing_key_from_jwt=lambda token: SimpleNamespace(key=key.public_key()))
    verifier = WorkloadVerifier(TENANT, AUDIENCE, PRINCIPAL, CLIENT, keys)
    now = int(time.time())
    claims = {"tid": TENANT, "oid": PRINCIPAL, "azp": CLIENT, "aud": AUDIENCE,
              "iss": verifier.issuer, "exp": now + 300, "nbf": now - 1, "iat": now - 1,
              "roles": ["Gateway.Invoke"], "ver": "2.0", "idtyp": "app"}
    if mutation in {"tid", "oid", "azp", "aud", "iss"}:
        claims[mutation] = "foreign"
    elif mutation == "exp":
        claims["exp"] = now - 1
    elif mutation == "nbf":
        claims["nbf"] = now + 300
    elif mutation == "roles":
        claims["roles"] = ["Other.Role"]
    elif mutation == "user":
        claims.update(scp="Gateway.Invoke", idtyp="user")
    signing_key = rsa.generate_private_key(public_exponent=65537, key_size=2048) if mutation == "signature" else key
    token = jwt.encode(claims, "synthetic-key-not-for-use-000000000" if mutation == "algorithm" else signing_key,
                       algorithm="HS256" if mutation == "algorithm" else "RS256", headers={"kid": "test"})
    if mutation is None:
        verifier.verify("Bearer " + token)
    else:
        with pytest.raises((ValueError, jwt.PyJWTError)):
            verifier.verify("Bearer " + token)


@pytest.mark.parametrize("mode,expected", [("valid", 204), ("foreign", 403), ("oversized", 413), ("chunked", 413), ("disabled", 503)])
def test_ingress_rejects_before_dispatch_and_bounds_body(monkeypatch, mode, expected):
    monkeypatch.setenv("GATEWAY_SERVICE_TOKEN", "synthetic")
    reads, dispatches, sent = [], [], []

    def active():
        if mode == "disabled":
            raise ValueError()

    def verify(token):
        if mode == "foreign":
            raise ValueError("private-marker")

    async def app(scope, receive, send):
        dispatches.append(await receive())
        await send({"type": "http.response.start", "status": 204, "headers": []})

    async def receive():
        reads.append(True)
        return {"type": "http.request", "body": b"x" * (MAX_BODY_BYTES + 1) if mode == "chunked" else b"{}"}

    async def send(message):
        sent.append(message)

    scope = {"type": "http", "method": "POST", "path": "/v1/food-analysis", "headers": [
        (b"content-type", b"application/json"), (b"x-service-token", b"synthetic"),
        (b"content-length", str(MAX_BODY_BYTES + 1 if mode == "oversized" else 2).encode()),
    ]}
    asyncio.run(ApiIngress(app, SimpleNamespace(verify=verify), active, None)(scope, receive, send))
    assert sent[0]["status"] == expected
    assert bool(dispatches) == (mode == "valid")
    assert bool(reads) == (mode in {"valid", "chunked"})
    assert "private-marker" not in str(sent)


def test_api_entrypoint_disabled_without_signed_release(monkeypatch):
    from starlette.testclient import TestClient
    from app.api_runtime import create_api_app

    monkeypatch.delenv("AI_API_ONLY_ENABLED", raising=False)
    with TestClient(create_api_app()) as client:
        assert client.get("/healthz").status_code == 200
        assert client.get("/readyz").status_code == 503
        assert client.post("/v1/food-analysis", json={}).status_code == 503
        assert client.get("/docs").status_code == 404


@pytest.fixture
def release_config(monkeypatch):
    import hashlib
    import hmac
    import json
    from app.config import Settings
    from app.pilot import canonical
    from app import pilot_release
    from app.providers.pricing import GPT_54_MINI
    from tests.test_pilot import profile_coordinator

    now = int(time.time())
    policy = profile_coordinator(deployment_verified_until=now + 3600).policy.model_dump(mode="json")
    values = {
        "APP_ENV": "production", "AI_PROVIDER": "azure_openai", "AI_API_ONLY_ENABLED": "true", "AI_PILOT_ENABLED": "true",
        "AI_PILOT_TENANT_ID": TENANT, "GATEWAY_WORKLOAD_AUDIENCE": AUDIENCE,
        "GATEWAY_BACKEND_PRINCIPAL_ID": PRINCIPAL, "GATEWAY_BACKEND_CLIENT_ID": CLIENT,
        "AI_PILOT_GATEWAY_CLIENT_ID": AUDIENCE, "AI_PILOT_RESOURCE_GROUP": "pft-pilot-synthetic",
        "AI_PILOT_TABLE_NAME": "PilotLedger", "AI_PILOT_TABLE_ENDPOINT": "https://synthetic.table.core.windows.net",
        "AI_PILOT_POLICY_JSON": json.dumps(policy), "API_ONLY_IMAGE_DIGEST": "sha256:" + "a" * 64,
        "AI_PILOT_ALL_IN_MONTHLY_EUR": "25", "AI_PILOT_ALLOWLIST_JSON": json.dumps([
            {"tid": TENANT, "oid": PRINCIPAL}, {"tid": TENANT, "oid": CLIENT}]),
        "GATEWAY_SERVICE_TOKEN": "service" * 8, "AI_PILOT_SIGNING_KEY": "signing" * 8,
        "AI_PILOT_FINGERPRINT_KEY": "fingerprint" * 8, "AI_PILOT_RELEASE_KEY": "release" * 8,
    }
    for name, value in values.items():
        monkeypatch.setenv(name, value)
    for name in ("AZURE_OPENAI_API_KEY", "COPILOT_GITHUB_TOKEN", "GH_TOKEN", "GITHUB_TOKEN"):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setattr(pilot_release, "is_api_artifact", lambda: True)
    settings = Settings(AI_PROVIDER_TIMEOUT_SECONDS=90, AZURE_OPENAI_ENDPOINT="https://synthetic.openai.azure.com",
                        AZURE_OPENAI_MODEL_ROUTES_JSON=json.dumps({"food_text_v1": "deployment-test", "food_image_v1": "deployment-test"}),
                        AZURE_OPENAI_PROFILES_JSON=json.dumps({"deployment-test": GPT_54_MINI.identifier}),
                        AZURE_OPENAI_PRICES_JSON=profile_coordinator().prices.model_dump_json())
    approval = {"configuration_sha256": pilot_release.configuration_digest(settings), "issued_at": now, "expires_at": now + 1800,
                "evidence": {name: "b" * 64 for name in pilot_release.EVIDENCE}, "approved": True}
    monkeypatch.setenv("AI_PILOT_RELEASE_JSON", json.dumps(approval))
    monkeypatch.setenv("AI_PILOT_RELEASE_SIGNATURE", hmac.new(values["AI_PILOT_RELEASE_KEY"].encode(), canonical(approval), hashlib.sha256).hexdigest())
    return settings


@pytest.mark.parametrize("mutation", [None, "signature", "expired", "budget", "benchmark", "image", "identity", "disabled", "legacy", "credential", "evidence"])
def test_release_requires_bound_owner_approval(monkeypatch, release_config, mutation):
    import json
    import os
    from app import pilot_release
    from app.pilot import PilotError

    settings = release_config
    if mutation == "signature":
        monkeypatch.setenv("AI_PILOT_RELEASE_SIGNATURE", "0" * 64)
    elif mutation == "expired":
        approval = json.loads(os.environ["AI_PILOT_RELEASE_JSON"])
        approval["expires_at"] = 1
        monkeypatch.setenv("AI_PILOT_RELEASE_JSON", json.dumps(approval))
    elif mutation in {"budget", "benchmark"}:
        policy = json.loads(os.environ["AI_PILOT_POLICY_JSON"])
        if mutation == "budget":
            policy["total"]["monthly_usd"] = "0"
        else:
            policy["benchmark"] = {"run_id": "old-benchmark"}
        monkeypatch.setenv("AI_PILOT_POLICY_JSON", json.dumps(policy))
    elif mutation == "image":
        monkeypatch.setenv("API_ONLY_IMAGE_DIGEST", "sha256:" + "c" * 64)
    elif mutation == "identity":
        monkeypatch.setenv("GATEWAY_BACKEND_PRINCIPAL_ID", AUDIENCE)
    elif mutation == "disabled":
        monkeypatch.setenv("AI_API_ONLY_ENABLED", "false")
    elif mutation == "legacy":
        monkeypatch.setattr(pilot_release, "is_api_artifact", lambda: False)
    elif mutation == "credential":
        monkeypatch.setenv("GITHUB_TOKEN", "synthetic-not-for-use")
    elif mutation == "evidence":
        monkeypatch.delenv("AI_PILOT_RELEASE_JSON")
    if mutation is None:
        settings.validate()
        assert pilot_release.validate_release(settings)["approved"]
    else:
        with pytest.raises(PilotError):
            pilot_release.validate_release(settings)


@pytest.mark.parametrize("missing", [None, "identity", "deployment", "table_rbac", "ledger", "budget", "privacy"])
def test_approval_tool_requires_all_fresh_evidence(release_config, missing):
    from app import pilot_release
    from app.pilot import PilotError

    evidence = {name: {"configuration_sha256": pilot_release.configuration_digest(release_config),
                       "checked_at": int(time.time()), "checks": {check: True for check in checks}}
                for name, checks in pilot_release.CHECKS.items()}
    if missing:
        evidence[missing]["checks"].pop(next(iter(evidence[missing]["checks"])))
        with pytest.raises(PilotError):
            pilot_release.prepare_approval(release_config, evidence)
    else:
        result = pilot_release.prepare_approval(release_config, evidence)
        assert result["approval"]["approved"] is True
        assert len(result["signature"]) == 64


@pytest.mark.parametrize("mutation", [None, "missing", "not_denied", "legacy_network"])
def test_variant_b_approval_requires_anonymous_access_denial(release_config, mutation):
    from app import pilot_release
    from app.pilot import PilotError

    evidence = {name: {"configuration_sha256": pilot_release.configuration_digest(release_config),
                       "checked_at": int(time.time()), "checks": {check: True for check in checks}}
                for name, checks in pilot_release.CHECKS.items()}
    checks = {"table_scoped_role": True, "no_shared_keys": True,
              "anonymous_access_denied": True, "foreign_identity_denied": True}
    evidence["table_rbac"]["checks"] = checks
    if mutation in {"missing", "legacy_network"}:
        del checks["anonymous_access_denied"]
    if mutation == "not_denied":
        checks["anonymous_access_denied"] = False
    if mutation == "legacy_network":
        checks["external_network_denied"] = True
    if mutation:
        with pytest.raises(PilotError):
            pilot_release.prepare_approval(release_config, evidence)
    else:
        signed = pilot_release.prepare_approval(release_config, evidence)
        assert pilot_release.verify_approval(release_config, signed)["approved"] is True


@pytest.mark.parametrize("mutation", [None, "signature", "config", "owner_expired", "checks", "stale"])
def test_renewal_preserves_owner_scope_and_ledger(monkeypatch, release_config, mutation):
    import json
    import os
    from app import pilot_release
    from app.pilot import PilotError
    from app.pilot_access import build_coordinator
    from tests.test_pilot import MemoryCAS

    now = int(time.time())
    policy = json.loads(os.environ["AI_PILOT_POLICY_JSON"])
    policy["deployment_verified_until"] = now + 30 * 86400
    monkeypatch.setenv("AI_PILOT_POLICY_JSON", json.dumps(policy))
    evidence = {name: {"configuration_sha256": pilot_release.configuration_digest(release_config),
                      "checked_at": now, "checks": {check: True for check in checks}}
                for name, checks in pilot_release.CHECKS.items()}
    first = pilot_release.prepare_approval(release_config, evidence)
    store = MemoryCAS()
    control = build_coordinator(store, settings=release_config)
    store.rows["ledger"] = (control.initial_ledger(), "1")
    monkeypatch.setenv("AI_PILOT_RELEASE_JSON", json.dumps(first["approval"]))
    monkeypatch.setenv("AI_PILOT_RELEASE_SIGNATURE", first["signature"])
    later = now + 86401
    monkeypatch.setattr(pilot_release.time, "time", lambda: later)
    with pytest.raises(PilotError):
        pilot_release.validate_release(release_config)
    fresh = {name: {**evidence[name], "checked_at": later} for name in pilot_release.RENEWABLE}
    if mutation == "signature":
        first["signature"] = "0" * 64
    elif mutation == "config":
        monkeypatch.setenv("AI_PILOT_ALL_IN_MONTHLY_EUR", "99")
    elif mutation == "owner_expired":
        later = policy["deployment_verified_until"] + 1
    elif mutation == "checks":
        fresh["identity"]["checks"] = {}
    elif mutation == "stale":
        fresh["identity"]["checked_at"] = now
    if mutation:
        with pytest.raises(PilotError):
            pilot_release.prepare_approval(release_config, fresh, previous=first)
        return
    renewed = pilot_release.prepare_approval(release_config, fresh, previous=first)
    assert renewed["approval"]["evidence"]["budget"] == first["approval"]["evidence"]["budget"]
    assert renewed["approval"]["evidence"]["privacy"] == first["approval"]["evidence"]["privacy"]
    assert renewed["approval"]["expires_at"] == later + 86400
    assert build_coordinator(store, settings=release_config).policy_id == control.policy_id
    assert store.rows["ledger"] == (control.initial_ledger(), "1")
    monkeypatch.setenv("AI_PILOT_RELEASE_JSON", json.dumps(renewed["approval"]))
    monkeypatch.setenv("AI_PILOT_RELEASE_SIGNATURE", renewed["signature"])
    assert pilot_release.validate_release(release_config)["approved"]
    monkeypatch.setenv("AI_API_ONLY_ENABLED", "false")
    with pytest.raises(PilotError):
        pilot_release.validate_release(release_config)


def test_readiness_requires_workload_authentication(monkeypatch):
    from starlette.applications import Starlette
    from starlette.testclient import TestClient

    monkeypatch.setenv("GATEWAY_SERVICE_TOKEN", "synthetic")
    reads = []

    async def ready():
        reads.append(True)

    def verify(token):
        if token != "Bearer synthetic":
            raise ValueError()

    with TestClient(ApiIngress(Starlette(), SimpleNamespace(verify=verify), lambda: None, ready)) as client:
        assert client.get("/readyz").status_code == 403
        assert not reads
        assert client.get("/readyz", headers={"Authorization": "Bearer synthetic", "X-Service-Token": "synthetic"}).status_code == 200
        assert len(reads) == 1


def test_api_artifact_cannot_bypass_ingress_via_legacy_entrypoint(monkeypatch, release_config):
    from starlette.requests import Request
    from app.security import require_authenticated_caller
    from app.errors import AuthenticationRequiredError

    monkeypatch.setattr("app.security.get_settings", lambda: release_config)
    scope = {"type": "http", "headers": [(b"x-service-token", release_config.gateway_service_token.encode())]}
    with pytest.raises(AuthenticationRequiredError):
        asyncio.run(require_authenticated_caller(Request(scope)))
    scope["api_only_workload_verified"] = True
    asyncio.run(require_authenticated_caller(Request(scope)))


@pytest.mark.parametrize("mutation", [None, "body", "operation", "hmac", "timestamp", "workload", "duplicate", "anonymous", "missing_token", "missing_service"])
def test_full_ingress_binds_workload_and_signed_request(monkeypatch, release_config, mutation):
    import base64
    import hashlib
    import hmac
    import json
    import os
    from starlette.testclient import TestClient
    from app.main import create_app
    from app.dependencies import get_food_analysis_use_case
    from app.pilot import canonical
    from app.pilot_release import validate_release
    from app.schemas.food_analysis import FoodAnalysisResponse
    from tests.test_openai_api import _food_data
    from tests.test_pilot import operation

    calls = []

    class UseCase:
        async def execute(self, request):
            calls.append(request)
            return FoodAnalysisResponse(estimate=_food_data())

    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    keys = SimpleNamespace(get_signing_key_from_jwt=lambda token: SimpleNamespace(key=key.public_key()))
    verifier = WorkloadVerifier(TENANT, AUDIENCE, PRINCIPAL, CLIENT, keys)
    now = int(time.time())
    token = jwt.encode({"tid": TENANT, "oid": AUDIENCE if mutation == "workload" else PRINCIPAL,
        "azp": CLIENT, "aud": AUDIENCE, "iss": verifier.issuer, "exp": now + 300, "nbf": now - 1,
        "iat": now - 1, "roles": ["Gateway.Invoke"], "ver": "2.0", "idtyp": "app"}, key,
        algorithm="RS256", headers={"kid": "synthetic"})
    payload = {"food_description": "synthetic"}
    identifier = operation()
    envelope = {"tid": TENANT, "oid": PRINCIPAL, "operation": identifier,
                "issued": now - 300 if mutation == "timestamp" else now,
                "body": hashlib.sha256(canonical(payload)).hexdigest(), "aud": "fitness-gateway-pilot-v1"}
    encoded = base64.urlsafe_b64encode(canonical(envelope)).decode()
    signature = hmac.new(os.environ["AI_PILOT_SIGNING_KEY"].encode(), encoded.encode(), hashlib.sha256).hexdigest()
    headers = [("Authorization", "Bearer " + token), ("X-Service-Token", release_config.gateway_service_token),
               ("X-Pilot-Authorization", encoded + "." + ("0" * 64 if mutation == "hmac" else signature)),
               ("X-Operation-Id", operation(sequence=2) if mutation == "operation" else identifier)]
    if mutation == "body":
        payload["food_description"] = "changed"
    if mutation == "duplicate":
        headers.append(("X-Operation-Id", identifier))
    if mutation == "anonymous":
        headers = []
    elif mutation == "missing_token":
        headers = [(name, value) for name, value in headers if name != "Authorization"]
    elif mutation == "missing_service":
        headers = [(name, value) for name, value in headers if name != "X-Service-Token"]
    monkeypatch.setattr("app.security.get_settings", lambda: release_config)
    inner = create_app()
    inner.dependency_overrides[get_food_analysis_use_case] = UseCase
    with TestClient(ApiIngress(inner, verifier, lambda: validate_release(release_config), None)) as client:
        response = client.post("/v1/food-analysis", json=payload, headers=headers)
    assert response.status_code == (200 if mutation is None else 400 if mutation == "duplicate" else 403)
    assert len(calls) == (1 if mutation is None else 0)


def test_ingress_diagnostics_are_content_free_and_bounded(monkeypatch, caplog):
    import logging
    from starlette.applications import Starlette
    from starlette.testclient import TestClient

    monkeypatch.setattr("app.workload_auth.logger", logging.getLogger("synthetic.pilot.events"))
    caplog.set_level(logging.INFO, logger="synthetic.pilot.events")
    app = ApiIngress(Starlette(), None, lambda: None, None)
    with TestClient(app) as client:
        for _ in range(65):
            response = client.post("/private-food-marker?secret=private-query-marker",
                                   headers={"X-Request-Id": "private-id-marker"}, content="private-body-marker")
            assert response.status_code == 404
    records = [record.message for record in caplog.records if record.name == "synthetic.pilot.events"]
    assert len(records) == 60
    assert all("boundary=route status=404" in record for record in records)
    assert not any("private-" in record for record in records)
    assert app.log_suppressed == 5


def test_api_artifact_excludes_legacy_runtime():
    root = Path(__file__).resolve().parents[1]
    docker = (root / "Dockerfile.api-only").read_text()
    requirements = (root / "requirements-api.txt").read_text()
    assert "copilot" not in docker.lower()
    assert "copilot" not in requirements.lower()
    assert "COPY app ./app" not in docker
    assert "app.api_runtime:app" in docker
    assert "--no-access-log" in docker
    ignored = (root / "Dockerfile.api-only.dockerignore").read_text().splitlines()
    assert ignored[0] == "**"
    assert "!requirements-api.txt" in ignored
    assert "app/benchmark*.py" in ignored
    assert not any("github_copilot" in line or "fake.py" in line for line in ignored)
    assert "copilot download-runtime" in (root / "Dockerfile").read_text()
    sources = [source for line in docker.splitlines() if line.startswith("COPY app/")
               for source in line.split()[1:-1]]
    assert all((root / source).exists() for source in sources)


def test_api_artifact_imports_without_legacy_modules(tmp_path):
    import os
    import shutil
    import subprocess
    import sys

    root = Path(__file__).resolve().parents[1]
    for line in (root / "Dockerfile.api-only").read_text().splitlines():
        if not line.startswith("COPY app/"):
            continue
        parts = line.split()
        destination = tmp_path / parts[-1]
        for source in parts[1:-1]:
            source_path = root / source
            if source_path.is_dir():
                shutil.copytree(source_path, destination, ignore=shutil.ignore_patterns("__pycache__"))
            else:
                destination.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(source_path, destination / source_path.name)
    (tmp_path / "app/.api-only").touch()
    assert not (tmp_path / "app/providers/github_copilot.py").exists()
    assert not (tmp_path / "app/providers/fake.py").exists()
    env = {**os.environ, "PYTHONDONTWRITEBYTECODE": "1", "AI_API_ONLY_ENABLED": "false", "APP_ENV": "production", "PYTHONPATH": str(tmp_path)}
    result = subprocess.run([sys.executable, "-B", "-c", "import app.api_runtime; import sys; assert 'copilot' not in sys.modules"],
                            cwd=tmp_path, env=env, capture_output=True, timeout=10)
    assert result.returncode == 0, result.stderr.decode()


def test_api_production_uses_one_permitted_mock_sdk_call(monkeypatch, release_config):
    import httpx2
    from app.providers.openai_api import AzureOpenAIProvider
    from app.pilot_access import build_coordinator
    from app.pilot_release import validate_release
    from app.schemas.food_analysis import FoodAnalysisRequest
    from app.use_cases.food_analysis import FoodAnalysisUseCase
    from tests.test_openai_api import _profile_completion, _food_data
    from tests.test_pilot import MemoryCAS, operation

    calls, tokens = [], []
    monkeypatch.setattr("app.config.get_settings", lambda: release_config)
    store = MemoryCAS()
    control = build_coordinator(store, settings=release_config)
    store.rows["ledger"] = (control.initial_ledger(), "1")

    async def token():
        tokens.append(True)
        return "synthetic-token"

    def handler(request):
        calls.append(request)
        return httpx2.Response(200, json=_profile_completion({**_food_data(), "declared_nutrition": None}))

    async def run():
        provider = AzureOpenAIProvider(endpoint=release_config.azure_openai_endpoint,
            token_provider=token, dispatch_guard=lambda: validate_release(release_config),
            model_routes=release_config.azure_openai_model_routes(), max_output_tokens=2000,
            prices=release_config.azure_openai_prices(), profile_bindings=release_config.azure_openai_profiles(),
            transport=httpx2.MockTransport(handler))
        use_case = FoodAnalysisUseCase(provider, 90, "food_text_v1", max_output_tokens=2000)
        async def dispatch(generation):
            return await control.generate(provider, generation, (TENANT, PRINCIPAL), operation(), "synthetic")
        monkeypatch.setattr(use_case, "_generate_with_timeout", dispatch)
        try:
            result = await use_case.execute(FoodAnalysisRequest(food_description="synthetic"))
            assert result.estimate.food_name
            assert len(calls) == len(tokens) == 1
            assert len([key for key in store.rows if key.startswith("op-")]) == 1
        finally:
            await provider.aclose()
    asyncio.run(run())


def test_initialize_ledger_never_replaces_existing_state(monkeypatch, release_config):
    from app.pilot_access import build_coordinator
    from app.pilot_release import initialize_ledger
    from app.pilot import PilotError
    from tests.test_pilot import MemoryCAS

    monkeypatch.setenv("AI_API_ONLY_ENABLED", "false")
    store = MemoryCAS()
    closed = []

    async def close():
        closed.append(True)

    store.close = close
    control = build_coordinator(store, settings=release_config)
    monkeypatch.setattr("app.pilot_access.build_coordinator", lambda **kwargs: control)
    asyncio.run(initialize_ledger(release_config))
    first = store.rows["ledger"]
    with pytest.raises(PilotError):
        asyncio.run(initialize_ledger(release_config))
    assert store.rows["ledger"] == first
    assert len(closed) == 2


def test_pilot_template_is_separate_bounded_and_inactive():
    import json

    root = Path(__file__).resolve().parents[2]
    template = json.loads((root / "infra/pilot/main.json").read_text())
    resources = template["resources"]
    assert template["parameters"]["enableAI"]["defaultValue"] is False
    assert template["parameters"]["deployGateway"]["defaultValue"] is False
    assert "defaultValue" not in template["parameters"]["policy"]
    app = next(resource for resource in resources if resource["type"] == "Microsoft.App/containerApps")
    assert app["properties"]["template"]["scale"]["minReplicas"] == 0
    assert app["properties"]["template"]["scale"]["maxReplicas"] == 1
    assert app["properties"]["template"]["containers"][0]["resources"] == {"cpu": "[json('0.25')]", "memory": "0.5Gi"}
    backend = next(resource for resource in resources if resource["type"] == "Microsoft.Web/sites")
    scale = backend["properties"]["functionAppConfig"]["scaleAndConcurrency"]
    assert scale == {"maximumInstanceCount": 1, "instanceMemoryMB": 512,
                     "http": {"perInstanceConcurrency": 2}, "alwaysReady": []}
    assert "@" in app["properties"]["template"]["containers"][0]["image"]
    storage = next(resource for resource in resources if resource["type"] == "Microsoft.Storage/storageAccounts")
    assert storage["properties"]["allowSharedKeyAccess"] is False
    assert storage["properties"]["allowBlobPublicAccess"] is False
    assert template["outputs"]["tableName"]["value"] == "PilotLedger"
    assert not any("benchmark" in str(resource).lower() for resource in resources)
    model = next(resource for resource in resources if resource["type"] == "Microsoft.CognitiveServices/accounts/deployments")
    assert model["properties"]["versionUpgradeOption"] == "NoAutoUpgrade"
    assert model["sku"]["name"] == "DataZoneStandard"
    assert len([resource for resource in resources if resource["type"] == "Microsoft.Consumption/budgets"]) == 1


def test_variant_b_uses_managed_network_without_weakening_identity_controls():
    import json

    root = Path(__file__).resolve().parents[2]
    template = json.loads((root / "infra/pilot/main.json").read_text())
    resources = template["resources"]
    assert not any(resource["type"].startswith("Microsoft.Network/") for resource in resources)
    assert not {"vnet", "gatewaySubnet", "backendSubnet"} & template["variables"].keys()
    assert "Subnet" not in json.dumps(template)
    environment = next(resource for resource in resources if resource["type"] == "Microsoft.App/managedEnvironments")
    assert "vnetConfiguration" not in environment["properties"]
    assert "infrastructureResourceGroup" not in environment["properties"]
    assert environment["properties"]["workloadProfiles"] == [{"name": "Consumption", "workloadProfileType": "Consumption"}]
    for resource_type in ("Microsoft.Storage/storageAccounts", "Microsoft.KeyVault/vaults", "Microsoft.CognitiveServices/accounts"):
        properties = next(resource["properties"] for resource in resources if resource["type"] == resource_type)
        assert properties["publicNetworkAccess"] == "Enabled"
        assert properties["networkAcls"] == {"defaultAction": "Allow", "bypass": "None", "ipRules": [], "virtualNetworkRules": []}
    vault = next(resource for resource in resources if resource["type"] == "Microsoft.KeyVault/vaults")
    assert vault["properties"]["enableRbacAuthorization"] is True
    model = next(resource for resource in resources if resource["type"] == "Microsoft.CognitiveServices/accounts")
    assert model["properties"]["disableLocalAuth"] is True
    app = next(resource for resource in resources if resource["type"] == "Microsoft.App/containerApps")
    ingress = app["properties"]["configuration"]["ingress"]
    assert ingress["external"] is True and ingress["allowInsecure"] is False
    env = {entry["name"]: entry for entry in app["properties"]["template"]["containers"][0]["env"]}
    assert env["GATEWAY_BACKEND_PRINCIPAL_ID"]["value"] == "[reference(variables('backendIdentityId'), '2023-01-31').principalId]"
    assert env["GATEWAY_BACKEND_CLIENT_ID"]["value"] == "[reference(variables('backendIdentityId'), '2023-01-31').clientId]"
    assert env["GATEWAY_WORKLOAD_AUDIENCE"]["value"] == "[parameters('gatewayAudience')]"
    assert env["AI_PILOT_SIGNING_KEY"]["secretRef"] == "signing-key"
    backend = next(resource for resource in resources if resource["type"] == "Microsoft.Web/sites")
    settings = {entry["name"]: entry["value"] for entry in backend["properties"]["siteConfig"]["appSettings"]}
    assert settings["AI_GATEWAY_BASE_URL"] == "[concat('https://', reference(resourceId('Microsoft.App/containerApps', variables('gateway')), '2024-03-01').configuration.ingress.fqdn)]"
    assert settings["GATEWAY_BACKEND_CLIENT_ID"] == env["GATEWAY_BACKEND_CLIENT_ID"]["value"]
    assert settings["FUNCTIONS_REQUEST_BODY_SIZE_LIMIT"] == "3211264"
    auth = next(resource for resource in resources if resource["type"] == "Microsoft.Web/sites/config")
    assert auth["properties"]["globalValidation"] == {"requireAuthentication": True, "unauthenticatedClientAction": "Return401", "excludedPaths": ["/api/health"]}
    roles = [resource for resource in resources if resource["type"] == "Microsoft.Authorization/roleAssignments"]
    assert len(roles) == 5
    table_role = next(resource for resource in roles if "pilot-table-gateway" in resource["name"])
    assert table_role["scope"] == "[resourceId('Microsoft.Storage/storageAccounts/tableServices/tables', variables('storage'), 'default', 'PilotLedger')]"
    assert table_role["properties"]["principalId"] == "[reference(variables('gatewayIdentityId'), '2023-01-31').principalId]"
    assert table_role["properties"]["roleDefinitionId"] == "[subscriptionResourceId('Microsoft.Authorization/roleDefinitions', '0a9a7e1f-b9d0-4cc4-a60d-0319b160aaa3')]"
    model_role = next(resource for resource in roles if "pilot-model-gateway" in resource["name"])
    assert model_role["scope"] == "[resourceId('Microsoft.CognitiveServices/accounts', variables('model'))]"
    assert model_role["properties"]["principalId"] == table_role["properties"]["principalId"]
    assert model_role["properties"]["roleDefinitionId"] == "[subscriptionResourceId('Microsoft.Authorization/roleDefinitions', '5e0bd9bd-7b93-4f28-af87-19fc36ad61bd')]"
    budget = json.loads((root / "infra/pilot/budget.json").read_text())
    assert budget["parameters"]["infrastructureResourceGroup"]["defaultValue"] == ""
    assert budget["resources"][0]["properties"]["amount"] == "[parameters('monthlyAmountEUR')]"


def load_local_module(relative):
    import importlib.util

    root = Path(__file__).resolve().parents[2]
    spec = importlib.util.spec_from_file_location("offline_helper", root / relative)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.mark.parametrize("mutation", [None, "url", "tenant", "scope", "team", "bundle", "build", "missing", "legacy"])
def test_pilot_ios_build_requires_complete_separate_configuration(mutation):
    validator = load_local_module("ios/Config/validate_pilot.py")
    values = {"PILOT_BUILD": "YES", "CONFIGURATION": "Release", "PRODUCT_BUNDLE_IDENTIFIER": "com.benedikt.Trainingsplan",
              "DEVELOPMENT_TEAM": "2SF7PV3WCD", "CURRENT_PROJECT_VERSION": "5", "API_BASE_URL": "https://pft-pilot-synthetic-api.azurewebsites.net/api",
              "ENTRA_TENANT_ID": TENANT, "ENTRA_CLIENT_ID": CLIENT, "ENTRA_API_SCOPE": f"api://{AUDIENCE}/FoodAnalysis.Access",
              "ENTRA_REDIRECT_URI": "msauth.com.benedikt.Trainingsplan://auth"}
    for name in ("API_BASE_URL", "ENTRA_TENANT_ID", "ENTRA_CLIENT_ID", "ENTRA_API_SCOPE"):
        values["PILOT_" + name] = values[name]
    if mutation:
        field = {"url": "API_BASE_URL", "tenant": "ENTRA_TENANT_ID", "scope": "ENTRA_API_SCOPE", "team": "DEVELOPMENT_TEAM",
                 "bundle": "PRODUCT_BUNDLE_IDENTIFIER", "build": "CURRENT_PROJECT_VERSION", "missing": "PILOT_API_BASE_URL", "legacy": "PILOT_BUILD"}[mutation]
        values[field] = "NO" if mutation == "legacy" else ""
    if mutation in {None, "legacy"}:
        validator.validate(values)
    else:
        with pytest.raises(ValueError):
            validator.validate(values)


def test_offline_packaging_excludes_local_files_and_preserves_public_outputs(tmp_path):
    import zipfile

    prepare = load_local_module("infra/pilot/prepare.py")
    raw = {name: {"value": value} for name, value in {
        "apiBaseURL": "https://pft-pilot-synthetic-api.azurewebsites.net/api", "tenantId": TENANT,
        "nativeClientId": CLIENT, "backendAudience": AUDIENCE, "gatewayAudience": AUDIENCE,
        "backendPrincipalId": PRINCIPAL, "backendClientId": CLIENT, "resourceGroup": "pft-pilot-synthetic",
    }.items()}
    data = prepare.outputs(raw)
    assert "https:/$()/pft-pilot-synthetic-api.azurewebsites.net/api" in prepare.ios_config(data)
    requests = prepare.entra_requests(data, PRINCIPAL)
    assert requests["backendIdentityAppRoleAssignment"]["principalId"] == PRINCIPAL
    assert requests["gatewayApplicationPatch"]["api"]["requestedAccessTokenVersion"] == 2
    destination = tmp_path / "backend.zip"
    prepare.backend_package(destination)
    with zipfile.ZipFile(destination) as archive:
        assert "workload_identity.py" in archive.namelist()
        assert not any(name.startswith(("tests/", ".")) or "local.settings" in name for name in archive.namelist())
        assert b"azure-identity==1.25.3" in archive.read("requirements.txt")