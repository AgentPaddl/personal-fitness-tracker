"""Server-side gateway configuration, read from environment variables only."""

from __future__ import annotations

from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

#: Providers implemented today. "copilot_sdk" is reserved for the future
#: production adapter and is intentionally not accepted yet.
SUPPORTED_PROVIDERS = frozenset({"fake"})

#: Fail-closed by default: only "development" may ever enable the dev auth
#: bypass. "test" is for the automated test suite; "production" is the
#: default so any unset/misconfigured deployment fails closed.
ALLOWED_APP_ENVS = frozenset({"development", "test", "production"})

_MIN_TIMEOUT_SECONDS = 0.1
_MAX_TIMEOUT_SECONDS = 120.0


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="", extra="ignore")

    # Defaults to the strictest environment so a missing/misconfigured
    # deployment fails closed rather than silently behaving like dev.
    app_env: str = Field(default="production", alias="APP_ENV")

    ai_provider: str = Field(default="fake", alias="AI_PROVIDER")
    ai_provider_timeout_seconds: float = Field(default=10.0, alias="AI_PROVIDER_TIMEOUT_SECONDS")

    # Server-side, opaque model-routing key for the food-text generation
    # purpose. Never exposed through the public API; changing it must not
    # require any change to the public request/response contract.
    food_text_model_purpose: str = Field(default="food_text_v1", alias="FOOD_TEXT_MODEL_PURPOSE")

    # Development-only bypass, off by default. Even when true, it only takes
    # effect if app_env == "development" (enforced in app.security).
    gateway_dev_auth_bypass: bool = Field(default=False, alias="GATEWAY_DEV_AUTH_BYPASS")

    def validate(self) -> None:
        if self.app_env not in ALLOWED_APP_ENVS:
            raise ValueError(
                f"Unsupported APP_ENV '{self.app_env}'. Supported values: {sorted(ALLOWED_APP_ENVS)}."
            )

        if self.gateway_dev_auth_bypass and self.app_env != "development":
            raise ValueError(
                "GATEWAY_DEV_AUTH_BYPASS may only be enabled when APP_ENV=development."
            )

        if self.ai_provider not in SUPPORTED_PROVIDERS:
            raise ValueError(
                f"Unsupported AI_PROVIDER '{self.ai_provider}'. "
                f"Supported values: {sorted(SUPPORTED_PROVIDERS)}."
            )

        if self.ai_provider == "fake" and self.app_env == "production":
            # FakeProvider must never silently become the production
            # provider; production has no real provider implemented yet.
            raise ValueError(
                "AI_PROVIDER=fake is not allowed when APP_ENV=production. "
                "No production provider is implemented yet."
            )

        if not (_MIN_TIMEOUT_SECONDS <= self.ai_provider_timeout_seconds <= _MAX_TIMEOUT_SECONDS):
            raise ValueError(
                f"AI_PROVIDER_TIMEOUT_SECONDS must be between {_MIN_TIMEOUT_SECONDS} "
                f"and {_MAX_TIMEOUT_SECONDS}."
            )

        if not self.food_text_model_purpose.strip():
            raise ValueError("FOOD_TEXT_MODEL_PURPOSE must not be blank.")


@lru_cache
def get_settings() -> Settings:
    settings = Settings()
    settings.validate()
    return settings
