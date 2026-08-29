"""Server-side gateway configuration, read from environment variables only."""

from __future__ import annotations

import json
from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

#: Providers implemented today. "copilot" is the real GitHub Copilot SDK
#: adapter (see app/providers/github_copilot.py); "fake" is deterministic
#: and credential-free.
SUPPORTED_PROVIDERS = frozenset({"fake", "copilot"})

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

    # Separate routing key for image-based food analysis, since it requires
    # a vision-capable model. Never silently falls back to the text route.
    food_image_model_purpose: str = Field(default="food_image_v1", alias="FOOD_IMAGE_MODEL_PURPOSE")

    # Development-only bypass, off by default. Even when true, it only takes
    # effect if app_env == "development" (enforced in app.security).
    gateway_dev_auth_bypass: bool = Field(default=False, alias="GATEWAY_DEV_AUTH_BYPASS")

    # JSON object mapping a model-routing purpose (e.g. "food_text_v1") to a
    # concrete Copilot model id (e.g. "gpt-5"). Required, with no default,
    # when AI_PROVIDER=copilot, so a model is never silently substituted.
    copilot_model_routes_json: str = Field(default="", alias="COPILOT_MODEL_ROUTES_JSON")

    # Optional explicit GitHub token for the Copilot SDK. When unset (the
    # default), the SDK falls back to its own documented mechanisms: a
    # locally logged-in `copilot` CLI session, or the standard
    # COPILOT_GITHUB_TOKEN/GH_TOKEN/GITHUB_TOKEN environment variables. This
    # setting never has a hard-coded value and is never committed.
    copilot_github_token: str | None = Field(default=None, alias="COPILOT_GITHUB_TOKEN")

    # Shared secret the backend must present (as `X-Service-Token`) on every
    # `/v1/*` call. This is the gateway's *only* real caller-authentication
    # mechanism outside the dev bypass; the gateway is never a public,
    # client-facing API, so this only ever needs to authenticate our own
    # backend, not end users. Never has a hard-coded value; never committed.
    gateway_service_token: str | None = Field(default=None, alias="GATEWAY_SERVICE_TOKEN")

    # Small, fail-fast concurrency cap on simultaneous provider calls (each
    # one holds a Copilot CLI session). Deliberately not an unbounded queue:
    # a request that cannot get a slot immediately is rejected
    # (ServiceSaturatedError, 503) rather than made to wait.
    ai_provider_max_concurrency: int = Field(default=2, alias="AI_PROVIDER_MAX_CONCURRENCY")

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

        if not self.food_image_model_purpose.strip():
            raise ValueError("FOOD_IMAGE_MODEL_PURPOSE must not be blank.")

        if self.ai_provider == "copilot":
            routes = self.copilot_model_routes()
            for purpose in (self.food_text_model_purpose, self.food_image_model_purpose):
                if purpose not in routes:
                    raise ValueError(
                        "COPILOT_MODEL_ROUTES_JSON must map every configured model "
                        f"purpose (here: '{purpose}') to a model id. "
                        "A model is never silently substituted."
                    )

        if not (1 <= self.ai_provider_max_concurrency <= 20):
            raise ValueError("AI_PROVIDER_MAX_CONCURRENCY must be between 1 and 20.")

        if self.app_env == "production" and not (self.gateway_service_token or "").strip():
            # The gateway is never a public API; its only caller is our own
            # backend, authenticated with this shared secret. Fails closed
            # in production rather than silently accepting any caller.
            raise ValueError("GATEWAY_SERVICE_TOKEN must be set when APP_ENV=production.")

    def copilot_model_routes(self) -> dict[str, str]:
        """Parse COPILOT_MODEL_ROUTES_JSON into a purpose -> model id mapping.

        Raises ValueError on any malformed configuration; never falls back
        to a default/guessed model. Routing keys and model ids are
        stripped and rejected if empty/whitespace-only, so a blank value
        can never reach the SDK and let the Copilot CLI silently pick its
        own default model.
        """

        raw = self.copilot_model_routes_json.strip()
        if not raw:
            raise ValueError(
                "COPILOT_MODEL_ROUTES_JSON is required when AI_PROVIDER=copilot."
            )
        try:
            parsed = json.loads(raw)
        except ValueError as exc:
            raise ValueError(f"COPILOT_MODEL_ROUTES_JSON is not valid JSON: {exc}") from exc
        if not isinstance(parsed, dict) or not all(
            isinstance(k, str) and isinstance(v, str) for k, v in parsed.items()
        ):
            raise ValueError("COPILOT_MODEL_ROUTES_JSON must be a JSON object of string to string.")

        routes: dict[str, str] = {}
        for key, value in parsed.items():
            stripped_key = key.strip()
            stripped_value = value.strip()
            if not stripped_key or not stripped_value:
                raise ValueError(
                    "COPILOT_MODEL_ROUTES_JSON routing keys and model ids must not "
                    "be empty or whitespace-only."
                )
            routes[stripped_key] = stripped_value
        return routes


@lru_cache
def get_settings() -> Settings:
    settings = Settings()
    settings.validate()
    return settings
