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
    monkeypatch.setattr("app.pilot_access.verify", lambda headers, payload: ((TENANT, PRINCIPAL), "synthetic"))
    monkeypatch.setattr("app.pilot_access.configured_allowlist", lambda: {(TENANT, PRINCIPAL)})
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
    assert bool(reads) == (mode in {"valid", "chunked", "disabled"})
    assert "private-marker" not in str(sent)


def test_api_entrypoint_disabled_without_signed_release(monkeypatch):
    from starlette.testclient import TestClient
    from app.api_runtime import create_api_app

    monkeypatch.delenv("AI_API_ONLY_ENABLED", raising=False)
    with TestClient(create_api_app()) as client:
        assert client.get("/healthz").status_code == 200
        assert client.get("/readyz").status_code == 403
        assert client.post("/v1/food-analysis", json={}).status_code == 403
        assert client.get("/docs").status_code == 404


@pytest.mark.parametrize("route,method", [("/readyz", "GET"), ("/v1/food-analysis", "POST")])
def test_disabled_release_authenticates_before_denying_without_ledger_or_dispatch(monkeypatch, route, method):
    from app.pilot import PilotError

    monkeypatch.setenv("GATEWAY_SERVICE_TOKEN", "synthetic")
    reached = []

    def active():
        reached.append("release")
        raise PilotError()

    def verify(token):
        reached.append("workload")
        if token != "Bearer synthetic":
            raise ValueError()

    def assertion(headers, payload):
        reached.append("assertion")
        return (TENANT, PRINCIPAL), "synthetic"

    monkeypatch.setattr("app.pilot_access.verify", assertion)
    monkeypatch.setattr("app.pilot_access.configured_allowlist", lambda: {(TENANT, PRINCIPAL)})

    async def inner(scope, receive, send):
        reached.append("domain")

    async def ready():
        reached.append("ledger")

    async def receive():
        reached.append("body")
        return {"type": "http.request", "body": b"{}"}

    for token in ("Bearer synthetic", "Bearer tampered"):
        reached.clear()
        sent = []

        async def send(message):
            sent.append(message)

        scope = {"type": "http", "path": route, "method": method, "headers": [
            (b"authorization", token.encode()), (b"x-service-token", b"synthetic"),
            (b"content-type", b"application/json"), (b"content-length", b"2")], "query_string": b""}
        asyncio.run(ApiIngress(inner, SimpleNamespace(verify=verify), active, ready)(scope, receive, send))
        assert sent[0]["status"] == (503 if token == "Bearer synthetic" else 403)
        assert reached == (["workload", *(["body", "assertion"] if method == "POST" else []), "release"]
                   if token == "Bearer synthetic" else ["workload"])


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


@pytest.mark.parametrize("count,duplicate", [(1, False), (2, False), (0, False), (3, False), (2, True)])
def test_release_allowlist_admits_only_one_or_two_distinct_approved_users(monkeypatch, release_config, count, duplicate):
    import json
    from app import pilot_release
    from app.pilot import PilotError

    identities = [{"tid": TENANT, "oid": principal} for principal in (PRINCIPAL, CLIENT, AUDIENCE)][:count]
    if duplicate:
        identities[1] = identities[0]
    monkeypatch.setenv("AI_PILOT_ALLOWLIST_JSON", json.dumps(identities))
    evidence = {name: {"configuration_sha256": pilot_release.configuration_digest(release_config),
                       "checked_at": int(time.time()), "checks": {check: True for check in checks}}
                for name, checks in pilot_release.CHECKS.items()}
    signed = pilot_release.prepare_approval(release_config, evidence)
    monkeypatch.setenv("AI_PILOT_RELEASE_JSON", json.dumps(signed["approval"]))
    monkeypatch.setenv("AI_PILOT_RELEASE_SIGNATURE", signed["signature"])
    if count in (1, 2) and not duplicate:
        assert pilot_release.validate_release(release_config)["approved"] is True
    else:
        with pytest.raises(PilotError):
            pilot_release.validate_release(release_config)


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


def test_acceptance_release_cannot_authorize_regular_inputs(monkeypatch, release_config):
    import hashlib
    import json
    import os
    from app import pilot_access, pilot_release
    from app.pilot import PilotError, canonical
    from tests.test_pilot import MemoryCAS, operation, request

    payload = {"food_description": "Synthetic example: 50 g rice"}
    policy = json.loads(os.environ["AI_PILOT_POLICY_JSON"])
    policy["acceptance"] = {"max_attempts": 10, "max_reserved_usd": "2.343",
                            "payload_sha256": [hashlib.sha256(canonical(payload)).hexdigest()],
                            "expires_at": policy["deployment_verified_until"]}
    monkeypatch.setenv("AI_PILOT_POLICY_JSON", json.dumps(policy))
    monkeypatch.setenv("AI_PILOT_ALLOWLIST_JSON", json.dumps([{"tid": TENANT, "oid": PRINCIPAL}]))
    evidence = {name: {"configuration_sha256": pilot_release.configuration_digest(release_config),
                       "checked_at": int(time.time()), "checks": {check: True for check in checks}}
                for name, checks in pilot_release.CHECKS.items()}
    with pytest.raises(PilotError):
        pilot_release.prepare_approval(release_config, evidence)
    evidence["privacy"]["checks"] = {check: True for check in pilot_release.ACCEPTANCE_PRIVACY_CHECKS}
    signed = pilot_release.prepare_approval(release_config, evidence)
    assert signed["approval"]["expires_at"] <= signed["approval"]["issued_at"] + 3600
    assert not any("revok" in check or "revocation" in check for record in evidence.values() for check in record["checks"])
    monkeypatch.setenv("AI_PILOT_RELEASE_JSON", json.dumps(signed["approval"]))
    monkeypatch.setenv("AI_PILOT_RELEASE_SIGNATURE", signed["signature"])
    assert pilot_release.validate_release(release_config)["approved"] is True
    control = pilot_access.build_coordinator(MemoryCAS(), settings=release_config)
    dispatched = []

    async def dispatch(*args):
        dispatched.append(True)
        return "synthetic-result"

    monkeypatch.setattr(control, "generate", dispatch)
    monkeypatch.setattr(pilot_access, "build_coordinator", lambda: control)

    async def run():
        token = pilot_access._context.set(((TENANT, PRINCIPAL), operation(), payload))
        try:
            assert await pilot_access.generate(None, request()) == "synthetic-result"
            pilot_access._context.set(((TENANT, PRINCIPAL), operation(), {"food_description": "Unapproved"}))
            with pytest.raises(PilotError):
                await pilot_access.generate(None, request())
        finally:
            pilot_access._context.reset(token)

    asyncio.run(run())
    assert dispatched == [True]
    policy.pop("acceptance")
    monkeypatch.setenv("AI_PILOT_POLICY_JSON", json.dumps(policy))
    with pytest.raises(PilotError):
        pilot_release.validate_release(release_config)


def test_owner_input_uses_migrated_coordinator_without_manifest_restriction(monkeypatch):
    import httpx2
    from app import pilot_access
    from tests.test_openai_api import _profile_provider, _profile_completion, _request
    from tests.test_pilot import IDENTITY, migrate_owner, operation, owner_coordinator, owner_transition_fixture

    monkeypatch.setenv("APP_ENV", "test")
    monkeypatch.setenv("AI_API_ONLY_ENABLED", "false")
    monkeypatch.setenv("AI_PILOT_ENABLED", "true")
    calls = []

    def handler(request):
        calls.append(request)
        return httpx2.Response(200, json=_profile_completion())

    async def run():
        old, policy = owner_transition_fixture()
        await migrate_owner(old, policy)
        control = owner_coordinator(old, policy)
        monkeypatch.setattr(pilot_access, "build_coordinator", lambda: control)
        monkeypatch.setattr(pilot_access.time, "time", control.clock)
        token = pilot_access._context.set((IDENTITY, operation(control.clock()), {"food_description": "synthetic owner meal"}))
        provider = _profile_provider(handler)
        try:
            result = await pilot_access.generate(provider, _request(max_output_tokens=2000))
            assert result.metadata.usage_known
            ledger = control.store.rows["ledger"][0]
            assert ledger["acceptance"]["attempts"] == 16
            assert ledger["owner_usage"]["attempts"] == 1
            assert ledger["owner_usage"]["period_cost"] == 953556450
        finally:
            pilot_access._context.reset(token)
            await provider.aclose()

    asyncio.run(run())
    assert len(calls) == 1


