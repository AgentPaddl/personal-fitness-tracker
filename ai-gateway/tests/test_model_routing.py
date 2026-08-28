"""Proves model/provider routing configuration is independent of the public contract."""

from __future__ import annotations

from fastapi.testclient import TestClient

from app.config import get_settings
from app.dependencies import get_provider
from app.main import create_app

_EXPECTED_ESTIMATE_KEYS = {
    "food_name",
    "calories",
    "protein_grams",
    "carbohydrate_grams",
    "fat_grams",
    "confidence",
    "warnings",
}


def test_changing_model_purpose_does_not_change_public_contract(monkeypatch):
    monkeypatch.setenv("APP_ENV", "development")
    monkeypatch.setenv("GATEWAY_DEV_AUTH_BYPASS", "true")
    monkeypatch.setenv("AI_PROVIDER", "fake")
    monkeypatch.setenv("FOOD_TEXT_MODEL_PURPOSE", "food_text_experimental_v2")
    get_settings.cache_clear()
    get_provider.cache_clear()

    client = TestClient(create_app())
    response = client.post("/v1/food-analysis", json={"food_description": "banana"})

    assert response.status_code == 200
    body = response.json()
    assert set(body.keys()) == {"estimate"}
    assert set(body["estimate"].keys()) == _EXPECTED_ESTIMATE_KEYS

    serialized = str(body).lower()
    assert "model" not in serialized
    assert "purpose" not in serialized
    assert "food_text_experimental_v2" not in serialized


def test_default_model_purpose_is_configurable_and_not_public(client):
    response = client.post("/v1/food-analysis", json={"food_description": "banana"})

    assert response.status_code == 200
    settings = get_settings()
    assert settings.food_text_model_purpose == "food_text_v1"
    assert "food_text_v1" not in str(response.json())
