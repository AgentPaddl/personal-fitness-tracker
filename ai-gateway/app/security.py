"""Authentication scaffolding for the gateway.

The gateway is never a public, client-facing API: its only caller is our
own backend. Authentication is a single shared secret (`X-Service-Token`,
`GATEWAY_SERVICE_TOKEN`) presented by the backend, compared in constant
time. This is intentionally not a general-purpose auth system (no per-user
identity, no token issuance) - it only needs to prove "this call came from
our backend", not authenticate individual end users.
"""

from __future__ import annotations

import hmac

from fastapi import Request

from app.config import get_settings
from app.errors import AuthenticationRequiredError


async def require_authenticated_caller(request: Request) -> None:
    """FastAPI dependency guarding non-public gateway routes.

    DEVELOPMENT-ONLY BYPASS: every caller is treated as authenticated when
    both ``APP_ENV=development`` and ``GATEWAY_DEV_AUTH_BYPASS=true`` are
    explicitly set. Otherwise, the request must present a valid
    ``X-Service-Token`` header matching ``GATEWAY_SERVICE_TOKEN``; a missing
    configured token (enforced fail-closed for ``APP_ENV=production`` at
    startup - see ``app.config.Settings.validate``) or a missing/mismatched
    header both fail closed with a sanitized 401.
    """

    settings = get_settings()
    if settings.app_env == "development" and settings.gateway_dev_auth_bypass:
        return

    configured_token = settings.gateway_service_token
    provided_token = request.headers.get("X-Service-Token")
    if not configured_token or not provided_token or not hmac.compare_digest(provided_token, configured_token):
        raise AuthenticationRequiredError()
