"""Server-side gateway configuration, read from environment variables only."""

from __future__ import annotations

import json
from functools import lru_cache

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

from app.providers.pricing import PriceTable, resolve_profiles

#: Providers implemented today. "copilot" is the real GitHub Copilot SDK
#: adapter (see app/providers/github_copilot.py); "fake" is deterministic
#: and credential-free.
SUPPORTED_PROVIDERS = frozenset({"fake", "copilot", "azure_openai"})

#: Fail-closed by default: only "development" may ever enable the dev auth
#: bypass. "test" is for the automated test suite; "production" is the
#: default so any unset/misconfigured deployment fails closed.
ALLOWED_APP_ENVS = frozenset({"development", "test", "production"})

_MIN_TIMEOUT_SECONDS = 0.1
_MAX_TIMEOUT_SECONDS = 120.0

#: Timeout hierarchy floor (self-contained - does not require knowing the
#: backend's own configured timeout): real Copilot calls are observed to
#: take tens of seconds, so a production provider timeout below this would
#: spuriously fail almost every real request.
_MIN_PRODUCTION_PROVIDER_TIMEOUT_SECONDS = 30.0

#: Production maximum for provider timeout. Must stay below backend's
#: configured timeout (which has its own minimum of 40s). Default production
#: value is 90s, maximum is 99s to preserve: 99s (provider) < 100s (backend).
_MAX_PRODUCTION_PROVIDER_TIMEOUT_SECONDS = 99.0

