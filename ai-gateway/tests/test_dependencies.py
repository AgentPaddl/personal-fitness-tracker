"""Proves the gateway selects FakeProvider vs GitHubCopilotProvider purely
from server-side configuration (AI_PROVIDER), with no public API involvement.
"""

from __future__ import annotations

import asyncio
import pytest

from app.config import get_settings
from app.dependencies import get_provider
from app.providers.fake import FakeProvider
from app.providers.github_copilot import GitHubCopilotProvider


def test_production_azure_post_is_blocked_without_readiness_check(monkeypatch):
    from fastapi.testclient import TestClient
    from app.main import create_app
    from app.providers import openai_api

    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.setenv("GATEWAY_DEV_AUTH_BYPASS", "false")
    monkeypatch.setenv("GATEWAY_SERVICE_TOKEN", "dummy-service-token")
    monkeypatch.setenv("AI_PROVIDER", "azure_openai")
    monkeypatch.setenv("AI_PROVIDER_TIMEOUT_SECONDS", "90")
    monkeypatch.setenv("AZURE_OPENAI_ENDPOINT", "https://example.openai.azure.com")
    monkeypatch.setenv("AZURE_OPENAI_API_KEY", "not-a-real-key")
    monkeypatch.setenv("AZURE_OPENAI_MODEL_ROUTES_JSON", '{"food_text_v1":"text-route","food_image_v1":"image-route"}')
    monkeypatch.setattr(openai_api, "AsyncOpenAI", lambda *args, **kwargs: pytest.fail("Azure client constructed"))
    monkeypatch.setattr(GitHubCopilotProvider, "__init__", lambda *args, **kwargs: pytest.fail("Copilot fallback"))

    with TestClient(create_app(), raise_server_exceptions=False) as client:
        response = client.post(
            "/v1/food-analysis", json={"food_description": "synthetic guard input"},
            headers={"X-Service-Token": "dummy-service-token"},
        )
    assert response.status_code == 500
    assert response.json()["error"]["code"] == "internal_error"
    assert "synthetic guard input" not in response.text
    assert "azure" not in response.text
    assert get_provider.cache_info().currsize == 0


def test_azure_selection_is_explicit_and_has_no_copilot_fallback(monkeypatch):
    from app.providers.openai_api import AzureOpenAIProvider

    monkeypatch.setenv("APP_ENV", "test")
    monkeypatch.setenv("AI_PROVIDER", "azure_openai")
    monkeypatch.setenv("AZURE_OPENAI_ENDPOINT", "https://example.openai.azure.com")
    monkeypatch.setenv("AZURE_OPENAI_API_KEY", "not-a-real-key")
    monkeypatch.setenv("AZURE_OPENAI_MODEL_ROUTES_JSON", '{"food_text_v1":"text-route","food_image_v1":"image-route"}')
    monkeypatch.setattr(GitHubCopilotProvider, "__init__", lambda *args, **kwargs: pytest.fail("Copilot constructed"))
    provider = get_provider()
    try:
        assert isinstance(provider, AzureOpenAIProvider)
    finally:
        asyncio.run(provider.aclose())
    get_settings.cache_clear()
    get_provider.cache_clear()
    monkeypatch.setenv("AZURE_OPENAI_MODEL_ROUTES_JSON", "invalid")
    with pytest.raises(ValueError):
        get_provider()


def test_ai_provider_fake_selects_fake_provider(monkeypatch):
    monkeypatch.setenv("APP_ENV", "development")
    monkeypatch.setenv("AI_PROVIDER", "fake")
    get_settings.cache_clear()
    get_provider.cache_clear()

    assert isinstance(get_provider(), FakeProvider)


def test_ai_provider_copilot_selects_github_copilot_provider(monkeypatch):
    monkeypatch.setenv("APP_ENV", "development")
    monkeypatch.setenv("AI_PROVIDER", "copilot")
    monkeypatch.setenv("COPILOT_MODEL_ROUTES_JSON", '{"food_text_v1": "gpt-5", "food_image_v1": "gpt-5-mini"}')
    get_settings.cache_clear()
    get_provider.cache_clear()

    try:
        provider = get_provider()
        assert isinstance(provider, GitHubCopilotProvider)
    finally:
        get_settings.cache_clear()
        get_provider.cache_clear()
