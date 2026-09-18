import base64
import json

import pytest

from security import pilot_identity

TENANT = "00000000-0000-4000-8000-000000000001"
PERSON = "00000000-0000-4000-8000-000000000002"
CLIENT = "00000000-0000-4000-8000-000000000003"


@pytest.fixture
def identity_headers(monkeypatch):
    config = {
        "EASY_AUTH_ENABLED": "true", "AI_PILOT_TENANT_ID": TENANT,
        "AI_PILOT_AUDIENCE": "synthetic-api", "AI_PILOT_CLIENT_ID": CLIENT,
        "AI_PILOT_ISSUER": f"https://login.microsoftonline.com/{TENANT}/v2.0",
        "AI_PILOT_SCOPE": "Analysis.Invoke",
        "AI_PILOT_ALLOWLIST_JSON": json.dumps([{"tid": TENANT, "oid": PERSON}]),
    }
    for name, value in config.items():
        monkeypatch.setenv(name, value)
    return _headers()


def _headers(**changes):
    claims = {"tid": TENANT, "oid": PERSON, "aud": "synthetic-api", "azp": CLIENT,
              "iss": f"https://login.microsoftonline.com/{TENANT}/v2.0", "scp": "Analysis.Invoke"}
    claims.update(changes)
    principal = {"auth_typ": "aad", "claims": [{"typ": name, "val": value} for name, value in claims.items()]}
    return {"X-MS-CLIENT-PRINCIPAL-ID": PERSON,
            "X-MS-CLIENT-PRINCIPAL": base64.b64encode(json.dumps(principal).encode()).decode()}


def test_platform_claims_and_allowlist(identity_headers):
    assert pilot_identity(identity_headers) == (TENANT, PERSON)


@pytest.mark.parametrize("changes", [{"tid": CLIENT}, {"oid": CLIENT}, {"aud": "other"},
                                      {"azp": "other"}, {"appid": "other"}, {"scp": "Other"},
                                      {"iss": "https://example.invalid"}])
def test_foreign_or_conflicting_claims(identity_headers, changes):
    with pytest.raises(ValueError):
        pilot_identity(_headers(**changes))


@pytest.mark.parametrize("setting", ["EASY_AUTH_ENABLED", "AI_PILOT_ALLOWLIST_JSON", "AI_PILOT_SCOPE"])
def test_missing_trust_configuration(identity_headers, monkeypatch, setting):
    monkeypatch.delenv(setting)
    with pytest.raises(ValueError):
        pilot_identity(identity_headers)


def test_bare_claimed_user_id_is_not_identity(identity_headers):
    with pytest.raises(ValueError):
        pilot_identity({"X-MS-CLIENT-PRINCIPAL-ID": PERSON, "X-Pilot-Identity": PERSON})


def test_empty_allowlist_and_duplicate_identity_claims(identity_headers, monkeypatch):
    principal = json.loads(base64.b64decode(identity_headers["X-MS-CLIENT-PRINCIPAL"]))
    principal["claims"].append({"typ": "http://schemas.microsoft.com/identity/claims/objectidentifier", "val": PERSON})
    duplicate = {**identity_headers, "X-MS-CLIENT-PRINCIPAL": base64.b64encode(json.dumps(principal).encode()).decode()}
    with pytest.raises(ValueError):
        pilot_identity(duplicate)
    monkeypatch.setenv("AI_PILOT_ALLOWLIST_JSON", "[]")
    with pytest.raises(ValueError):
        pilot_identity(identity_headers)


def test_pilot_missing_operation_is_rejected_before_gateway(identity_headers, monkeypatch):
    import azure.functions as func
    from api.food_analysis import food_analysis
    from gateway_client import GatewayClient

    monkeypatch.setenv("AI_PILOT_ENABLED", "true")
    monkeypatch.setenv("APP_ENV", "development")
    monkeypatch.setattr(GatewayClient, "__init__", lambda *args, **kwargs: pytest.fail("Unexpected gateway construction"))
    response = food_analysis(func.HttpRequest(method="POST", url="/api/food-analysis", headers=identity_headers,
                                             body=b'{"food_description":"synthetic"}'))
    assert response.status_code == 400
    assert json.loads(response.get_body())["error"]["code"] == "operation_required"


@pytest.mark.parametrize("reason", ["deep_json", "missing_platform", "mismatched_id", "missing_scope"])
def test_invalid_pilot_identity_is_normalized_before_gateway(identity_headers, monkeypatch, caplog, reason):
    import azure.functions as func
    from api.food_analysis import food_analysis
    from gateway_client import GatewayClient

    monkeypatch.setenv("AI_PILOT_ENABLED", "true")
    monkeypatch.setenv("APP_ENV", "development")
    monkeypatch.setattr(GatewayClient, "__init__", lambda *args, **kwargs: pytest.fail("Unexpected gateway construction"))
    headers = dict(identity_headers)
    if reason == "deep_json":
        headers["X-MS-CLIENT-PRINCIPAL"] = base64.b64encode(b"[" * 3000 + b"]" * 3000).decode()
    elif reason == "missing_platform":
        monkeypatch.setenv("EASY_AUTH_ENABLED", "false")
    elif reason == "mismatched_id":
        headers["X-MS-CLIENT-PRINCIPAL-ID"] = CLIENT
    else:
        headers = _headers(scp="")
    response = food_analysis(func.HttpRequest(method="POST", url="/api/food-analysis", headers=headers,
                                             body=b'{"food_description":"synthetic"}'))
    assert response.status_code == 403
    assert json.loads(response.get_body())["error"]["code"] == "pilot_forbidden"
    assert headers["X-MS-CLIENT-PRINCIPAL"] not in caplog.text
    assert PERSON not in caplog.text