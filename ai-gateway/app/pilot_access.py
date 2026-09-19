"""Authenticated backend assertions and per-request admission wiring."""

import base64
from contextvars import ContextVar
import hashlib
import hmac
import json
import os
import time
from uuid import UUID

from app.pilot import Coordinator, PilotError, PilotPolicy, canonical, digest, enabled, operation_id

_context = ContextVar("pilot_identity", default=None)


def verify(headers, payload):
    try:
        assertion = headers.get("X-Pilot-Authorization", "")
        if not enabled():
            if assertion:
                raise PilotError()
            return None
        if not assertion or len(assertion) > 2048:
            raise PilotError("pilot_forbidden")
        secret = os.environ["AI_PILOT_SIGNING_KEY"].encode()
        if len(secret) < 32:
            raise PilotError()
        encoded, signature = assertion.split(".")
        expected = hmac.new(secret, encoded.encode(), hashlib.sha256).hexdigest()
        if not hmac.compare_digest(expected, signature):
            raise PilotError("pilot_forbidden")
        envelope = json.loads(base64.b64decode(encoded, altchars=b"-_", validate=True))
        if (envelope["aud"] != "fitness-gateway-pilot-v1" or type(envelope["issued"]) is not int
                or not time.time() - 60 <= envelope["issued"] <= time.time() + 5
                or envelope["body"] != hashlib.sha256(canonical(payload)).hexdigest()
                or envelope["operation"] != headers.get("X-Operation-Id")):
            raise PilotError("pilot_forbidden")
        identity = (str(UUID(envelope["tid"])), str(UUID(envelope["oid"])))
        return identity, envelope["operation"]
    except PilotError:
        raise
    except Exception:
        raise PilotError("pilot_forbidden") from None


def build_coordinator(store=None, *, settings=None):
    from app.config import get_settings
    from app.pilot_table import AzureTableStore

    try:
        settings = settings if settings is not None else get_settings()
        if settings.ai_provider != "azure_openai":
            raise PilotError()
        policy = PilotPolicy.model_validate_json(os.environ["AI_PILOT_POLICY_JSON"])
        entries = json.loads(os.environ["AI_PILOT_ALLOWLIST_JSON"])
        if not isinstance(entries, list) or not 1 <= len(entries) <= 2:
            raise PilotError()
        allowlist = {(str(UUID(entry["tid"])), str(UUID(entry["oid"]))) for entry in entries}
        secret = os.environ["AI_PILOT_FINGERPRINT_KEY"].encode()
        if len(secret) < 32 or secret == os.environ["AI_PILOT_SIGNING_KEY"].encode():
            raise PilotError()
        prices = settings.azure_openai_prices()
        if prices is None or settings.ai_provider_max_output_tokens > policy.max_output_tokens:
            raise PilotError()
        routes = settings.azure_openai_model_routes()
        control = Coordinator(store, policy, secret, allowlist, prices, routes,
                      profile_bindings=settings.azure_openai_profiles(),
                      max_output_tokens=settings.ai_provider_max_output_tokens)
        if store is None:
            control.store = AzureTableStore.connect(os.environ["AI_PILOT_TABLE_ENDPOINT"], os.environ["AI_PILOT_TABLE_NAME"])
        return control
    except PilotError:
        raise
    except Exception:
        raise PilotError() from None


async def generate(provider, request):
    context = _context.get()
    if context is None:
        raise PilotError("pilot_forbidden")
    control = build_coordinator()
    identity, operation, payload = context
    try:
        acceptance = control.policy.acceptance
        if acceptance and hashlib.sha256(canonical(payload)).hexdigest() not in acceptance.payload_sha256:
            raise PilotError("pilot_forbidden")
        operation_id(operation, time.time(), control.policy.operation_max_age_seconds)
        fingerprint = digest(control.secret, "request-v1", [identity, payload])
        return await control.generate(provider, request, identity, operation, fingerprint)
    finally:
        try:
            await control.store.close()
        except Exception:
            pass