import pytest

from app.config import Settings, get_settings


def test_unsupported_provider_rejected(monkeypatch):
    monkeypatch.setenv("AI_PROVIDER", "copilot_sdk")
    get_settings.cache_clear()
    try:
        with pytest.raises(ValueError):
            get_settings()
    finally:
        get_settings.cache_clear()
        monkeypatch.delenv("AI_PROVIDER", raising=False)


def test_default_provider_is_fake():
    settings = Settings()
    assert settings.ai_provider == "fake"
