"""Authentication scaffolding for the gateway.

Production authentication is not implemented yet. This module provides a
single, clearly marked seam so real authentication (e.g. mTLS, signed
service tokens) can be added later without reshaping routes or use cases.
"""

from __future__ import annotations

from fastapi import Request

from app.config import get_settings
from app.errors import AuthenticationRequiredError


async def require_authenticated_caller(request: Request) -> None:
    """FastAPI dependency guarding non-public gateway routes.

    DEVELOPMENT-ONLY BEHAVIOR: every caller is treated as authenticated only
    when both ``APP_ENV=development`` and ``GATEWAY_DEV_AUTH_BYPASS=true``
    are explicitly set. Any other configuration fails closed with a 401,
    including the default configuration, until real authentication is
    implemented.
    """

    settings = get_settings()
    if settings.app_env == "development" and settings.gateway_dev_auth_bypass:
        return
    raise AuthenticationRequiredError()
