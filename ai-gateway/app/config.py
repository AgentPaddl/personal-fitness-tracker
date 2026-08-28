"""Server-side gateway configuration, read from environment variables only."""

from __future__ import annotations

from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

#: Providers implemented today. "copilot_sdk" is reserved for the future
#: production adapter and is intentionally not accepted yet.
SUPPORTED_PROVIDERS = frozenset({"fake"})


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="", extra="ignore")

    ai_provider: str = Field(default="fake", alias="AI_PROVIDER")
    ai_provider_timeout_seconds: float = Field(default=10.0, alias="AI_PROVIDER_TIMEOUT_SECONDS")

    # Development-only bypass. Must never be true outside a trusted local
    # environment; real authentication is not implemented yet (see AGENTS.md).
    gateway_dev_auth_bypass: bool = Field(default=True, alias="GATEWAY_DEV_AUTH_BYPASS")

    def validate_provider(self) -> None:
        if self.ai_provider not in SUPPORTED_PROVIDERS:
            raise ValueError(
                f"Unsupported AI_PROVIDER '{self.ai_provider}'. "
                f"Supported values: {sorted(SUPPORTED_PROVIDERS)}."
            )


@lru_cache
def get_settings() -> Settings:
    settings = Settings()
    settings.validate_provider()
    return settings
