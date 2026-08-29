"""Authentication scaffolding for the gateway.

The gateway is never a public, client-facing API: its only caller is our
own backend. Authentication is a shared secret (`X-Service-Token`,
`GATEWAY_SERVICE_TOKEN`, optionally with `GATEWAY_SERVICE_TOKEN_PREVIOUS`
accepted during rotation) presented by the backend, compared in constant
time. This is intentionally not a general-purpose auth system (no per-user
identity, no token issuance) - it only needs to prove "this call came from
our backend", not authenticate individual end users.

Possible later improvement: Managed Identity / Entra service-to-service
auth between the backend and gateway, instead of a shared secret. Not
adopted in this change - it is not clearly simpler than the current
mechanism for a two-service, single-tenant private deployment.
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
    ``X-Service-Token`` header matching either ``GATEWAY_SERVICE_TOKEN``
    (current) or ``GATEWAY_SERVICE_TOKEN_PREVIOUS`` (optional, accepted
    only during a token rotation window - the backend always sends only
    the current token). A missing configured current token (enforced
    fail-closed for ``APP_ENV=production`` at startup - see
    ``app.config.Settings.validate``) or a missing/mismatched header both
    fail closed with a sanitized 401. Never logs either secret.
    """

    settings = get_settings()
    if settings.app_env == "development" and settings.gateway_dev_auth_bypass:
        return

    provided_token = request.headers.get("X-Service-Token")
    if not provided_token:
        raise AuthenticationRequiredError()

    for configured_token in (settings.gateway_service_token, settings.gateway_service_token_previous):
        if configured_token and hmac.compare_digest(provided_token, configured_token):
            return

    raise AuthenticationRequiredError()
