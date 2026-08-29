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


def test_validate_config_rejects_production_defaults():
    # Bare defaults resolve to APP_ENV=production with no API key, no
    # gateway service token, and a localhost gateway URL - none of that is
    # a valid production configuration, and it must fail closed rather than
    # silently "pass" as it would have before Phase 6 production hardening.
    with pytest.raises(config.ConfigError, match="BACKEND_API_KEY"):
        config.validate_config()


def test_validate_config_rejects_production_without_gateway_service_token(monkeypatch):
    monkeypatch.setenv("BACKEND_API_KEY", "test-api-key")
    with pytest.raises(config.ConfigError, match="GATEWAY_SERVICE_TOKEN"):
        config.validate_config()


def test_validate_config_rejects_production_localhost_gateway(monkeypatch):
    monkeypatch.setenv("BACKEND_API_KEY", "test-api-key")
    monkeypatch.setenv("GATEWAY_SERVICE_TOKEN", "test-service-token")
    monkeypatch.setenv("AI_GATEWAY_BASE_URL", "https://127.0.0.1:8000")
    with pytest.raises(config.ConfigError, match="localhost"):
        config.validate_config()


def test_validate_config_rejects_production_non_https_gateway(monkeypatch):
    monkeypatch.setenv("BACKEND_API_KEY", "test-api-key")
    monkeypatch.setenv("GATEWAY_SERVICE_TOKEN", "test-service-token")
    monkeypatch.setenv("AI_GATEWAY_BASE_URL", "http://gateway.internal.example")
    with pytest.raises(config.ConfigError, match="https"):
        config.validate_config()


def test_validate_config_passes_with_a_valid_production_configuration(monkeypatch):
    monkeypatch.setenv("BACKEND_API_KEY", "test-api-key")
    monkeypatch.setenv("GATEWAY_SERVICE_TOKEN", "test-service-token")
    monkeypatch.setenv("AI_GATEWAY_BASE_URL", "https://gateway.internal.example")

    config.validate_config()  # must not raise


def test_validate_config_passes_in_development_with_defaults(monkeypatch):
    monkeypatch.setenv("APP_ENV", "development")

    config.validate_config()  # must not raise: production-only checks don't apply
