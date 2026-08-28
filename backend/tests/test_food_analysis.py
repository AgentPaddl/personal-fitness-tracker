import json

import azure.functions as func
import pytest

from api.food_analysis import food_analysis
from gateway_client import GatewayClient, GatewayClientError


def _request(body: dict | bytes | None) -> func.HttpRequest:
    raw_body = body if isinstance(body, (bytes, type(None))) else json.dumps(body).encode()
    return func.HttpRequest(
        method="POST",
        url="/api/food-analysis",
        body=raw_body or b"",
        headers={"Content-Type": "application/json"},
    )


@pytest.fixture(autouse=True)
def _development_mode(monkeypatch):
    # This route has no production authentication yet; tests must opt in
    # explicitly, matching what is required in a real deployment.
    monkeypatch.setenv("APP_ENV", "development")


def test_food_analysis_rejects_missing_description():
    response = food_analysis(_request({}))

    assert response.status_code == 400
    assert json.loads(response.get_body())["error"]["code"] == "invalid_request"


def test_food_analysis_rejects_invalid_json():
    response = food_analysis(_request(b"not json"))

    assert response.status_code == 400
    assert json.loads(response.get_body())["error"]["code"] == "invalid_request"


def test_food_analysis_rejects_description_over_length_bound():
    response = food_analysis(_request({"food_description": "x" * 2001}))

    assert response.status_code == 400
    assert json.loads(response.get_body())["error"]["code"] == "invalid_request"


def test_food_analysis_denied_outside_development_mode(monkeypatch):
    monkeypatch.setenv("APP_ENV", "production")

    response = food_analysis(_request({"food_description": "an apple"}))

    assert response.status_code == 403
    assert json.loads(response.get_body())["error"]["code"] == "not_implemented"


def test_food_analysis_success_maps_to_public_contract(monkeypatch):
    gateway_result = {
        "estimate": {
            "food_name": "apple",
            "calories": 95.0,
            "protein_grams": 0.5,
            "carbohydrate_grams": 25.0,
            "fat_grams": 0.3,
            "confidence": 0.8,
            "warnings": [],
        }
    }

    def fake_analyze(self, food_description):
        assert food_description == "an apple"
        return gateway_result

    monkeypatch.setattr(GatewayClient, "analyze_food_text", fake_analyze)
    monkeypatch.setattr(GatewayClient, "close", lambda self: None)

    response = food_analysis(_request({"food_description": "an apple"}))

    assert response.status_code == 200
    assert json.loads(response.get_body()) == gateway_result


def test_food_analysis_drops_unknown_gateway_fields(monkeypatch):
    # The gateway response includes fields that must never reach the
    # client: provider/model identifiers, token usage, and debug data.
    gateway_result = {
        "estimate": {
            "food_name": "apple",
            "calories": 95.0,
            "protein_grams": 0.5,
            "carbohydrate_grams": 25.0,
            "fat_grams": 0.3,
            "confidence": 0.8,
            "warnings": [],
        },
        "provider": "fake",
        "model": "internal-test-model",
        "usage": {"prompt_tokens": 42, "completion_tokens": 7},
        "debug": {"trace_id": "abc-123"},
    }

    def fake_analyze(self, food_description):
        return gateway_result

    monkeypatch.setattr(GatewayClient, "analyze_food_text", fake_analyze)
    monkeypatch.setattr(GatewayClient, "close", lambda self: None)

    response = food_analysis(_request({"food_description": "an apple"}))
    body = json.loads(response.get_body())

    assert response.status_code == 200
    assert set(body.keys()) == {"estimate"}
    assert set(body["estimate"].keys()) == {
        "food_name",
        "calories",
        "protein_grams",
        "carbohydrate_grams",
        "fat_grams",
        "confidence",
        "warnings",
    }
    serialized = json.dumps(body).lower()
    for leaked_term in ("provider", "model", "usage", "debug", "trace_id", "token"):
        assert leaked_term not in serialized


def test_food_analysis_rejects_malformed_gateway_response(monkeypatch):
    def fake_analyze(self, food_description):
        return {"estimate": {"food_name": "apple"}}  # missing required fields

    monkeypatch.setattr(GatewayClient, "analyze_food_text", fake_analyze)
    monkeypatch.setattr(GatewayClient, "close", lambda self: None)

    response = food_analysis(_request({"food_description": "an apple"}))

    assert response.status_code == 502
    assert json.loads(response.get_body())["error"]["code"] == "gateway_invalid_response"


def test_food_analysis_normalizes_gateway_client_errors(monkeypatch):
    def fake_analyze(self, food_description):
        raise GatewayClientError("gateway_unreachable", 503, "The AI gateway is unreachable.")

    monkeypatch.setattr(GatewayClient, "analyze_food_text", fake_analyze)
    monkeypatch.setattr(GatewayClient, "close", lambda self: None)

    response = food_analysis(_request({"food_description": "an apple"}))

    assert response.status_code == 503
    body = json.loads(response.get_body())
    assert body["error"]["code"] == "gateway_unreachable"


def test_food_analysis_normalizes_gateway_timeout(monkeypatch):
    def fake_analyze(self, food_description):
        raise GatewayClientError("gateway_timeout", 504, "The AI gateway did not respond in time.")

    monkeypatch.setattr(GatewayClient, "analyze_food_text", fake_analyze)
    monkeypatch.setattr(GatewayClient, "close", lambda self: None)

    response = food_analysis(_request({"food_description": "an apple"}))

    assert response.status_code == 504
    assert json.loads(response.get_body())["error"]["code"] == "gateway_timeout"
