"""Internal HTTP client for the Personal AI Gateway.

This client forwards only the gateway's already-normalized response body;
it never adds provider or model detail and never logs request/response
bodies (which may contain user food descriptions). It distinguishes
connectivity failures, timeouts, and gateway-side errors so the backend can
map each to an appropriate public status code.

Error messages are always backend-owned: the gateway's own error message
text is never forwarded to the client, only its normalized ``error.code``
is read (safely) to decide which whitelisted backend status/code applies.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import time
from typing import Any

import httpx

#: Gateway error codes whose semantics are safe to preserve at the backend
#: boundary, each mapped to a distinct backend-owned (code, http_status).
#: Any other gateway error code (or a malformed/unparseable error body) is
#: treated as untrusted and normalized to "gateway_upstream_error" (502).
_UPSTREAM_CODE_TO_BACKEND: dict[str, tuple[str, int]] = {
    "pilot_unavailable": ("pilot_unavailable", 503),
    "pilot_forbidden": ("pilot_forbidden", 403),
    "operation_required": ("operation_required", 400),
    "operation_conflict": ("operation_conflict", 409),
    "operation_consumed": ("operation_consumed", 409),
    "pilot_limit": ("pilot_limit", 429),
    "pilot_input": ("pilot_input", 413),
    "service_not_ready": ("gateway_service_unavailable", 503),
    "provider_timeout": ("gateway_timeout", 504),
    "provider_rate_limited": ("gateway_rate_limited", 429),
    "provider_unavailable": ("gateway_service_unavailable", 503),
    "service_saturated": ("gateway_saturated", 503),
}

_BACKEND_MESSAGES: dict[str, str] = {
    "pilot_unavailable": "Analysis admission is unavailable. Do not automatically repeat this operation.",
    "pilot_forbidden": "This identity is not authorized for the pilot.",
    "operation_required": "A current UUIDv7 X-Operation-Id is required for pilot analysis.",
    "operation_conflict": "This operation ID was already used with different content.",
    "operation_consumed": "This operation was already accepted. Its result cannot be retrieved or automatically repeated.",
    "pilot_limit": "The configured pilot usage limit has been reached.",
    "pilot_input": "This input exceeds the configured pilot analysis limits.",
    "gateway_timeout": "The AI gateway did not respond in time.",
    "gateway_rate_limited": "The AI provider is currently rate limited. Try again later.",
    "gateway_service_unavailable": "The AI gateway or provider is currently unavailable.",
    "gateway_saturated": "The AI gateway is at its concurrent request limit. Try again shortly.",
    "gateway_upstream_error": "The AI gateway reported an error.",
    "gateway_unreachable": "The AI gateway is unreachable.",
    "gateway_invalid_response": "The AI gateway returned an invalid response.",
}

#: Sanitized bounds for a Retry-After value we are willing to forward.
#: Never trusts an arbitrary/huge/negative value from the gateway.
_MIN_RETRY_AFTER_SECONDS = 1
_MAX_RETRY_AFTER_SECONDS = 60


class GatewayClientError(Exception):
    """Normalized error raised when the gateway cannot fulfil a request."""

    def __init__(
        self, code: str, http_status: int, message: str | None = None, retry_after_seconds: int | None = None
    ):
        super().__init__(message or _BACKEND_MESSAGES.get(code, "Gateway request failed."))
        self.code = code
        self.http_status = http_status
        self.message = message or _BACKEND_MESSAGES.get(code, "Gateway request failed.")
        self.retry_after_seconds = retry_after_seconds


def _safe_parse_upstream_error_code(response: httpx.Response) -> str | None:
    """Best-effort, never-raising extraction of the gateway's error code.

    The gateway's error *message* is intentionally never read here; only
    the structured ``error.code`` is used, and only to look up a
    whitelisted backend mapping.
    """

    try:
        data = response.json()
    except ValueError:
        return None
    if not isinstance(data, dict):
        return None
    error = data.get("error")
    if not isinstance(error, dict):
        return None
    code = error.get("code")
    return code if isinstance(code, str) else None


def _safe_parse_retry_after(response: httpx.Response) -> int | None:
    """Best-effort, never-raising, bounded extraction of a Retry-After
    value. Never trusts an out-of-bounds/malformed value - the caller must
    never invent its own provider-specific timing, but forwarding an
    upstream value unbounded would be just as untrustworthy.
    """

    raw = response.headers.get("Retry-After")
    if raw is None:
        return None
    try:
        seconds = int(raw)
    except ValueError:
        return None
    if not (_MIN_RETRY_AFTER_SECONDS <= seconds <= _MAX_RETRY_AFTER_SECONDS):
        return None
    return seconds


class GatewayClient:
    def __init__(
        self,
        base_url: str = "",
        timeout: float = 10.0,
        transport: httpx.BaseTransport | None = None,
        client: httpx.Client | None = None,
        service_token: str | None = None,
        request_id: str | None = None,
        verified_identity: tuple[str, str] | None = None,
        operation_id: str | None = None,
    ):
        # ``client`` allows tests to inject a fully-configured httpx.Client
        # (e.g. Starlette's TestClient) that talks to the gateway in-process.
        self._client = client or httpx.Client(base_url=base_url, timeout=timeout, transport=transport)
        self._headers: dict[str, str] = {}
        self._verified_identity = verified_identity
        self._operation_id = operation_id
        if operation_id:
            self._headers["X-Operation-Id"] = operation_id
        if service_token:
            # Proves to the gateway this call came from the backend, not an
            # arbitrary caller - the gateway is never a public API.
            self._headers["X-Service-Token"] = service_token
        if request_id:
            self._headers["X-Request-Id"] = request_id

    def analyze_food_text(self, food_description: str) -> dict[str, Any]:
        return self._post_and_handle({"food_description": food_description})

    def analyze_food_refinement(self, payload: dict[str, Any]) -> dict[str, Any]:
        """Forward an already validated, explicitly mapped refinement payload."""

        return self._post_and_handle(payload)

    def analyze_food_image(
        self, image_bytes: bytes, mime_type: str, food_description: str | None = None
    ) -> dict[str, Any]:
        # Sent as an inline base64 JSON payload on the existing internal
        # gateway contract (server-to-server, not the public multipart API)
        # to reuse the existing JSON httpx client rather than adding a
        # second internal transport.
        payload: dict[str, Any] = {
            "image": {"media_type": mime_type, "data_base64": base64.b64encode(image_bytes).decode("ascii")}
        }
        if food_description:
            payload["food_description"] = food_description
        return self._post_and_handle(payload)

    def _post_and_handle(self, payload: dict[str, Any]) -> dict[str, Any]:
        headers = dict(self._headers)
        if self._verified_identity is not None:
            try:
                secret = os.environ["AI_PILOT_SIGNING_KEY"].encode()
                if len(secret) < 32 or not self._operation_id:
                    raise ValueError()
                serialized = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True, allow_nan=False).encode()
                envelope = {"tid": self._verified_identity[0], "oid": self._verified_identity[1],
                            "operation": self._operation_id, "issued": int(time.time()),
                            "body": hashlib.sha256(serialized).hexdigest(), "aud": "fitness-gateway-pilot-v1"}
                encoded = base64.urlsafe_b64encode(json.dumps(envelope, sort_keys=True, separators=(",", ":")).encode()).decode()
                signature = hmac.new(secret, encoded.encode(), hashlib.sha256).hexdigest()
                headers["X-Pilot-Authorization"] = encoded + "." + signature
            except (KeyError, ValueError):
                raise GatewayClientError("pilot_unavailable", 503) from None
        try:
            response = self._client.post("/v1/food-analysis", json=payload, headers=headers)
        except httpx.TimeoutException as exc:
            raise GatewayClientError("gateway_timeout", 504) from exc
        except httpx.RequestError as exc:
            raise GatewayClientError("gateway_unreachable", 503) from exc

        if response.status_code >= 400:
            upstream_code = _safe_parse_upstream_error_code(response)
            backend_code, backend_status = _UPSTREAM_CODE_TO_BACKEND.get(
                upstream_code, ("gateway_upstream_error", 502)
            )
            raise GatewayClientError(
                backend_code, backend_status, retry_after_seconds=_safe_parse_retry_after(response)
            )

        try:
            data = response.json()
        except ValueError as exc:
            raise GatewayClientError("gateway_invalid_response", 502) from exc

        if not isinstance(data, dict):
            raise GatewayClientError("gateway_invalid_response", 502)

        return data

    def close(self) -> None:
        self._client.close()