@pytest.mark.parametrize("mutation", [None, "synthetic_privacy", "new_ledger", "old_grant", "expired", "disabled", "revoked"])
def test_owner_release_requires_new_scope_and_preserved_ledger(monkeypatch, release_config, mutation):
    import json
    import os
    from app import pilot_release
    from app.pilot import PilotError
    from tests.test_pilot import owner_transition_fixture

    release_config = release_config.model_copy(update={"ai_provider_max_concurrency": 1})
    now = int(time.time())
    original_grant = {"approval": json.loads(os.environ["AI_PILOT_RELEASE_JSON"]),
                      "signature": os.environ["AI_PILOT_RELEASE_SIGNATURE"]}
    _, template = owner_transition_fixture()
    policy = template.model_dump(mode="json")
    policy["deployment_verified_until"] = now + 30 * 86400
    policy["acceptance"]["expires_at"] = now + 30 * 86400
    policy["owner_usage"]["expires_at"] = now + 90000
    monkeypatch.setenv("AI_PILOT_POLICY_JSON", json.dumps(policy))
    monkeypatch.setenv("AI_PILOT_ALLOWLIST_JSON", json.dumps([{"tid": TENANT, "oid": PRINCIPAL}]))
    evidence = {name: {"configuration_sha256": pilot_release.configuration_digest(release_config),
                       "checked_at": now, "checks": {check: True for check in checks}}
                for name, checks in pilot_release.CHECKS.items()}
    evidence["ledger"]["checks"] = {check: True for check in pilot_release.OWNER_LEDGER_CHECKS}
    if mutation == "synthetic_privacy":
        evidence["privacy"]["checks"] = {check: True for check in pilot_release.ACCEPTANCE_PRIVACY_CHECKS}
    if mutation == "new_ledger":
        evidence["ledger"]["checks"] = {check: True for check in pilot_release.CHECKS["ledger"]}
    if mutation in {"synthetic_privacy", "new_ledger"}:
        with pytest.raises(PilotError): pilot_release.prepare_approval(release_config, evidence)
        return
    signed = pilot_release.prepare_approval(release_config, evidence)
    assert signed["approval"]["expires_at"] == now + 86400
    if mutation == "old_grant": signed = original_grant
    monkeypatch.setenv("AI_PILOT_RELEASE_JSON", json.dumps(signed["approval"]))
    monkeypatch.setenv("AI_PILOT_RELEASE_SIGNATURE", signed["signature"])
    if mutation == "expired": monkeypatch.setattr(pilot_release.time, "time", lambda: now + 90000)
    if mutation == "disabled": monkeypatch.setenv("AI_API_ONLY_ENABLED", "false")
    if mutation == "revoked": monkeypatch.setenv("AI_PILOT_RELEASE_KEY", "changed-synthetic-key" * 3)
    if mutation:
        with pytest.raises(PilotError): pilot_release.validate_release(release_config)
    else:
        assert pilot_release.validate_release(release_config)["approved"] is True


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


@pytest.mark.parametrize("fault", [None, "malformed", "missing_signature", "revoked", "disabled"])
def test_atomic_release_bundle_never_falls_back_to_old_grant(monkeypatch, release_config, fault):
    import json
    import os
    from app.pilot import PilotError
    from app.pilot_release import validate_release

    signed = {"approval": json.loads(os.environ["AI_PILOT_RELEASE_JSON"]),
              "signature": os.environ["AI_PILOT_RELEASE_SIGNATURE"]}
    if fault == "missing_signature":
        signed.pop("signature")
    monkeypatch.setenv("AI_PILOT_RELEASE_BUNDLE_JSON", "{" if fault == "malformed" else json.dumps(signed))
    if fault == "revoked":
        monkeypatch.setenv("AI_PILOT_RELEASE_KEY", "synthetic-revoked-release-key" * 2)
    if fault == "disabled":
        monkeypatch.setenv("AI_API_ONLY_ENABLED", "false")
    if fault:
        with pytest.raises(PilotError):
            validate_release(release_config)
    else:
        assert validate_release(release_config) == signed["approval"]


def test_expired_owner_grant_renews_only_inside_original_period(monkeypatch, release_config):
    import json
    import os
    from app import pilot_release
    from app.pilot import PilotError
    from tests.test_pilot import owner_transition_fixture

    now = int(time.time())
    _, template = owner_transition_fixture()
    policy = template.model_dump(mode="json")
    deadline = now + 90000
    policy["deployment_verified_until"] = deadline
    policy["acceptance"]["expires_at"] = deadline
    policy["owner_usage"]["expires_at"] = deadline
    monkeypatch.setenv("AI_PILOT_POLICY_JSON", json.dumps(policy))
    monkeypatch.setenv("AI_PILOT_ALLOWLIST_JSON", json.dumps([{"tid": TENANT, "oid": PRINCIPAL}]))
    settings = release_config.model_copy(update={"ai_provider_max_concurrency": 1})
    evidence = {name: {"configuration_sha256": pilot_release.configuration_digest(settings),
        "checked_at": now, "checks": {check: True for check in checks}}
        for name, checks in {**pilot_release.CHECKS, "ledger": pilot_release.OWNER_LEDGER_CHECKS}.items()}
    first = pilot_release.prepare_approval(settings, evidence)
    original_policy = os.environ["AI_PILOT_POLICY_JSON"]
    later = first["approval"]["expires_at"] + 1
    monkeypatch.setattr(pilot_release.time, "time", lambda: later)
    fresh = {name: {**evidence[name], "checked_at": later} for name in pilot_release.RENEWABLE}
    renewed = pilot_release.prepare_approval(settings, fresh, previous=first)
    assert renewed["approval"]["expires_at"] == deadline
    assert renewed["approval"]["configuration_sha256"] == first["approval"]["configuration_sha256"]
    assert all(renewed["approval"]["evidence"][name] == first["approval"]["evidence"][name]
               for name in ("budget", "privacy"))
    assert os.environ["AI_PILOT_POLICY_JSON"] == original_policy
    later = deadline
    with pytest.raises(PilotError):
        pilot_release.prepare_approval(settings, fresh, previous=renewed)


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


