import httpx
import pytest

from gateway_client import GatewayClient, GatewayClientError


@pytest.mark.parametrize("failure", [None, "token", "identity", "flag"])
def test_api_only_uses_managed_identity_and_existing_assertion_once(monkeypatch, failure):
    import workload_identity

    monkeypatch.setenv("AI_API_ONLY_ENABLED", "invalid" if failure == "flag" else "true")
    monkeypatch.setenv("AI_PILOT_SIGNING_KEY", "synthetic-signing-key-not-for-use-0000")
    tokens, calls = [], []

    def token():
        tokens.append(True)
        if failure == "token":
            raise ValueError("private-credential-marker")
        return "synthetic-token"

    def handler(request):
        calls.append(request)
        return httpx.Response(200, json={"estimate": {}})

    monkeypatch.setattr(workload_identity, "gateway_access_token", token)
    client = GatewayClient(base_url="https://gateway.test", transport=httpx.MockTransport(handler),
                           service_token="synthetic", verified_identity=None if failure == "identity" else ("tenant", "person"),
                           operation_id="synthetic-operation")
    try:
        if failure:
            with pytest.raises(GatewayClientError) as caught:
                client.analyze_food_text("private-food")
            assert caught.value.code == "pilot_unavailable"
            assert "private" not in str(caught.value)
            assert not calls
        else:
            client.analyze_food_text("synthetic")
            assert len(calls) == len(tokens) == 1
            assert calls[0].headers["Authorization"] == "Bearer synthetic-token"
            assert calls[0].headers["X-Service-Token"] == "synthetic"
            assert calls[0].headers["X-Pilot-Authorization"]
    finally:
        client.close()


def test_workload_token_uses_only_configured_identity_and_audience(monkeypatch):
    import time
    from types import SimpleNamespace
    import workload_identity

    identifier = "00000000-0000-4000-8000-000000000001"
    for name, value in {"APP_ENV": "production", "AI_PILOT_ENABLED": "true", "EASY_AUTH_ENABLED": "true",
                        "GATEWAY_BACKEND_CLIENT_ID": identifier, "GATEWAY_WORKLOAD_AUDIENCE": identifier,
                        "AI_PILOT_TENANT_ID": identifier}.items():
        monkeypatch.setenv(name, value)
    selected, scopes = [], []

    def credential(client_id):
        selected.append(client_id)
        return SimpleNamespace(get_token=lambda scope: (scopes.append(scope) or SimpleNamespace(token="synthetic", expires_on=time.time() + 300)))

    monkeypatch.setattr(workload_identity, "_credential", credential)
    assert workload_identity.gateway_access_token() == "synthetic"
    assert selected == [identifier]
    assert scopes == [f"api://{identifier}/.default"]


def test_analyze_food_text_returns_gateway_json():
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/v1/food-analysis"
        return httpx.Response(200, json={"estimate": {"food_name": "apple"}})

    client = GatewayClient(base_url="http://gateway.test", transport=httpx.MockTransport(handler))

    result = client.analyze_food_text("an apple")

    assert result == {"estimate": {"food_name": "apple"}}


def test_analyze_food_refinement_sends_exact_allow_listed_payload_without_image():
    import json as jsonlib

    captured = {}
    payload = {
        "food_description": "rice bowl",
        "refinement": {
            "correction_text": "I ate half.",
            "current_estimate": {
                "food_name": "rice bowl",
                "calories": 620.0,
                "protein_grams": 24.0,
                "carbohydrate_grams": 86.0,
                "fat_grams": 18.0,
                "confidence": 0.72,
                "warnings": [],
                "assumptions": [],
            },
            "source_kind": "text",
            "iteration": 1,
        },
    }

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/v1/food-analysis"
        captured["body"] = jsonlib.loads(request.content)
        return httpx.Response(200, json={"estimate": {"food_name": "rice bowl"}})

    client = GatewayClient(base_url="http://gateway.test", transport=httpx.MockTransport(handler))

    result = client.analyze_food_refinement(payload)

    assert captured["body"] == payload
    assert "image" not in captured["body"]
    assert result == {"estimate": {"food_name": "rice bowl"}}


