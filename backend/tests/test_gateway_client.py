import httpx
import pytest

from gateway_client import GatewayClient, GatewayClientError


def test_analyze_food_text_returns_gateway_json():
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/v1/food-analysis"
        return httpx.Response(200, json={"estimate": {"food_name": "apple"}})

    client = GatewayClient(base_url="http://gateway.test", transport=httpx.MockTransport(handler))

    result = client.analyze_food_text("an apple")

    assert result == {"estimate": {"food_name": "apple"}}


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
