"""Backend-facing authentication: iOS -> backend.

This authenticates "this is our own iOS app", not individual end users -
there is exactly one user of this private, personal app. It intentionally
is not a general-purpose auth system (no accounts, no token issuance).
"""

from __future__ import annotations

import hmac

from config import get_backend_api_key, is_development_mode


def caller_is_authenticated(provided_api_key: str | None) -> bool:
    """True if the request may proceed.

    DEVELOPMENT-ONLY BYPASS: every caller is authenticated when
    ``APP_ENV=development`` (the existing local-dev convenience). In any
    other environment, the caller must present a valid ``X-API-Key``
    header matching ``BACKEND_API_KEY`` (compared in constant time); a
    missing configured key (fails closed at startup for
    ``APP_ENV=production`` - see ``config.validate_config``) or a
    missing/mismatched header both deny the request.
    """

    if is_development_mode():
        return True

    configured = get_backend_api_key()
    if not configured or not provided_api_key:
        return False
    return hmac.compare_digest(provided_api_key, configured)
