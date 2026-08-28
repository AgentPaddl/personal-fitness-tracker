"""Backend configuration, read from environment variables only."""

from __future__ import annotations

import os

DEFAULT_GATEWAY_BASE_URL = "http://127.0.0.1:8000"
DEFAULT_GATEWAY_TIMEOUT_SECONDS = 10.0


def get_gateway_base_url() -> str:
    return os.environ.get("AI_GATEWAY_BASE_URL", DEFAULT_GATEWAY_BASE_URL)


def get_gateway_timeout_seconds() -> float:
    return float(os.environ.get("AI_GATEWAY_TIMEOUT_SECONDS", DEFAULT_GATEWAY_TIMEOUT_SECONDS))