#: Production default provider timeout (recommended value; can be overridden
#: via AI_PROVIDER_TIMEOUT_SECONDS environment variable).
_DEFAULT_PRODUCTION_PROVIDER_TIMEOUT_SECONDS = 90.0


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="", extra="ignore")

    # Defaults to the strictest environment so a missing/misconfigured
    # deployment fails closed rather than silently behaving like dev.
    app_env: str = Field(default="production", alias="APP_ENV")

    ai_provider: str = Field(default="fake", alias="AI_PROVIDER")
    # Default to production-recommended 90s in production; 10s for fast local tests/dev
    ai_provider_timeout_seconds: float = Field(default=10.0, alias="AI_PROVIDER_TIMEOUT_SECONDS")
    ai_provider_max_output_tokens: int = Field(default=2000, alias="AI_PROVIDER_MAX_OUTPUT_TOKENS")
    azure_openai_endpoint: str = Field(default="", alias="AZURE_OPENAI_ENDPOINT")
    azure_openai_api_key: SecretStr | None = Field(default=None, alias="AZURE_OPENAI_API_KEY", repr=False)
    azure_openai_model_routes_json: str = Field(default="", alias="AZURE_OPENAI_MODEL_ROUTES_JSON")
    azure_openai_prices_json: str = Field(default="", alias="AZURE_OPENAI_PRICES_JSON")
    azure_openai_profiles_json: str = Field(default="", alias="AZURE_OPENAI_PROFILES_JSON")

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

    # Optional secondary/previous token, accepted alongside the current one
    # so the backend and gateway can be rotated to a new
    # GATEWAY_SERVICE_TOKEN without a synchronized-instant cutover: set the
    # old value here, roll out the new GATEWAY_SERVICE_TOKEN, then remove
    # this once the rotation is complete. Never required.
    gateway_service_token_previous: str | None = Field(default=None, alias="GATEWAY_SERVICE_TOKEN_PREVIOUS")

    # Small, fail-fast concurrency cap on simultaneous provider calls (each
    # one holds a Copilot CLI session). Deliberately not an unbounded queue:
    # a request that cannot get a slot immediately is rejected
    # (ServiceSaturatedError, 503) rather than made to wait.
    ai_provider_max_concurrency: int = Field(default=2, alias="AI_PROVIDER_MAX_CONCURRENCY")

    def validate(self) -> None:
        from app.pilot_release import is_api_artifact, validate_release

        if is_api_artifact():
            validate_release(self)
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

        if self.ai_provider == "azure_openai":
            from app.providers.openai_api import validate_endpoint

            if self.app_env == "production" and not is_api_artifact():
                raise ValueError("AI_PROVIDER=azure_openai is local-only until the production migration is approved.")
            validate_endpoint(self.azure_openai_endpoint)
            if not is_api_artifact() and (self.azure_openai_api_key is None or not self.azure_openai_api_key.get_secret_value().strip()):
                raise ValueError("AZURE_OPENAI_API_KEY is required for the Azure adapter.")
            routes = self.azure_openai_model_routes()
            if any(purpose not in routes for purpose in (self.food_text_model_purpose, self.food_image_model_purpose)):
                raise ValueError("AZURE_OPENAI_MODEL_ROUTES_JSON must map every configured purpose.")
            if not 1 <= self.ai_provider_max_output_tokens <= 32768:
                raise ValueError("AI_PROVIDER_MAX_OUTPUT_TOKENS must be between 1 and 32768.")
            resolve_profiles(self.azure_openai_profiles(), routes, self.azure_openai_prices(),
                             self.ai_provider_max_output_tokens)

        if not (1 <= self.ai_provider_max_concurrency <= 20):
            raise ValueError("AI_PROVIDER_MAX_CONCURRENCY must be between 1 and 20.")

        if self.app_env == "production" and not (self.gateway_service_token or "").strip():
            # The gateway is never a public API; its only caller is our own
            # backend, authenticated with this shared secret. Fails closed
            # in production rather than silently accepting any caller.
            raise ValueError("GATEWAY_SERVICE_TOKEN must be set when APP_ENV=production.")

        if self.app_env == "production" and self.ai_provider == "copilot":
            # The interactive `copilot`/`/login` device-code flow used for
            # local development has no headless equivalent in a deployed,
            # non-interactive container - a server-to-server token is the
            # only documented mechanism available today. Fails closed
            # rather than silently trying (and failing) an interactive login.
            if not (self.copilot_github_token or "").strip():
                raise ValueError(
                    "COPILOT_GITHUB_TOKEN must be set when APP_ENV=production and AI_PROVIDER=copilot "
                    "(no interactive Copilot CLI login is possible in a headless production deployment)."
                )

        if self.app_env == "production" and self.ai_provider_timeout_seconds < _MIN_PRODUCTION_PROVIDER_TIMEOUT_SECONDS:
            # Real Copilot calls are observed to take tens of seconds; a
            # production timeout below this floor would spuriously time out
            # essentially every real request.
            raise ValueError(
                f"AI_PROVIDER_TIMEOUT_SECONDS must be at least {_MIN_PRODUCTION_PROVIDER_TIMEOUT_SECONDS} "
                "seconds when APP_ENV=production."
            )

        if self.app_env == "production" and self.ai_provider_timeout_seconds > _MAX_PRODUCTION_PROVIDER_TIMEOUT_SECONDS:
            # Enforce timeout hierarchy: provider < backend (100s minimum) < iOS (110s).
            # Gateway must not permit timeouts that equal or exceed backend's floor.
            # Maximum 99s preserves: 99s (provider) < 100s (backend) < 110s (iOS).
            raise ValueError(
                f"AI_PROVIDER_TIMEOUT_SECONDS must be at most {_MAX_PRODUCTION_PROVIDER_TIMEOUT_SECONDS} "
                "seconds when APP_ENV=production to preserve the timeout hierarchy: "
                "provider < backend (100s) < iOS (110s)."
            )

    @staticmethod
    def _azure_json(raw: str) -> dict:
        def unique_object(pairs):
            result = {}
            for key, value in pairs:
                if key in result:
                    raise ValueError("Duplicate configuration key.")
                result[key] = value
            return result

        try:
            parsed = json.loads(raw, object_pairs_hook=unique_object)
            if not isinstance(parsed, dict):
                raise ValueError()
            return parsed
        except (ValueError, TypeError):
            raise ValueError("Invalid Azure JSON configuration.") from None

    def azure_openai_model_routes(self) -> dict[str, str]:
        from app.providers.openai_api import _identifier

        routes = self._azure_json(self.azure_openai_model_routes_json)
        if not routes or any(not _identifier(key) or not _identifier(value) for key, value in routes.items()):
            raise ValueError("AZURE_OPENAI_MODEL_ROUTES_JSON requires explicit purpose/deployment identifiers.")
        return routes

    def azure_openai_prices(self) -> PriceTable | None:
        if not self.azure_openai_prices_json.strip():
            return None
        try:
            return PriceTable.model_validate(self._azure_json(self.azure_openai_prices_json))
        except ValueError:
            raise ValueError("Invalid AZURE_OPENAI_PRICES_JSON; expected a versioned USD deployment price table.") from None

    def azure_openai_profiles(self) -> dict[str, str]:
        from app.providers.openai_api import _identifier

        if not self.azure_openai_profiles_json.strip():
            return {}
        bindings = self._azure_json(self.azure_openai_profiles_json)
        if not bindings or any(not _identifier(key) or not _identifier(value) for key, value in bindings.items()):
            raise ValueError("AZURE_OPENAI_PROFILES_JSON requires deployment/profile identifiers.")
        return bindings

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
