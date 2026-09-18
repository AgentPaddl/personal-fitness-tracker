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

import base64
import json
import os
from uuid import UUID
from typing import Mapping

from config import is_development_mode, is_easy_auth_enabled

#: Injected by Azure App Service/Functions only when Easy Auth is enabled
#: and the caller was already authenticated by Azure itself.
_EASY_AUTH_PRINCIPAL_ID_HEADER = "X-MS-CLIENT-PRINCIPAL-ID"


def pilot_enabled() -> bool:
    value = os.environ.get("AI_PILOT_ENABLED", "false")
    if value not in {"true", "false"}:
        raise ValueError("Invalid pilot configuration.")
    return value == "true"


def pilot_identity(headers: Mapping[str, str]) -> tuple[str, str]:
    if not is_easy_auth_enabled():
        raise ValueError("Pilot identity is not authorized.")
    aliases = {
        "http://schemas.microsoft.com/identity/claims/tenantid": "tid",
        "http://schemas.microsoft.com/identity/claims/objectidentifier": "oid",
        "http://schemas.microsoft.com/identity/claims/scope": "scp",
    }
    try:
        raw = headers.get("X-MS-CLIENT-PRINCIPAL", "")
        if len(raw) > 32768:
            raise ValueError()
        principal = json.loads(base64.b64decode(raw, validate=True))
        if principal["auth_typ"] != "aad":
            raise ValueError()
        claims = {}
        for claim in principal["claims"]:
            name = aliases.get(claim["typ"], claim["typ"])
            if name in {"tid", "oid", "aud", "iss", "azp", "appid", "scp"}:
                if name in claims or not isinstance(claim["val"], str):
                    raise ValueError()
                claims[name] = claim["val"]
        tenant, person = str(UUID(claims["tid"])), str(UUID(claims["oid"]))
        allowed = json.loads(os.environ["AI_PILOT_ALLOWLIST_JSON"])
        if not isinstance(allowed, list) or not 1 <= len(allowed) <= 2:
            raise ValueError()
        pairs = {(str(UUID(entry["tid"])), str(UUID(entry["oid"]))) for entry in allowed}
        if (tenant, person) not in pairs or tenant != os.environ["AI_PILOT_TENANT_ID"]:
            raise ValueError()
        if claims["aud"] != os.environ["AI_PILOT_AUDIENCE"] or not claims["aud"]:
            raise ValueError()
        issuer = os.environ["AI_PILOT_ISSUER"]
        if issuer not in {f"https://login.microsoftonline.com/{tenant}/v2.0", f"https://sts.windows.net/{tenant}/"}:
            raise ValueError()
        if claims["iss"] != issuer:
            raise ValueError()
        clients = {claims[name] for name in ("azp", "appid") if name in claims}
        if clients != {os.environ["AI_PILOT_CLIENT_ID"]} or "" in clients:
            raise ValueError()
        scope = os.environ["AI_PILOT_SCOPE"]
        if not scope or scope not in claims["scp"].split():
            raise ValueError()
        if str(UUID(headers.get(_EASY_AUTH_PRINCIPAL_ID_HEADER, ""))) != person:
            raise ValueError()
        return tenant, person
    except (ValueError, KeyError, TypeError, AttributeError, RecursionError):
        raise ValueError("Pilot identity is not authorized.") from None


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
