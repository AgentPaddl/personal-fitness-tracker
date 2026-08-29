"""Backend configuration, read from environment variables only."""

from __future__ import annotations

import os
from urllib.parse import urlparse

DEFAULT_GATEWAY_BASE_URL = "http://127.0.0.1:8000"
DEFAULT_GATEWAY_TIMEOUT_SECONDS = 10.0

_MIN_TIMEOUT_SECONDS = 0.1
_MAX_TIMEOUT_SECONDS = 120.0

#: The gateway's own production floor is 30s (real Copilot calls are
#: observed to take tens of seconds); the backend must allow strictly more
#: headroom than that so a slow-but-successful gateway call is never cut
#: off first by the backend's own timeout. Self-contained - does not
#: require querying the gateway's live config.
_MIN_PRODUCTION_GATEWAY_TIMEOUT_SECONDS = 40.0

#: Fail-closed by default: only "development" unlocks the food-analysis
#: route, which has no production authentication yet.
ALLOWED_APP_ENVS = frozenset({"development", "test", "production"})

#: Hosts that are only ever reachable from the developer's own machine/LAN.
#: A production deployment must never point at one of these - it would
#: mean the backend can't actually reach a real, separately-hosted gateway.
_LOCAL_ONLY_HOSTNAMES = frozenset({"localhost", "127.0.0.1", "::1"})


class ConfigError(ValueError):
    """Raised when server-side configuration is invalid at startup."""


def get_app_env() -> str:
    return os.environ.get("APP_ENV", "production")


def is_development_mode() -> bool:
    return get_app_env() == "development"


def is_production_mode() -> bool:
    return get_app_env() == "production"


def get_gateway_base_url() -> str:
    return os.environ.get("AI_GATEWAY_BASE_URL", DEFAULT_GATEWAY_BASE_URL)


def get_gateway_timeout_seconds() -> float:
    return float(os.environ.get("AI_GATEWAY_TIMEOUT_SECONDS", DEFAULT_GATEWAY_TIMEOUT_SECONDS))


def is_easy_auth_enabled() -> bool:
    """Server-side-only flag, set manually once Easy Auth is actually
    configured and enforcing ("Require authentication") on the deployed
    Function App - never inferred from anything a caller sends. See
    `security.py` and `backend/AGENTS.md`'s Entra setup checklist.
    """

    return os.environ.get("EASY_AUTH_ENABLED", "false").strip().lower() == "true"


def get_gateway_service_token() -> str | None:
    """Current shared secret forwarded to the gateway as `X-Service-Token`.

    Proves to the gateway that a call came from this backend, not an
    arbitrary caller - the gateway itself is never a public API. Never has
    a hard-coded value; never committed.
    """

    return os.environ.get("GATEWAY_SERVICE_TOKEN") or None


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

    if app_env == "production":
        # Every production requirement below fails closed: a missing value
        # is a startup error, never a silently-permissive default.
        if not get_gateway_service_token():
            raise ConfigError("GATEWAY_SERVICE_TOKEN must be set when APP_ENV=production.")
        if (parsed.hostname or "").lower() in _LOCAL_ONLY_HOSTNAMES:
            raise ConfigError(
                "AI_GATEWAY_BASE_URL must not be a localhost address when APP_ENV=production; "
                "the production gateway must be an explicitly configured, separately-hosted URL."
            )
        if parsed.scheme != "https":
            raise ConfigError(
                "AI_GATEWAY_BASE_URL must use https when APP_ENV=production "
                "(private networking/HTTPS only - see backend/AGENTS.md)."
            )
        if timeout < _MIN_PRODUCTION_GATEWAY_TIMEOUT_SECONDS:
            raise ConfigError(
                f"AI_GATEWAY_TIMEOUT_SECONDS must be at least {_MIN_PRODUCTION_GATEWAY_TIMEOUT_SECONDS} "
                "seconds when APP_ENV=production, to leave headroom above the gateway's own "
                "production timeout floor for real Copilot latency."
            )
