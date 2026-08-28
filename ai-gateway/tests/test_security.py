"""Tests proving the gateway's authentication fails closed by default."""

from __future__ import annotations

from fastapi.testclient import TestClient

from app.main import create_app


def test_v1_route_denies_by_default_with_no_configuration():
    # No env vars set at all: APP_ENV defaults to "production" and
    # GATEWAY_DEV_AUTH_BYPASS defaults to false.
    response = TestClient(create_app(), raise_server_exceptions=False).post(
        "/v1/food-analysis", json={"food_description": "apple"}
    )

    assert response.status_code in (401, 500)
    body = response.json()
    assert body["error"]["code"] in ("authentication_required", "internal_error")
    # Never leak why it failed beyond the normalized code/message.
    assert "traceback" not in str(body).lower()


def test_v1_route_denies_when_app_env_is_development_but_bypass_is_off(monkeypatch):
    monkeypatch.setenv("APP_ENV", "development")
    monkeypatch.setenv("GATEWAY_DEV_AUTH_BYPASS", "false")
    monkeypatch.setenv("AI_PROVIDER", "fake")

    from app.config import get_settings
    from app.dependencies import get_provider

    get_settings.cache_clear()
    get_provider.cache_clear()

    response = TestClient(create_app(), raise_server_exceptions=False).post(
        "/v1/food-analysis", json={"food_description": "apple"}
    )

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "authentication_required"


def test_v1_route_denies_when_bypass_is_on_but_app_env_is_production(monkeypatch):
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.setenv("GATEWAY_DEV_AUTH_BYPASS", "true")

    from app.config import get_settings
    from app.dependencies import get_provider

    get_settings.cache_clear()
    get_provider.cache_clear()

    # Settings.validate() rejects this combination outright; the app must
    # not silently ignore the bypass flag in production.
    response = TestClient(create_app(), raise_server_exceptions=False).post(
        "/v1/food-analysis", json={"food_description": "apple"}
    )

    assert response.status_code == 500
    assert response.json()["error"]["code"] == "internal_error"


def test_v1_route_succeeds_only_with_explicit_dev_bypass(client):
    response = client.post("/v1/food-analysis", json={"food_description": "apple"})
    assert response.status_code == 200
