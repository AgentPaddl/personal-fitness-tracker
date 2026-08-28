"""Authentication scaffolding for the gateway.

Production authentication is not implemented yet. This module provides a
single, clearly marked seam so real authentication (e.g. mTLS, signed
service tokens) can be added later without reshaping routes or use cases.
"""

from __future__ import annotations

from fastapi import Request

from app.config import get_settings


async def require_authenticated_caller(request: Request) -> None:
    """FastAPI dependency guarding non-public gateway routes.

    DEVELOPMENT-ONLY BEHAVIOR: when ``GATEWAY_DEV_AUTH_BYPASS`` is true (the
    default), every caller is treated as authenticated. This must be
    disabled and replaced with real authentication before the gateway is
    reachable outside a trusted local environment.
    """

    settings = get_settings()
    if settings.gateway_dev_auth_bypass:
        return
    # No production authentication mechanism exists yet; fail closed.
    raise NotImplementedError(
        "Production authentication is not implemented. "
        "Set GATEWAY_DEV_AUTH_BYPASS=true for local development only."
    )