def test_analyze_food_refinement_uses_existing_error_normalization():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(504, json={"error": {"code": "provider_timeout"}})

    client = GatewayClient(base_url="http://gateway.test", transport=httpx.MockTransport(handler))

    with pytest.raises(GatewayClientError) as excinfo:
        client.analyze_food_refinement({"refinement": {}})

    assert excinfo.value.code == "gateway_timeout"
    assert excinfo.value.http_status == 504


def test_analyze_food_text_preserves_provider_timeout_as_504(monkeypatch):
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            504, json={"error": {"code": "provider_timeout", "message": "upstream detail"}}
        )

    client = GatewayClient(base_url="http://gateway.test", transport=httpx.MockTransport(handler))

    with pytest.raises(GatewayClientError) as excinfo:
        client.analyze_food_text("an apple")

    assert excinfo.value.code == "gateway_timeout"
    assert excinfo.value.http_status == 504
    assert "upstream detail" not in excinfo.value.message


def test_analyze_food_text_preserves_provider_rate_limited_as_429():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            429, json={"error": {"code": "provider_rate_limited", "message": "upstream detail"}}
        )

    client = GatewayClient(base_url="http://gateway.test", transport=httpx.MockTransport(handler))

    with pytest.raises(GatewayClientError) as excinfo:
        client.analyze_food_text("an apple")

    assert excinfo.value.code == "gateway_rate_limited"
    assert excinfo.value.http_status == 429
    assert "upstream detail" not in excinfo.value.message


def test_analyze_food_text_preserves_provider_unavailable_as_503():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            502, json={"error": {"code": "provider_unavailable", "message": "upstream detail"}}
        )

    client = GatewayClient(base_url="http://gateway.test", transport=httpx.MockTransport(handler))

    with pytest.raises(GatewayClientError) as excinfo:
        client.analyze_food_text("an apple")

    assert excinfo.value.code == "gateway_service_unavailable"
    assert excinfo.value.http_status == 503
    assert "upstream detail" not in excinfo.value.message


def test_analyze_food_text_normalizes_unknown_upstream_code_to_502():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            502, json={"error": {"code": "provider_output_invalid", "message": "upstream detail"}}
        )

    client = GatewayClient(base_url="http://gateway.test", transport=httpx.MockTransport(handler))

    with pytest.raises(GatewayClientError) as excinfo:
        client.analyze_food_text("an apple")

    assert excinfo.value.code == "gateway_upstream_error"
    assert excinfo.value.http_status == 502
    assert "upstream detail" not in excinfo.value.message


def test_analyze_food_text_normalizes_untrusted_client_error_to_502():
    # request_invalid is a real gateway code, but it is not one of the
    # whitelisted status-preserving codes, so it must not leak through.
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(422, json={"error": {"code": "request_invalid"}})

    client = GatewayClient(base_url="http://gateway.test", transport=httpx.MockTransport(handler))

    with pytest.raises(GatewayClientError) as excinfo:
        client.analyze_food_text("an apple")

    assert excinfo.value.code == "gateway_upstream_error"
    assert excinfo.value.http_status == 502


def test_analyze_food_text_normalizes_malformed_error_body_to_502():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(500, content=b"not json", headers={"content-type": "text/plain"})

    client = GatewayClient(base_url="http://gateway.test", transport=httpx.MockTransport(handler))

    with pytest.raises(GatewayClientError) as excinfo:
        client.analyze_food_text("an apple")

    assert excinfo.value.code == "gateway_upstream_error"
    assert excinfo.value.http_status == 502


def test_analyze_food_text_maps_non_json_response_to_invalid_response():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, content=b"not json", headers={"content-type": "text/plain"})

    client = GatewayClient(base_url="http://gateway.test", transport=httpx.MockTransport(handler))

    with pytest.raises(GatewayClientError) as excinfo:
        client.analyze_food_text("an apple")

    assert excinfo.value.code == "gateway_invalid_response"


def test_analyze_food_text_maps_non_object_json_to_invalid_response():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=["not", "an", "object"])

    client = GatewayClient(base_url="http://gateway.test", transport=httpx.MockTransport(handler))

    with pytest.raises(GatewayClientError) as excinfo:
        client.analyze_food_text("an apple")

    assert excinfo.value.code == "gateway_invalid_response"


