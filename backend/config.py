"""Backend configuration, read from environment variables only."""

from __future__ import annotations

import os
from urllib.parse import urlparse

DEFAULT_GATEWAY_BASE_URL = "http://127.0.0.1:8000"
DEFAULT_GATEWAY_TIMEOUT_SECONDS = 10.0

_MIN_TIMEOUT_SECONDS = 0.1
_MAX_TIMEOUT_SECONDS = 120.0

#: Fail-closed by default: only "development" unlocks the food-analysis
#: route, which has no production authentication yet.
ALLOWED_APP_ENVS = frozenset({"development", "test", "production"})


class ConfigError(ValueError):
    """Raised when server-side configuration is invalid at startup."""


def get_app_env() -> str:
    return os.environ.get("APP_ENV", "production")


def is_development_mode() -> bool:
    return get_app_env() == "development"


def get_gateway_base_url() -> str:
    return os.environ.get("AI_GATEWAY_BASE_URL", DEFAULT_GATEWAY_BASE_URL)


def get_gateway_timeout_seconds() -> float:
    return float(os.environ.get("AI_GATEWAY_TIMEOUT_SECONDS", DEFAULT_GATEWAY_TIMEOUT_SECONDS))


def validate_config() -> None:
    """Fail closed at startup on any invalid configuration."""

    app_env = get_app_env()
    if app_env not in ALLOWED_APP_ENVS:
        raise ConfigError(f"Unsupported APP_ENV '{app_env}'. Supported values: {sorted(ALLOWED_APP_ENVS)}.")

    base_url = get_gateway_base_url()
    parsed = urlparse(base_url)
    if parsed.scheme not in ("http", "https") or not parsed.netloc:
        raise ConfigError(f"AI_GATEWAY_BASE_URL must be a valid http(s) URL, got '{base_url}'.")

    timeout = get_gateway_timeout_seconds()
    if not (_MIN_TIMEOUT_SECONDS <= timeout <= _MAX_TIMEOUT_SECONDS):
        raise ConfigError(
            f"AI_GATEWAY_TIMEOUT_SECONDS must be between {_MIN_TIMEOUT_SECONDS} and {_MAX_TIMEOUT_SECONDS}."
        )
