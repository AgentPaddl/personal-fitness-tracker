import json

import azure.functions as func
import httpx
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


def test_food_analysis_rejects_missing_description(monkeypatch):
    response = food_analysis(_request({}))

    assert response.status_code == 400
    assert json.loads(response.get_body())["error"]["code"] == "invalid_request"


def test_food_analysis_rejects_invalid_json():
    response = food_analysis(_request(b"not json"))

    assert response.status_code == 400
    assert json.loads(response.get_body())["error"]["code"] == "invalid_request"


def test_food_analysis_success_forwards_gateway_response(monkeypatch):
    fake_result = {
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
        return fake_result

    monkeypatch.setattr(GatewayClient, "analyze_food_text", fake_analyze)
    monkeypatch.setattr(GatewayClient, "close", lambda self: None)

    response = food_analysis(_request({"food_description": "an apple"}))

    assert response.status_code == 200
    assert json.loads(response.get_body()) == fake_result


def test_food_analysis_normalizes_gateway_errors(monkeypatch):
    def fake_analyze(self, food_description):
        raise GatewayClientError("gateway_unreachable")

    monkeypatch.setattr(GatewayClient, "analyze_food_text", fake_analyze)
    monkeypatch.setattr(GatewayClient, "close", lambda self: None)

    response = food_analysis(_request({"food_description": "an apple"}))

    assert response.status_code == 502
    body = json.loads(response.get_body())
    assert body["error"]["code"] == "gateway_error"
    assert "gateway_unreachable" not in json.dumps(body)