def test_analyze_food_text_raises_on_transport_error():
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("boom", request=request)

    client = GatewayClient(base_url="http://gateway.test", transport=httpx.MockTransport(handler))

    with pytest.raises(GatewayClientError) as excinfo:
        client.analyze_food_text("an apple")

    assert excinfo.value.code == "gateway_unreachable"
    assert excinfo.value.http_status == 503


def test_analyze_food_text_maps_transport_timeout_to_gateway_timeout():
    # Simulates httpx raising a timeout exception client-side (e.g. the
    # gateway never responded). This is a mocked exception, not a real
    # elapsed-time measurement; real timeout behavior against a live
    # process is covered by ai-gateway/tests/test_smoke_process.py.
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("timed out", request=request)

    client = GatewayClient(base_url="http://gateway.test", transport=httpx.MockTransport(handler))

    with pytest.raises(GatewayClientError) as excinfo:
        client.analyze_food_text("an apple")

    assert excinfo.value.code == "gateway_timeout"
    assert excinfo.value.http_status == 504


def test_analyze_food_image_sends_base64_payload_and_maps_gateway_response():
    import base64
    import json as jsonlib

    captured = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["body"] = jsonlib.loads(request.content)
        return httpx.Response(200, json={"estimate": {"food_name": "pasta"}})

    client = GatewayClient(base_url="http://gateway.test", transport=httpx.MockTransport(handler))

    result = client.analyze_food_image(b"raw image bytes", "image/jpeg", food_description="a bowl of pasta")

    assert result == {"estimate": {"food_name": "pasta"}}
    assert captured["body"]["food_description"] == "a bowl of pasta"
    assert captured["body"]["image"]["media_type"] == "image/jpeg"
    assert base64.b64decode(captured["body"]["image"]["data_base64"]) == b"raw image bytes"


def test_analyze_food_image_omits_food_description_when_none():
    import json as jsonlib

    captured = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["body"] = jsonlib.loads(request.content)
        return httpx.Response(200, json={"estimate": {"food_name": "pasta"}})

    client = GatewayClient(base_url="http://gateway.test", transport=httpx.MockTransport(handler))

    client.analyze_food_image(b"raw image bytes", "image/jpeg")

    assert "food_description" not in captured["body"]


def test_analyze_food_image_normalizes_gateway_error():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(504, json={"error": {"code": "provider_timeout", "message": "detail"}})

    client = GatewayClient(base_url="http://gateway.test", transport=httpx.MockTransport(handler))

    with pytest.raises(GatewayClientError) as excinfo:
        client.analyze_food_image(b"raw image bytes", "image/jpeg")

    assert excinfo.value.code == "gateway_timeout"
    assert excinfo.value.http_status == 504


def test_analyze_food_text_maps_service_saturated_to_gateway_saturated_503():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            503,
            json={"error": {"code": "service_saturated", "message": "upstream detail"}},
            headers={"Retry-After": "2"},
        )

    client = GatewayClient(base_url="http://gateway.test", transport=httpx.MockTransport(handler))

    with pytest.raises(GatewayClientError) as excinfo:
        client.analyze_food_text("an apple")

    assert excinfo.value.code == "gateway_saturated"
    assert excinfo.value.http_status == 503
    assert excinfo.value.retry_after_seconds == 2
    assert "upstream detail" not in excinfo.value.message


def test_analyze_food_text_drops_out_of_bounds_retry_after():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            503,
            json={"error": {"code": "service_saturated"}},
            headers={"Retry-After": "9999"},
        )

    client = GatewayClient(base_url="http://gateway.test", transport=httpx.MockTransport(handler))

    with pytest.raises(GatewayClientError) as excinfo:
        client.analyze_food_text("an apple")

    assert excinfo.value.retry_after_seconds is None


def test_analyze_food_text_drops_malformed_retry_after():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            503,
            json={"error": {"code": "service_saturated"}},
            headers={"Retry-After": "not-a-number"},
        )

    client = GatewayClient(base_url="http://gateway.test", transport=httpx.MockTransport(handler))

    with pytest.raises(GatewayClientError) as excinfo:
        client.analyze_food_text("an apple")

    assert excinfo.value.retry_after_seconds is None
