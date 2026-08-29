"""Proves the gateway selects FakeProvider vs GitHubCopilotProvider purely
from server-side configuration (AI_PROVIDER), with no public API involvement.
"""

from __future__ import annotations

from app.config import get_settings
from app.dependencies import get_provider
from app.providers.fake import FakeProvider
from app.providers.github_copilot import GitHubCopilotProvider


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
