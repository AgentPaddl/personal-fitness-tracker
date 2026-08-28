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


def test_analyze_food_text_maps_gateway_5xx_to_upstream_error():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(502, json={"error": {"code": "provider_unavailable"}})

    client = GatewayClient(base_url="http://gateway.test", transport=httpx.MockTransport(handler))

    with pytest.raises(GatewayClientError) as excinfo:
        client.analyze_food_text("an apple")

    assert excinfo.value.code == "gateway_upstream_error"
    assert excinfo.value.http_status == 502


def test_analyze_food_text_maps_gateway_4xx_to_rejected_request():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(422, json={"error": {"code": "request_invalid"}})

    client = GatewayClient(base_url="http://gateway.test", transport=httpx.MockTransport(handler))

    with pytest.raises(GatewayClientError) as excinfo:
        client.analyze_food_text("an apple")

    assert excinfo.value.code == "gateway_rejected_request"
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


def test_analyze_food_text_distinguishes_timeout_from_connectivity_failure():
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("timed out", request=request)

    client = GatewayClient(base_url="http://gateway.test", transport=httpx.MockTransport(handler))

    with pytest.raises(GatewayClientError) as excinfo:
        client.analyze_food_text("an apple")

    assert excinfo.value.code == "gateway_timeout"
    assert excinfo.value.http_status == 504


def test_analyze_food_text_enforces_real_client_timeout():
    # A genuinely slow transport must surface as our normalized timeout
    # error, not hang or raise a raw httpx exception.
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("simulated slow upstream", request=request)

    client = GatewayClient(
        base_url="http://gateway.test", timeout=0.05, transport=httpx.MockTransport(handler)
    )

    with pytest.raises(GatewayClientError) as excinfo:
        client.analyze_food_text("an apple")

    assert excinfo.value.code == "gateway_timeout"
