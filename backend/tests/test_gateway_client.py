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


def test_analyze_food_text_raises_on_http_error():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(504, json={"error": {"code": "provider_timeout"}})

    client = GatewayClient(base_url="http://gateway.test", transport=httpx.MockTransport(handler))

    with pytest.raises(GatewayClientError) as excinfo:
        client.analyze_food_text("an apple")

    assert excinfo.value.code == "gateway_http_504"


def test_analyze_food_text_raises_on_transport_error():
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("boom", request=request)

    client = GatewayClient(base_url="http://gateway.test", transport=httpx.MockTransport(handler))

    with pytest.raises(GatewayClientError) as excinfo:
        client.analyze_food_text("an apple")

    assert excinfo.value.code == "gateway_unreachable"