@pytest.mark.parametrize("ai_enabled", [True, False])
@pytest.mark.parametrize("mutation", [None, "body", "operation", "hmac", "timestamp", "identity", "workload", "duplicate", "anonymous", "missing_token", "missing_service", "disabled", "missing_flag", "invalid_flag", "expired", "revoked"])
def test_full_ingress_binds_workload_and_signed_request(monkeypatch, release_config, mutation, ai_enabled):
    import base64
    import hashlib
    import hmac
    import json
    import os
    from copy import deepcopy
    from starlette.testclient import TestClient
    from app.main import create_app
    from app.dependencies import get_food_analysis_use_case
    from app.pilot import canonical, consume_permit
    from app.pilot_access import _context, build_coordinator
    from app.pilot_release import validate_release
    from app.providers.base import GenerationMessage, StructuredGenerationRequest, StructuredGenerationResult
    from app.schemas.food_analysis import FoodAnalysisResponse
    from tests.test_openai_api import _food_data
    from tests.test_pilot import MemoryCAS, operation

    calls = []
    provider_calls = []
    control = build_coordinator(MemoryCAS(), settings=release_config)
    control.store.rows["ledger"] = (control.initial_ledger(), "1")
    original_rows = deepcopy(control.store.rows)
    generation = StructuredGenerationRequest(next(iter(control.routes)), [GenerationMessage("user", "synthetic")],
                                             {"type": "object"}, 1, max_output_tokens=2000)

    class Provider:
        async def generate(self, request):
            admission = control.admission(request)
            consume_permit(request, deployment=admission["deployment"], profile_id=admission["profile_id"],
                           max_output_tokens=admission["max_output_tokens"], price_version=admission["price_version"])
            provider_calls.append(True)
            assert len(control.store.rows["ledger"][0]["active"]) == 1
            return StructuredGenerationResult({})

    class UseCase:
        async def execute(self, request):
            calls.append(request)
            identity, identifier, payload = _context.get()
            await control.generate(Provider(), generation, identity, identifier, "synthetic")
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
    envelope = {"tid": TENANT, "oid": AUDIENCE if mutation == "identity" else PRINCIPAL, "operation": identifier,
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
    if mutation == "disabled" or not ai_enabled:
        monkeypatch.setenv("AI_API_ONLY_ENABLED", "false")
    elif mutation == "missing_flag":
        monkeypatch.delenv("AI_API_ONLY_ENABLED")
    elif mutation == "invalid_flag":
        monkeypatch.setenv("AI_API_ONLY_ENABLED", "invalid")
    elif mutation == "revoked":
        monkeypatch.setenv("AI_PILOT_RELEASE_SIGNATURE", "0" * 64)
    elif mutation == "expired":
        approval = json.loads(os.environ["AI_PILOT_RELEASE_JSON"])
        approval["issued_at"], approval["expires_at"] = now - 100, now - 1
        monkeypatch.setenv("AI_PILOT_RELEASE_JSON", json.dumps(approval))
        monkeypatch.setenv("AI_PILOT_RELEASE_SIGNATURE", hmac.new(os.environ["AI_PILOT_RELEASE_KEY"].encode(), canonical(approval), hashlib.sha256).hexdigest())
    monkeypatch.setattr("app.security.get_settings", lambda: release_config)
    inner = create_app()
    inner.dependency_overrides[get_food_analysis_use_case] = UseCase
    with TestClient(ApiIngress(inner, verifier, lambda: validate_release(release_config), None)) as client:
        response = client.post("/v1/food-analysis", json=payload, headers=headers)
    assert response.status_code == (200 if mutation is None and ai_enabled else 503 if mutation in {None, "disabled", "missing_flag", "invalid_flag", "expired", "revoked"} else 400 if mutation == "duplicate" else 403)
    if response.status_code == 503:
        assert response.json()["error"]["code"] == "pilot_unavailable"
        assert response.json()["error"].get("reason") == (
            "pilot_not_activated" if mutation == "disabled" or not ai_enabled else None)
    elif response.status_code != 200:
        assert "reason" not in response.json()["error"]
    assert len(calls) == (1 if mutation is None and ai_enabled else 0)
    assert len(provider_calls) == len(calls)
    if not calls:
        assert control.store.rows == original_rows


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
    assert template["parameters"]["allowlist"] == {"type": "array", "minLength": 1, "maxLength": 2}
    assert "defaultValue" not in template["parameters"]["policy"]
    app = next(resource for resource in resources if resource["type"] == "Microsoft.App/containerApps")
    assert app["properties"]["template"]["scale"]["minReplicas"] == 0
    assert app["properties"]["template"]["scale"]["maxReplicas"] == 1
    assert app["properties"]["template"]["containers"][0]["resources"] == {"cpu": "[json('0.25')]", "memory": "0.5Gi"}
    backend = next(resource for resource in resources if resource["type"] == "Microsoft.Web/sites")
    scale = backend["properties"]["functionAppConfig"]["scaleAndConcurrency"]
    assert scale == {"maximumInstanceCount": 1, "instanceMemoryMB": 512,
                     "triggers": {"http": {"perInstanceConcurrency": 2}}, "alwaysReady": []}
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
    assert environment["properties"]["appLogsConfiguration"] == {"destination": "[json('null')]"}
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
    assert app["dependsOn"][1] == "[extensionResourceId(resourceId('Microsoft.ContainerRegistry/registries', variables('registry')), 'Microsoft.Authorization/roleAssignments', guid(resourceGroup().id, 'pilot-acr-gateway'))]"
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


def test_acceptance_manifest_binds_exact_gateway_normalization():
    import hashlib
    from app.pilot import canonical
    from app.schemas.food_analysis import FoodAnalysisRequest

    helper = load_local_module("infra/pilot/prepare.py")
    manifest = helper.acceptance_manifest()
    assert manifest["max_attempts"] == 10
    assert manifest["max_reserved_usd"] == "2.343"
    assert [case["id"] for case in manifest["cases"]] == ["T2", "T5", "T4", "T1", "L1", "L2", "P1", "R1", "R4", "P5"]
    for case in manifest["cases"]:
        payload = FoodAnalysisRequest.model_validate(case["payload"]).model_dump(mode="json")
        assert hashlib.sha256(canonical(payload)).hexdigest() == case["payload_sha256"]
    assert manifest["cases"][0]["expected"]["calories"] == 272


@pytest.mark.parametrize("mutation", [None, "hash", "order", "active", "duplicate", "http", "transport", "unknown", "too_soon"])
def test_model_qualifier_one_intent_one_attempt_no_retry(monkeypatch, capsys, mutation):
    import httpx2
    import sys
    from copy import deepcopy
    from app.pilot import Conflict
    from tests.test_pilot import MemoryCAS
    from tests.test_openai_api import _food_data

    monkeypatch.setitem(sys.modules, "qualify_auth", load_local_module("infra/pilot/qualify_auth.py"))
    helper = load_local_module("infra/pilot/qualify_models.py")
    case = load_local_module("infra/pilot/prepare.py").acceptance_manifest()["cases"][0]
    allowed = [case["payload_sha256"]]
    if mutation == "hash":
        case["payload"]["food_description"] += " changed"
    if mutation == "order":
        case["id"] = "T5"
    before = {"blocked": False, "active": {"unexpected": "person"} if mutation == "active" else {},
              "acceptance": {"attempts": 0, "reserved": 0},
              "last_time": time.time() if mutation == "too_soon" else 0}
    store, receipts, calls = MemoryCAS(), MemoryCAS(), []
    store.rows["ledger"] = (deepcopy(before), "1")
    if mutation == "duplicate":
        receipts.rows["T2"] = ({"state": "intent"}, "1")

    class Client:
        async def post(self, url, **kwargs):
            calls.append((url, kwargs))
            store.rows["ledger"] = ({**before, "acceptance": {"attempts": 1, "reserved": 234300000}}, "2")
            operation = kwargs["headers"]["X-Operation-Id"]
            key = "op-" + helper.digest(b"f" * 48, "operation", [(TENANT, PRINCIPAL), operation])
            store.rows[key] = ({"settled": True, "usage_known": mutation != "unknown"}, "1")
            if mutation == "transport":
                raise TimeoutError("private diagnostic must not be logged")
            payload = {"estimate": _food_data()}
            return httpx2.Response(503 if mutation == "http" else 200, json=payload)

    arguments = (Client(), store, receipts, case, 0, allowed, "private-token", (TENANT, PRINCIPAL),
                 "s" * 48, "t" * 48, "f" * 48)
    if mutation:
        with pytest.raises(Conflict if mutation == "duplicate" else RuntimeError):
            asyncio.run(helper.run_case(*arguments))
    else:
        result = asyncio.run(helper.run_case(*arguments))
        assert result["state"] == "response_received"
        with pytest.raises(RuntimeError):
            asyncio.run(helper.run_case(*arguments))
    assert len(calls) == (0 if mutation in {"hash", "order", "active", "duplicate", "too_soon"} else 1)
    assert "private-token" not in capsys.readouterr().out
    if calls:
        assert receipts.rows["T2"][0]["state"] != "intent"


@pytest.mark.parametrize("mutation", [None, "enabled", "receipt", "ledger", "timeout", "unsettled", "changed_hold", "conflict", "local_limit", "provider"])
def test_terminal_429_completion_preserves_money_counters_and_replay(monkeypatch, mutation):
    import hashlib
    import sys
    from copy import deepcopy
    from app.pilot import Conflict, canonical, digest
    from tests.test_pilot import MemoryCAS, IDENTITY, SECRET, operation

    monkeypatch.setitem(sys.modules, "qualify_auth", load_local_module("infra/pilot/qualify_auth.py"))
    helper = load_local_module("infra/pilot/qualify_models.py")
    monkeypatch.setenv("AI_API_ONLY_ENABLED", "true" if mutation == "enabled" else "false")
    store = MemoryCAS()
    identifier = operation(time.time() - 300)
    key = "op-" + digest(SECRET, "operation", [IDENTITY, identifier])
    ledger = {"blocked": False, "acceptance": {"attempts": 5, "reserved": 1171500000},
              "buckets": {"total:day": {"cost": 240686325, "count": 5}},
              "active": {key: digest(SECRET, "person", IDENTITY)}}
    record = {"state": "unknown", "settled": True, "usage_known": False,
              "reserved": 234300000, "charged": 234300000, "fingerprint": "unchanged"}
    if mutation == "unsettled": record["settled"] = False
    if mutation == "changed_hold": record["charged"] = 0
    receipt = {"case": "L1", "http_status": 504 if mutation == "timeout" else 429,
               "state": "http_failure", "created_at": int(time.time()) - 300,
               "completed_at": int(time.time()) - 290, "operation": identifier,
               "operation_record": deepcopy(record), "ledger_acceptance": deepcopy(ledger["acceptance"])}
    if mutation in {"local_limit", "provider"}:
        receipt["error_code"] = "pilot_limit" if mutation == "local_limit" else "provider_rate_limited"
    store.rows = {"ledger": (deepcopy(ledger), "1"), key: (deepcopy(record), "1")}
    original = deepcopy(store.rows)
    ledger_hash = hashlib.sha256(canonical(ledger)).hexdigest()
    receipt_hash = hashlib.sha256(canonical(receipt)).hexdigest()
    if mutation == "receipt": receipt_hash = "0" * 64
    if mutation == "ledger": ledger_hash = "0" * 64
    if mutation == "conflict":
        async def conflict(changes): raise Conflict()
        store.commit = conflict
    async def run():
        arguments = (store, receipt, IDENTITY, SECRET.decode(), ledger_hash, receipt_hash)
        if mutation not in {None, "provider"}:
            with pytest.raises(Conflict if mutation == "conflict" else RuntimeError):
                await helper.complete_terminal_429(*arguments)
            assert store.rows == original
        else:
            result = await helper.complete_terminal_429(*arguments)
            assert result["slot_released"] and result["charged"] == 234300000
            updated = store.rows["ledger"][0]
            assert updated == {**ledger, "active": {}}
            assert all(store.rows[key][0][field] == value for field, value in record.items())
            with pytest.raises(RuntimeError): await helper.complete_terminal_429(*arguments)
    asyncio.run(run())


@pytest.mark.parametrize("attempts", [10, 11, 12, 13, 14])
def test_correction_cases_continue_counters_with_separate_receipts(monkeypatch, attempts):
    import httpx2
    import sys
    from copy import deepcopy
    from tests.test_pilot import MemoryCAS
    from tests.test_openai_api import _food_data

    monkeypatch.setitem(sys.modules, "qualify_auth", load_local_module("infra/pilot/qualify_auth.py"))
    helper = load_local_module("infra/pilot/qualify_models.py")
    identifier = ("L1", "L2", "P1", "P5", "P5")[attempts - 10]
    case = next(case for case in load_local_module("infra/pilot/prepare.py").acceptance_manifest()["cases"]
                if case["id"] == identifier)
    store, receipts, calls = MemoryCAS(), MemoryCAS(), []
    original = {"blocked": False, "active": {}, "last_time": 0,
                "acceptance": {"attempts": attempts, "reserved": attempts * 234300000}}
    store.rows["ledger"] = (deepcopy(original), "1")
    receipts.rows[identifier] = ({"old_receipt": True}, "old-etag")

    class Client:
        async def post(self, url, **kwargs):
            calls.append(True)
            store.rows["ledger"] = ({**original, "acceptance": {
                "attempts": attempts + 1, "reserved": (attempts + 1) * 234300000}}, "2")
            operation = kwargs["headers"]["X-Operation-Id"]
            key = "op-" + helper.digest(b"f" * 48, "operation", [(TENANT, PRINCIPAL), operation])
            store.rows[key] = ({"settled": True, "usage_known": True}, "1")
            return httpx2.Response(200, json={"estimate": _food_data()})

    arguments = (Client(), store, receipts, case, attempts, [case["payload_sha256"]], "private-token",
                 (TENANT, PRINCIPAL), "s" * 48, "t" * 48, "f" * 48)
    if attempts == 14:
        with pytest.raises(RuntimeError):
            asyncio.run(helper.run_case(*arguments))
        assert store.rows["ledger"][0] == original
    else:
        asyncio.run(helper.run_case(*arguments))
        assert receipts.rows["correction-" + identifier][0]["state"] == "response_received"
        with pytest.raises(RuntimeError):
            asyncio.run(helper.run_case(*arguments))
    assert len(calls) == (0 if attempts == 14 else 1)
    assert receipts.rows[identifier] == ({"old_receipt": True}, "old-etag")


@pytest.mark.parametrize("iphone", [False, True])
@pytest.mark.parametrize("mutation", [None, "enabled", "ledger", "etag", "policy", "money", "reset", "active", "blocked", "expiry", "payload", "duplicate", "old_payload", "conflict"])
def test_acceptance_amendment_preserves_all_existing_state(monkeypatch, mutation, iphone):
    import hashlib
    import sys
    from copy import deepcopy
    from app.pilot import Conflict, PilotError, PilotPolicy, canonical
    from tests.test_pilot import profile_coordinator

    monkeypatch.setenv("AI_API_ONLY_ENABLED", "true" if mutation == "enabled" else "false")
    monkeypatch.setitem(sys.modules, "qualify_auth", load_local_module("infra/pilot/qualify_auth.py"))
    helper = load_local_module("infra/pilot/qualify_models.py")
    old_attempts, new_attempts = (14, 16) if iphone else (10, 14)
    old_reserve, new_reserve = ("3.2802", "3.7488") if iphone else ("2.343", "3.2802")
    limits = {"minute": 2, "day": old_attempts, "month": old_attempts, "concurrent": 1,
              "daily_usd": "2.343", "monthly_usd": "2.343"}
    control = profile_coordinator(person=limits, total=limits, acceptance={
        "max_attempts": old_attempts, "max_reserved_usd": old_reserve, "payload_sha256": ["a" * 64],
        "expires_at": int(time.time()) + 3600})
    ledger = control.initial_ledger()
    ledger.update(acceptance={"attempts": old_attempts, "reserved": old_attempts * 234300000},
                  buckets={"total:day": {"cost": 945317175, "count": old_attempts}}, last_time=123)
    if mutation == "active": ledger["active"] = {"op-held": "person"}
    if mutation == "blocked": ledger["blocked"] = True
    if mutation == "reset": ledger["acceptance"] = {"attempts": 0, "reserved": 0}
    control.store.rows["ledger"] = (ledger, "7")
    for index in range(4):
        control.store.rows[f"op-held-{index}"] = ({"state": "unknown", "charged": 234300000,
                                                  "fingerprint": f"retained-{index}"}, "2")
    previous = deepcopy(control.store.rows)
    policy = control.policy.model_dump(mode="json")
    policy["acceptance"].update(max_attempts=new_attempts, max_reserved_usd=new_reserve)
    hashes = ["b" * 64, "c" * 64]
    options = {"iphone_payload_sha256": hashes} if iphone else {}
    if iphone: policy["acceptance"]["payload_sha256"] = hashes.copy()
    if mutation == "duplicate":
        options["iphone_payload_sha256"] = ["b" * 64, "b" * 64]
        policy["acceptance"]["payload_sha256"] = options["iphone_payload_sha256"]
    if mutation == "old_payload":
        options["iphone_payload_sha256"] = ["a" * 64, "b" * 64]
        policy["acceptance"]["payload_sha256"] = options["iphone_payload_sha256"]
    if mutation == "payload": policy["acceptance"]["payload_sha256"] = ["d" * 64]
    if mutation == "expiry": policy["acceptance"]["expires_at"] += 1
    for scope in ("person", "total"): policy[scope].update(day=new_attempts, month=new_attempts)
    if mutation == "money": policy["person"]["daily_usd"] = "3.2802"
    policy_hash = hashlib.sha256(canonical(policy)).hexdigest()
    ledger_hash = hashlib.sha256(canonical(ledger)).hexdigest()
    if mutation == "conflict":
        async def conflict(changes): raise Conflict()
        control.store.commit = conflict
    arguments = (control, PilotPolicy.model_validate(policy), "0" * 64 if mutation == "ledger" else ledger_hash,
                 "wrong" if mutation == "etag" else "7", "0" * 64 if mutation == "policy" else policy_hash)
    if mutation:
        expected_error = {"conflict": Conflict, "blocked": PilotError}.get(mutation, RuntimeError)
        with pytest.raises(expected_error):
            asyncio.run(helper.extend_acceptance(*arguments, **options))
        assert control.store.rows == previous
    else:
        amendment = asyncio.run(helper.extend_acceptance(*arguments, **options))
        assert control.store.rows["ledger"][0] == {**ledger, "policy": amendment["revised_policy"]}
        assert all(control.store.rows[key] == value for key, value in previous.items() if key != "ledger")
        assert control.store.rows[f"acceptance-extension-{new_attempts}-v1"][0] == amendment
        assert amendment["additional_attempts"] == new_attempts - old_attempts
        with pytest.raises(PilotError):
            asyncio.run(helper.extend_acceptance(*arguments, **options))


def test_acceptance_schema_has_six_additional_attempts_only():
    from app.pilot import AcceptanceRun
    from pydantic import ValidationError

    values = {"max_attempts": 16, "max_reserved_usd": "3.7488", "payload_sha256": ["a" * 64],
              "expires_at": int(time.time()) + 3600}
    assert AcceptanceRun.model_validate(values).max_attempts == 16
    for change in ({"max_attempts": 17}, {"max_reserved_usd": "3.748800001"}):
        with pytest.raises(ValidationError):
            AcceptanceRun.model_validate({**values, **change})


def test_model_free_ledger_qualification_preserves_unknown_holds():
    from tests.test_pilot import profile_coordinator

    helper = load_local_module("infra/pilot/qualify_ledger.py")
    control = profile_coordinator(acceptance={
        "max_attempts": 10, "max_reserved_usd": "2.343", "payload_sha256": ["a" * 64],
        "expires_at": int(time.time()) + 3600})
    result = asyncio.run(helper.exercise(control))
    assert result["model_attempts"] == 0
    assert result["unknown_hold_survives_restart"] is True
    assert all(value is True for name, value in result.items() if name != "model_attempts")
    assert control.store.rows["ledger"][0]["acceptance"] == {"attempts": 1, "reserved": 234300000}


def test_auth_qualifier_only_sends_nonmanifest_probes_and_stops_on_mismatch():
    import base64
    import json

    helper = load_local_module("infra/pilot/qualify_auth.py")
    calls = []
    token = "synthetic.synthetic." + base64.urlsafe_b64encode(b"synthetic-signature").decode()

    class Client:
        def post(self, url, *, headers, json):
            calls.append((url, headers, json))
            return SimpleNamespace(status_code=503 if len(calls) == 1 else 403)

    results = helper.probe(Client(), "https://synthetic.invalid", token, (TENANT, PRINCIPAL), "s" * 48, "t" * 48, 503)
    assert len(results) == len(calls) == 9
    assert all(record["passed"] for record in results)
    manifest = load_local_module("infra/pilot/prepare.py").acceptance_manifest()
    assert helper.PAYLOAD not in [case["payload"] for case in manifest["cases"]]
    assert token not in json.dumps(results)
    calls.clear()
    with pytest.raises(RuntimeError, match="valid_authentication"):
        helper.probe(Client(), "https://synthetic.invalid", token, (TENANT, PRINCIPAL), "s" * 48, "t" * 48, 403)
    assert len(calls) == 1


@pytest.mark.parametrize("expected,mutation", [(403, None), (503, None), (503, "different_token"),
    (503, "no_prior_token"), (403, "expired"), (503, "expired"), (403, "readiness"), (503, "analysis")])
def test_release_qualifier_same_live_token_and_nonmanifest_only(capsys, expected, mutation):
    import hashlib

    helper = load_local_module("infra/pilot/qualify_auth.py")
    token = helper.jwt.encode({"exp": int(time.time()) + (-60 if mutation == "expired" else 300)},
        "synthetic-signing-key-long-enough-for-tests", algorithm="HS256")
    fingerprint = hashlib.sha256(token.encode()).hexdigest()
    previous = None if expected == 403 or mutation == "no_prior_token" else (
        "0" * 64 if mutation == "different_token" else fingerprint)
    calls = []

    class Client:
        def request(self, method, url, **kwargs):
            calls.append((method, url, kwargs))
            correct = (200 if expected == 403 else 503) if method == "GET" else expected
            wrong = mutation == "readiness" and method == "GET" or mutation == "analysis" and method == "POST"
            return SimpleNamespace(status_code=500 if wrong else correct)

    if mutation:
        with pytest.raises(RuntimeError):
            helper.probe_release(Client(), "https://synthetic.invalid", token,
                (TENANT, PRINCIPAL), "s" * 48, "t" * 48, expected, previous)
    else:
        results = helper.probe_release(Client(), "https://synthetic.invalid", token,
            (TENANT, PRINCIPAL), "s" * 48, "t" * 48, expected, previous)
        assert all(record["passed"] and record["token_sha256"] == fingerprint for record in results)
    assert len(calls) == (0 if mutation in {"different_token", "no_prior_token", "expired"}
                         else 1 if mutation == "readiness" else 2)
    if len(calls) == 2:
        assert calls[0][0] == "GET" and "json" not in calls[0][2]
        assert calls[1][0] == "POST" and calls[1][2]["json"] == helper.PAYLOAD
        assert all(call[2]["headers"]["Authorization"] == "Bearer " + token for call in calls)
    assert token not in capsys.readouterr().out


@pytest.mark.parametrize("signalled", [True, False])
def test_release_cycle_keeps_token_in_memory_and_bounds_operator_signal(monkeypatch, signalled):
    helper = load_local_module("infra/pilot/qualify_auth.py")
    calls, handlers, waits = [], [], []
    sentinel = object()

    class Event:
        def set(self):
            pass

        def wait(self, *, timeout):
            waits.append(timeout)
            return signalled

    def register(signal_number, handler):
        handlers.append((signal_number, handler))
        return sentinel

    def probe(*args):
        calls.append(args)
        return [{"token_sha256": "a" * 64, "passed": True}]

    monkeypatch.setattr(helper.threading, "Event", Event)
    monkeypatch.setattr(helper.signal, "signal", register)
    monkeypatch.setattr(helper, "probe_release", probe)
    if signalled:
        assert len(helper.probe_release_cycle(None, "base", "same-token", (TENANT, PRINCIPAL), "secret", "service")) == 2
        assert calls[0][2] == calls[1][2] == "same-token"
        assert calls[0][-1] == 403 and calls[1][-2:] == (503, "a" * 64)
    else:
        with pytest.raises(RuntimeError, match="No bounded operator"):
            helper.probe_release_cycle(None, "base", "same-token", (TENANT, PRINCIPAL), "secret", "service")
        assert len(calls) == 1
    assert waits == [120]
    assert handlers[-1] == (helper.signal.SIGTERM, sentinel)


@pytest.mark.parametrize("write,cleanup", [(True, False), (False, False), (False, True)])
def test_release_cycle_receipt_is_isolated_create_only_and_explicitly_cleaned(monkeypatch, write, cleanup):
    from app.pilot_table import AzureTableStore

    helper = load_local_module("infra/pilot/qualify_auth.py")
    changes, removed, closed, verified = [], [], [], []
    results = [{"check": "pilot_ledger_unchanged", "passed": True}]

    class Store:
        partition = "pilot-v1"

        async def commit(self, records):
            changes.append((self.partition, records))

        async def read(self, key):
            assert self.partition == "qualification-release-v1" and key == "result"
            return {"checks": results}, "etag"

        async def delete_entity(self, partition, key, **kwargs):
            removed.append((partition, key, kwargs))

        async def close(self):
            closed.append(True)

    async def ledger():
        verified.append(True)

    store = Store()
    store.client = store
    monkeypatch.setattr(helper, "read_ledger", ledger)
    monkeypatch.setattr(AzureTableStore, "connect", lambda *args: store)
    monkeypatch.setenv("AI_PILOT_TABLE_ENDPOINT", "https://synthetic.table.core.windows.net")
    monkeypatch.setenv("AI_PILOT_TABLE_NAME", "PilotSynthetic")
    result = asyncio.run(helper.cycle_receipt(results if write else None, cleanup=cleanup))
    assert verified == closed == [True]
    if write:
        assert result is None and removed == []
        assert changes[0][0] == "qualification-release-v1"
        assert changes[0][1][0][0] == "result" and changes[0][1][0][2] is None
        assert changes[0][1][0][1]["checks"] == results
    else:
        assert result == {"checks": results} and not changes
        if cleanup:
            assert removed[0][:2] == ("qualification-release-v1", "result")
            assert removed[0][2]["etag"] == "etag"
        else:
            assert not removed


def test_auth_qualifier_limits_are_bounded_and_stop_on_mismatch():
    helper = load_local_module("infra/pilot/qualify_auth.py")
    calls = []

    class Client:
        def post(self, url, *, headers, content):
            body = content if isinstance(content, bytes) else b"".join(content)
            calls.append((headers, body))
            return SimpleNamespace(status_code=[415, 413, 400, 400, 413][len(calls) - 1])

    results = helper.probe_limits(Client(), "https://synthetic.invalid", "private-token",
        (TENANT, PRINCIPAL), "s" * 48, "t" * 48)
    assert len(results) == len(calls) == 5
    assert all(record["passed"] for record in results)
    assert max(len(body) for _, body in calls) == 4 * 1024 * 1024 + 64 * 1024 + 1
    assert all("Authorization" not in authorization for authorization, _ in calls[:2])

    class WrongClient:
        def post(self, *args, **kwargs):
            calls.append(None)
            return SimpleNamespace(status_code=200)

    calls.clear()
    with pytest.raises(RuntimeError, match="unsupported_media_before_auth"):
        helper.probe_limits(WrongClient(), "https://synthetic.invalid", "private-token",
            (TENANT, PRINCIPAL), "s" * 48, "t" * 48)
    assert len(calls) == 1


def test_auth_qualifier_slow_body_is_incomplete_and_connection_is_closed(monkeypatch):
    helper = load_local_module("infra/pilot/qualify_auth.py")
    sent = []
    closed = []

    class Connection:
        def __init__(self, host, *, timeout):
            assert host == "synthetic.invalid" and timeout == 20

        def putrequest(self, method, route):
            assert (method, route) == ("POST", "/v1/food-analysis")

        def putheader(self, name, value):
            pass

        def endheaders(self):
            pass

        def send(self, content):
            sent.append(content)

        def getresponse(self):
            return SimpleNamespace(status=408)

        def close(self):
            closed.append(True)

    monkeypatch.setattr(helper, "HTTPSConnection", Connection)
    result = helper.probe_slow_body("https://synthetic.invalid", "token", (TENANT, PRINCIPAL), "secret", "service")
    assert result["passed"] is True
    assert sent == [b"1\r\n{\r\n"] and closed == [True]


@pytest.mark.parametrize("failure", ["AADSTS501051: no assigned role", "timeout"])
def test_auth_qualifier_foreign_workload_never_counts_token_failure(monkeypatch, capsys, failure):
    helper = load_local_module("infra/pilot/qualify_auth.py")
    monkeypatch.setenv("AI_PILOT_GATEWAY_CLIENT_ID", PRINCIPAL)
    monkeypatch.setenv("GATEWAY_WORKLOAD_AUDIENCE", AUDIENCE)

    class Credential:
        def __init__(self, **kwargs):
            assert kwargs["client_id"] == PRINCIPAL and kwargs["retry_total"] == 0

        def __enter__(self):
            return self

        def __exit__(self, *args):
            pass

        def get_token(self, *args):
            raise helper.ClientAuthenticationError(failure)

    monkeypatch.setattr(helper, "ManagedIdentityCredential", Credential)
    with pytest.raises(RuntimeError, match="not an authorization test"):
        helper.probe_foreign_workload(None, "https://synthetic.invalid", (TENANT, PRINCIPAL), "secret", "service", None)
    assert failure not in capsys.readouterr().out


@pytest.mark.parametrize("mutation", [None, "accepted", "wrong_identity", "expired"])
def test_foreign_qualifier_requires_issued_token_and_real_gateway_denial(monkeypatch, capsys, mutation):
    helper = load_local_module("infra/pilot/qualify_auth.py")
    foreign = "00000000-0000-4000-8000-000000000002"
    for name, value in {"AI_PILOT_GATEWAY_CLIENT_ID": CLIENT, "QUALIFICATION_FOREIGN_PRINCIPAL_ID": foreign,
                        "GATEWAY_BACKEND_PRINCIPAL_ID": PRINCIPAL}.items():
        monkeypatch.setenv(name, value)
    claims = {"tid": TENANT, "oid": PRINCIPAL if mutation == "wrong_identity" else foreign, "appid": CLIENT,
              "aud": "https://storage.azure.com", "exp": int(time.time()) + (-60 if mutation == "expired" else 300)}
    token = helper.jwt.encode(claims, "synthetic-signing-key-long-enough-for-tests", algorithm="HS256")
    scopes, calls = [], []

    class Credential:
        def __init__(self, **kwargs):
            assert kwargs["client_id"] == CLIENT and kwargs["retry_total"] == 0

        def __enter__(self):
            return self

        def __exit__(self, *args):
            pass

        def get_token(self, scope):
            scopes.append(scope)
            return SimpleNamespace(token=token)

    class Client:
        def post(self, url, **kwargs):
            calls.append((url, kwargs))
            return SimpleNamespace(status_code=200 if mutation == "accepted" else 403)

    monkeypatch.setattr(helper, "ManagedIdentityCredential", Credential)
    if mutation:
        with pytest.raises(RuntimeError):
            helper.probe_foreign_workload(Client(), "https://synthetic.invalid", (TENANT, PRINCIPAL), "secret", "service", None)
    else:
        result = helper.probe_foreign_workload(Client(), "https://synthetic.invalid", (TENANT, PRINCIPAL), "secret", "service", None)
        assert result["passed"] and result["boundary"] == "gateway"
        assert result["isolates_wrong_principal_only"] is False
    assert scopes == ["https://storage.azure.com/.default"]
    assert len(calls) == (0 if mutation in {"wrong_identity", "expired"} else 1)
    if calls:
        assert calls[0][1]["headers"]["Authorization"] == "Bearer " + token
        assert calls[0][1]["json"] == helper.PAYLOAD
    assert token not in capsys.readouterr().out


def test_ledger_qualification_isolates_writes_and_uses_ai_off_settings(monkeypatch, capsys):
    import json
    from copy import deepcopy
    from tests.test_pilot import MemoryCAS, profile_coordinator

    helper = load_local_module("infra/pilot/qualify_ledger.py")
    control = profile_coordinator(acceptance={
        "max_attempts": 10, "max_reserved_usd": "2.343", "payload_sha256": ["a" * 64],
        "expires_at": int(time.time()) + 3600})
    original = deepcopy(control.store.rows)

    class PartitionedStore:
        partition = "pilot-v1"
        closed = False

        def __init__(self):
            self.partitions = {"pilot-v1": control.store}
            self.client = self

        def current(self):
            return self.partitions.setdefault(self.partition, MemoryCAS())

        async def read(self, key):
            return await self.current().read(key)

        async def commit(self, changes):
            assert self.partition.startswith("qualification-")
            await self.current().commit(changes)

        async def query_entities(self, query, *, parameters, logging_enable):
            assert parameters["partition"] == self.partition
            for key in list(self.current().rows):
                yield {"RowKey": key}

        async def delete_entity(self, partition, key, *, logging_enable):
            assert partition == self.partition and partition.startswith("qualification-")
            del self.current().rows[key]

        async def close(self):
            self.closed = True

    store = PartitionedStore()
    control.store = store
    settings = object()
    monkeypatch.setattr(helper, "Settings", lambda: settings)

    def configured(*, settings):
        assert settings is expected_settings
        return control

    expected_settings = settings
    monkeypatch.setattr(helper, "build_coordinator", configured)
    monkeypatch.setenv("AI_API_ONLY_ENABLED", "false")
    monkeypatch.setenv("AI_PILOT_RESOURCE_GROUP", "pft-pilot-20260919")
    monkeypatch.setenv("AI_PILOT_TABLE_NAME", "PilotLedger")
    asyncio.run(helper.main())
    result = json.loads(capsys.readouterr().out.removeprefix("QUALIFICATION "))
    assert result["pilot_attempts"] == result["pilot_reserved_units"] == 0
    assert result["pilot_ledger_unchanged"] is True
    assert store.partitions["pilot-v1"].rows == original
    assert all(not value.rows for key, value in store.partitions.items() if key != "pilot-v1")
    assert store.closed is True


def test_pilot_bootstrap_resumes_without_duplicate_mutations_or_secret_arguments(monkeypatch, tmp_path):
    from datetime import datetime, timedelta
    import json
    import shutil

    root = Path(__file__).resolve().parents[2] / "infra/pilot"
    monkeypatch.syspath_prepend(str(root))
    helper = load_local_module("infra/pilot/provision.py")
    helper.ROOT = tmp_path
    shutil.copyfile(root / "policy.proposed.json", tmp_path / "policy.proposed.json")
    args = SimpleNamespace(name="synthetic", azure_config=tmp_path, subscription=CLIENT, tenant=TENANT)
    bootstrap = helper.Bootstrap(args)
    owner = {"id": PRINCIPAL, "mail": None, "userPrincipalName": "synthetic#EXT#@example.invalid",
             "otherMails": ["synthetic@example.invalid"]}
    calls = []

    def cli(*arguments):
        calls.append(arguments)
        if arguments[:2] == ("group", "exists"):
            return False
        if arguments[:3] == ("ad", "app", "list") or arguments[:2] == ("resource", "list"):
            return []
        if arguments[:3] in (("ad", "app", "create"), ("ad", "sp", "create")):
            return {"id": f"00000000-0000-4000-8000-{len(calls):012d}",
                    "appId": f"00000000-0000-4000-9000-{len(calls):012d}"}
        return None

    monkeypatch.setattr(bootstrap, "cli", cli)
    bootstrap.initialize(owner)
    original = list(calls)
    bootstrap.initialize(owner)
    assert calls == original
    state = json.loads((bootstrap.directory / "period.json").read_text())
    assert datetime.fromisoformat(state["end"]) - datetime.fromisoformat(state["start"]) == timedelta(days=30)
    parameters_file = bootstrap.directory / "parameters.json"
    parameters = json.loads(parameters_file.read_text())["parameters"]
    assert parameters["enableAI"]["value"] is False
    assert parameters["deployGateway"]["value"] is False
    assert parameters["allowlist"]["value"] == [{"tid": TENANT, "oid": PRINCIPAL}]
    assert parameters["budgetEmails"]["value"] == ["synthetic@example.invalid"]
    assert parameters_file.stat().st_mode & 0o777 == 0o600
    keys = [parameters[name]["value"] for name in ("serviceToken", "signingKey", "fingerprintKey", "releaseKey")]
    assert len(set(keys)) == 4 and all(len(key) >= 32 for key in keys)
    assert not any(key in str(calls) for key in keys)
    helper.private_json(bootstrap.directory / "unresolved.intent.json", {})
    with pytest.raises(RuntimeError, match="Unresolved"):
        bootstrap.once("unresolved", "group", "create")
    assert calls == original


def test_pilot_login_probe_never_persists_tokens_or_posts_model_requests(monkeypatch, tmp_path, capsys):
    import json
    import msal
    import requests

    monkeypatch.syspath_prepend(str(Path(__file__).resolve().parents[2] / "infra/pilot"))
    helper = load_local_module("infra/pilot/provision.py")
    helper.ROOT = tmp_path
    args = SimpleNamespace(name="synthetic", azure_config=tmp_path, subscription=CLIENT, tenant=TENANT)
    bootstrap = helper.Bootstrap(args)
    helper.private_json(bootstrap.directory / "period.json", {
        "subscription": CLIENT, "tenant": TENANT, "owner": PRINCIPAL, "end": "2030-01-01T00:00:00+00:00"})
    helper.private_json(bootstrap.directory / "runtime-create.json", {"properties": {"outputs": {
        name: {"value": value} for name, value in {
            "nativeClientId": CLIENT, "backendAudience": AUDIENCE,
            "apiBaseURL": "https://pft-pilot-synthetic.azurewebsites.net/api"}.items()}}})
    result = {"access_token": "synthetic-access-token", "refresh_token": "synthetic-refresh-token",
              "id_token_claims": {"tid": TENANT, "oid": PRINCIPAL}}
    monkeypatch.setattr(msal, "PublicClientApplication", lambda *args, **kwargs: SimpleNamespace(
        initiate_device_flow=lambda **kwargs: {"user_code": "synthetic", "message": "Synthetic sign-in instruction"},
        acquire_token_by_device_flow=lambda flow: result))
    calls = []

    def get(self, url, **kwargs):
        calls.append((url, kwargs))
        return SimpleNamespace(status_code=503, json=lambda: {"status": "not_ready"})

    monkeypatch.setattr(requests.Session, "get", get)
    bootstrap.login_probe()
    assert len(calls) == 1 and calls[0][0].endswith("/api/readiness")
    assert calls[0][1]["allow_redirects"] is False
    assert result == {}
    evidence = list(bootstrap.directory.glob("native-login-probe-*.json"))
    assert len(evidence) == 1
    assert json.loads(evidence[0].read_text())["expected_ai_off_backend_response"] is True
    assert evidence[0].stat().st_mode & 0o777 == 0o600
    captured = capsys.readouterr().out + "".join(file.read_text() for file in bootstrap.directory.glob("*.json"))
    assert "synthetic-access-token" not in captured and "synthetic-refresh-token" not in captured


@pytest.mark.parametrize("enabled", ["false", "true"])
def test_native_analysis_login_requires_ai_off_and_clears_tokens(monkeypatch, tmp_path, enabled):
    import msal

    monkeypatch.syspath_prepend(str(Path(__file__).resolve().parents[2] / "infra/pilot"))
    helper = load_local_module("infra/pilot/provision.py")
    helper.ROOT = tmp_path
    bootstrap = helper.Bootstrap(SimpleNamespace(name="synthetic", azure_config=tmp_path, subscription=CLIENT, tenant=TENANT))
    helper.private_json(bootstrap.directory / "period.json", {
        "subscription": CLIENT, "tenant": TENANT, "owner": PRINCIPAL, "end": "2030-01-01T00:00:00+00:00"})
    helper.private_json(bootstrap.directory / "runtime-create.json", {"properties": {"outputs": {
        name: {"value": value} for name, value in {
            "nativeClientId": CLIENT, "backendAudience": AUDIENCE, "resourceGroup": "pft-pilot-synthetic",
            "apiBaseURL": "https://pft-pilot-synthetic.azurewebsites.net/api"}.items()}}})
    result = {"access_token": "private-token", "refresh_token": "private-refresh",
              "id_token_claims": {"tid": TENANT, "oid": PRINCIPAL}}
    logins = []

    def application(*args, **kwargs):
        logins.append(True)
        return SimpleNamespace(initiate_device_flow=lambda **kwargs: {"user_code": "synthetic", "message": "Synthetic login"},
                               acquire_token_by_device_flow=lambda flow: result)

    def fail_checks(*args):
        raise RuntimeError("Synthetic downstream failure")

    monkeypatch.setattr(msal, "PublicClientApplication", application)
    monkeypatch.setattr(bootstrap, "cli", lambda *args: enabled)
    monkeypatch.setattr(bootstrap, "native_analysis_checks", fail_checks)
    with pytest.raises(RuntimeError, match="Synthetic downstream failure" if enabled == "false" else "requires AI off"):
        bootstrap.login_probe(analysis=True)
    if enabled == "false":
        assert result == {} and logins == [True]
    else:
        assert not logins
    assert not list(bootstrap.directory.glob("native-analysis-probe-*.json"))


@pytest.mark.parametrize("mismatch", [False, True])
def test_native_analysis_probe_is_nonmanifest_bounded_and_stops_on_mismatch(monkeypatch, tmp_path, capsys, mismatch):
    from uuid import UUID
    import requests
    from app.pilot import canonical
    from app.schemas.food_analysis import FoodAnalysisRequest
    import hashlib

    monkeypatch.syspath_prepend(str(Path(__file__).resolve().parents[2] / "infra/pilot"))
    helper = load_local_module("infra/pilot/provision.py")
    helper.ROOT = tmp_path
    bootstrap = helper.Bootstrap(SimpleNamespace(name="synthetic", azure_config=tmp_path, tenant=TENANT))
    helper.private_json(bootstrap.directory / "acceptance-parameters.json", {"parameters": {
        "signingKey": {"value": "s" * 48}, "serviceToken": {"value": "t" * 48}}})
    deployment = {"apiBaseURL": {"value": "https://pft-pilot-20260919-api.azurewebsites.net/api"},
        "gatewayBaseURL": {"value": "https://pft-pilot-20260919-gateway.gentleriver-150ab3f0.swedencentral.azurecontainerapps.io"}}
    calls = []

    def post(self, url, **kwargs):
        calls.append((url, kwargs))
        status, code = [(400, "operation_required"), (503, "pilot_unavailable"), (403, "pilot_forbidden")][len(calls) - 1]
        return SimpleNamespace(status_code=200 if mismatch else status, json=lambda: {"error": {"code": code}})

    monkeypatch.setattr(requests.Session, "post", post)
    if mismatch:
        with pytest.raises(RuntimeError, match="native_analysis_identity"):
            bootstrap.native_analysis_checks(deployment, {"owner": PRINCIPAL}, "private-token")
        assert len(calls) == 1
    else:
        result = bootstrap.native_analysis_checks(deployment, {"owner": PRINCIPAL}, "private-token")
        assert len(calls) == 3 and all(check["passed"] for check in result["checks"])
        assert result["model_attempts"] == 0
        assert "X-Operation-Id" not in calls[0][1]["headers"]
        assert UUID(calls[1][1]["headers"]["X-Operation-Id"]).version == 7
    hashes = {case["payload_sha256"] for case in load_local_module("infra/pilot/prepare.py").acceptance_manifest()["cases"]}
    for _, kwargs in calls:
        payload = FoodAnalysisRequest.model_validate(kwargs["json"]).model_dump(mode="json")
        assert hashlib.sha256(canonical(payload)).hexdigest() not in hashes
        assert kwargs["allow_redirects"] is False and kwargs["timeout"] == (10, 30)
    assert "private-token" not in capsys.readouterr().out


@pytest.mark.parametrize("build", ["5", "6", "7", "8", "9", "10", "11", "12"])
@pytest.mark.parametrize("mutation", [None, "url", "tenant", "scope", "team", "bundle", "build", "unreviewed_build", "missing", "legacy"])
def test_pilot_ios_build_requires_complete_separate_configuration(mutation, build):
    validator = load_local_module("ios/Config/validate_pilot.py")
    values = {"PILOT_BUILD": "YES", "CONFIGURATION": "Release", "PRODUCT_BUNDLE_IDENTIFIER": "com.benedikt.Trainingsplan",
              "DEVELOPMENT_TEAM": "2SF7PV3WCD", "CURRENT_PROJECT_VERSION": build, "API_BASE_URL": "https://pft-pilot-synthetic-api.azurewebsites.net/api",
              "ENTRA_TENANT_ID": TENANT, "ENTRA_CLIENT_ID": CLIENT, "ENTRA_API_SCOPE": f"api://{AUDIENCE}/FoodAnalysis.Access",
              "ENTRA_REDIRECT_URI": "msauth.com.benedikt.Trainingsplan://auth"}
    for name in ("API_BASE_URL", "ENTRA_TENANT_ID", "ENTRA_CLIENT_ID", "ENTRA_API_SCOPE"):
        values["PILOT_" + name] = values[name]
    if mutation:
        field = {"url": "API_BASE_URL", "tenant": "ENTRA_TENANT_ID", "scope": "ENTRA_API_SCOPE", "team": "DEVELOPMENT_TEAM",
                 "bundle": "PRODUCT_BUNDLE_IDENTIFIER", "build": "CURRENT_PROJECT_VERSION", "unreviewed_build": "CURRENT_PROJECT_VERSION",
                 "missing": "PILOT_API_BASE_URL", "legacy": "PILOT_BUILD"}[mutation]
        values[field] = {"legacy": "NO", "unreviewed_build": "13"}.get(mutation, "")
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