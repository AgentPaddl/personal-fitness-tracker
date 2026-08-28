import pytest

import config


def test_default_app_env_is_production():
    assert config.get_app_env() == "production"
    assert config.is_development_mode() is False


def test_development_mode_requires_explicit_app_env(monkeypatch):
    monkeypatch.setenv("APP_ENV", "development")
    assert config.is_development_mode() is True


def test_validate_config_rejects_unsupported_app_env(monkeypatch):
    monkeypatch.setenv("APP_ENV", "staging")
    with pytest.raises(config.ConfigError):
        config.validate_config()


def test_validate_config_rejects_invalid_gateway_url(monkeypatch):
    monkeypatch.setenv("AI_GATEWAY_BASE_URL", "not-a-url")
    with pytest.raises(config.ConfigError):
        config.validate_config()


def test_validate_config_rejects_out_of_bounds_timeout(monkeypatch):
    monkeypatch.setenv("AI_GATEWAY_TIMEOUT_SECONDS", "0")
    with pytest.raises(config.ConfigError):
        config.validate_config()


def test_validate_config_passes_with_defaults():
    config.validate_config()  # must not raise
