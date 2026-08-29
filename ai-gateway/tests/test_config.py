import pytest

from app.config import Settings, get_settings


def test_default_settings_fail_closed():
    # No env vars: APP_ENV defaults to "production" and AI_PROVIDER defaults
    # to "fake", which is an intentionally invalid combination (fake must
    # never silently become the production provider).
    with pytest.raises(ValueError):
        Settings().validate()


def test_dev_auth_bypass_rejected_outside_development():
    settings = Settings(app_env="production", gateway_dev_auth_bypass=True, ai_provider="fake")
    with pytest.raises(ValueError, match="GATEWAY_DEV_AUTH_BYPASS"):
        settings.validate()


def test_fake_provider_rejected_in_production():
    settings = Settings(app_env="production", gateway_dev_auth_bypass=False, ai_provider="fake")
    with pytest.raises(ValueError, match="AI_PROVIDER=fake"):
        settings.validate()


def test_unsupported_provider_rejected():
    settings = Settings(app_env="development", gateway_dev_auth_bypass=True, ai_provider="copilot_sdk")
    with pytest.raises(ValueError):
        settings.validate()


def test_unsupported_app_env_rejected():
    settings = Settings(app_env="staging")
    with pytest.raises(ValueError):
        settings.validate()


def test_timeout_out_of_bounds_rejected():
    settings = Settings(
        app_env="development",
        gateway_dev_auth_bypass=True,
        ai_provider="fake",
        ai_provider_timeout_seconds=0,
    )
    with pytest.raises(ValueError):
        settings.validate()


def test_valid_development_configuration_passes():
    settings = Settings(app_env="development", gateway_dev_auth_bypass=True, ai_provider="fake")
    settings.validate()  # must not raise


def test_get_settings_uses_env_overrides(monkeypatch):
    monkeypatch.setenv("APP_ENV", "development")
    monkeypatch.setenv("GATEWAY_DEV_AUTH_BYPASS", "true")
    monkeypatch.setenv("AI_PROVIDER", "fake")
    get_settings.cache_clear()
    try:
        settings = get_settings()
        assert settings.app_env == "development"
        assert settings.gateway_dev_auth_bypass is True
    finally:
        get_settings.cache_clear()


def test_copilot_provider_requires_model_routes():
    settings = Settings(app_env="development", ai_provider="copilot", copilot_model_routes_json="")
    with pytest.raises(ValueError, match="COPILOT_MODEL_ROUTES_JSON"):
        settings.validate()


def test_copilot_provider_rejects_malformed_json():
    settings = Settings(app_env="development", ai_provider="copilot", copilot_model_routes_json="not json")
    with pytest.raises(ValueError, match="COPILOT_MODEL_ROUTES_JSON"):
        settings.validate()


def test_copilot_provider_requires_route_for_configured_purpose():
    settings = Settings(
        app_env="development",
        ai_provider="copilot",
        copilot_model_routes_json='{"some_other_purpose": "gpt-5"}',
    )
    with pytest.raises(ValueError, match="food_text_v1"):
        settings.validate()


def test_copilot_provider_valid_configuration_passes():
    settings = Settings(
        app_env="development",
        ai_provider="copilot",
        copilot_model_routes_json='{"food_text_v1": "gpt-5", "food_image_v1": "gpt-5-mini"}',
    )
    settings.validate()  # must not raise
    assert settings.copilot_model_routes() == {"food_text_v1": "gpt-5", "food_image_v1": "gpt-5-mini"}


def test_copilot_provider_requires_route_for_image_purpose():
    settings = Settings(
        app_env="development",
        ai_provider="copilot",
        copilot_model_routes_json='{"food_text_v1": "gpt-5"}',
    )
    with pytest.raises(ValueError, match="food_image_v1"):
        settings.validate()


def test_copilot_model_routes_never_silently_defaults():
    settings = Settings(ai_provider="copilot", copilot_model_routes_json="")
    with pytest.raises(ValueError):
        settings.copilot_model_routes()


def test_copilot_model_routes_rejects_blank_routing_key():
    settings = Settings(
        ai_provider="copilot", copilot_model_routes_json='{"": "gpt-5"}'
    )
    with pytest.raises(ValueError, match="empty or whitespace-only"):
        settings.copilot_model_routes()


def test_copilot_model_routes_rejects_whitespace_only_routing_key():
    settings = Settings(
        ai_provider="copilot", copilot_model_routes_json='{"   ": "gpt-5"}'
    )
    with pytest.raises(ValueError, match="empty or whitespace-only"):
        settings.copilot_model_routes()


def test_copilot_model_routes_rejects_blank_model_id():
    settings = Settings(
        ai_provider="copilot", copilot_model_routes_json='{"food_text_v1": ""}'
    )
    with pytest.raises(ValueError, match="empty or whitespace-only"):
        settings.copilot_model_routes()


def test_copilot_model_routes_rejects_whitespace_only_model_id():
    settings = Settings(
        ai_provider="copilot", copilot_model_routes_json='{"food_text_v1": "   "}'
    )
    with pytest.raises(ValueError, match="empty or whitespace-only"):
        settings.copilot_model_routes()


def test_copilot_model_routes_rejects_blank_values_at_settings_validate_time():
    # The blank-model-id case must also fail closed during full Settings
    # validation, not only when copilot_model_routes() happens to be called.
    settings = Settings(
        app_env="development",
        ai_provider="copilot",
        copilot_model_routes_json='{"food_text_v1": "   "}',
    )
    with pytest.raises(ValueError, match="empty or whitespace-only"):
        settings.validate()


def test_copilot_model_routes_strips_valid_surrounding_whitespace():
    # Existing valid routing behavior is preserved: surrounding whitespace
    # around otherwise-valid keys/values is trimmed, not rejected.
    settings = Settings(
        ai_provider="copilot", copilot_model_routes_json='{"  food_text_v1  ": "  gpt-5  "}'
    )
    assert settings.copilot_model_routes() == {"food_text_v1": "gpt-5"}
