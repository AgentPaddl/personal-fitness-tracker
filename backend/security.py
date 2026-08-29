"""Backend-facing authentication: iOS -> backend.

Production authentication relies on Azure Functions / App Service
Authentication ("Easy Auth") with Microsoft Entra ID, configured entirely
outside this repository (see backend/AGENTS.md's Entra setup checklist).
When Easy Auth's "Require authentication" is enabled, Azure itself rejects
an unauthenticated caller *before* our code ever runs, and only then
injects trusted identity headers (e.g. `X-MS-CLIENT-PRINCIPAL-ID`).

A previous static shared-secret (`BACKEND_API_KEY`/`X-API-Key`) design was
rejected in review and has been removed entirely - do not reintroduce it.
"""

from __future__ import annotations

from typing import Mapping

from config import is_development_mode, is_easy_auth_enabled

#: Injected by Azure App Service/Functions only when Easy Auth is enabled
#: and the caller was already authenticated by Azure itself.
_EASY_AUTH_PRINCIPAL_ID_HEADER = "X-MS-CLIENT-PRINCIPAL-ID"


def caller_is_authenticated(headers: Mapping[str, str]) -> bool:
    """True if the request may proceed.

    DEVELOPMENT-ONLY BYPASS: every caller is authenticated when
    ``APP_ENV=development`` (the existing local-dev convenience).

    In any other environment, the request is trusted only if
    ``is_easy_auth_enabled()`` - a server-side-only flag set manually once
    Easy Auth is actually configured and enforcing in Azure - is true, and
    the request carries Easy Auth's own identity header. That header is
    never trusted while ``is_easy_auth_enabled()`` is false: a caller
    cannot grant itself trust just by sending it, since whether it is ever
    consulted is controlled entirely server-side. Until Easy Auth is
    configured in Azure, production fails closed with no valid caller.
    """

    if is_development_mode():
        return True

    if not is_easy_auth_enabled():
        return False

    return bool(headers.get(_EASY_AUTH_PRINCIPAL_ID_HEADER))
