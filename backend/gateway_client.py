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

from typing import Any

import httpx

#: Gateway error codes whose semantics are safe to preserve at the backend
#: boundary, each mapped to a distinct backend-owned (code, http_status).
#: Any other gateway error code (or a malformed/unparseable error body) is
#: treated as untrusted and normalized to "gateway_upstream_error" (502).
_UPSTREAM_CODE_TO_BACKEND: dict[str, tuple[str, int]] = {
    "provider_timeout": ("gateway_timeout", 504),
    "provider_rate_limited": ("gateway_rate_limited", 429),
    "provider_unavailable": ("gateway_service_unavailable", 503),
}

_BACKEND_MESSAGES: dict[str, str] = {
    "gateway_timeout": "The AI gateway did not respond in time.",
    "gateway_rate_limited": "The AI provider is currently rate limited. Try again later.",
    "gateway_service_unavailable": "The AI gateway or provider is currently unavailable.",
    "gateway_upstream_error": "The AI gateway reported an error.",
    "gateway_unreachable": "The AI gateway is unreachable.",
    "gateway_invalid_response": "The AI gateway returned an invalid response.",
}


class GatewayClientError(Exception):
    """Normalized error raised when the gateway cannot fulfil a request."""

    def __init__(self, code: str, http_status: int, message: str | None = None):
        super().__init__(message or _BACKEND_MESSAGES.get(code, "Gateway request failed."))
        self.code = code
        self.http_status = http_status
        self.message = message or _BACKEND_MESSAGES.get(code, "Gateway request failed.")


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


class GatewayClient:
    def __init__(
        self,
        base_url: str = "",
        timeout: float = 10.0,
        transport: httpx.BaseTransport | None = None,
        client: httpx.Client | None = None,
    ):
        # ``client`` allows tests to inject a fully-configured httpx.Client
        # (e.g. Starlette's TestClient) that talks to the gateway in-process.
        self._client = client or httpx.Client(base_url=base_url, timeout=timeout, transport=transport)

    def analyze_food_text(self, food_description: str) -> dict[str, Any]:
        try:
            response = self._client.post(
                "/v1/food-analysis", json={"food_description": food_description}
            )
        except httpx.TimeoutException as exc:
            raise GatewayClientError("gateway_timeout", 504) from exc
        except httpx.RequestError as exc:
            raise GatewayClientError("gateway_unreachable", 503) from exc

        if response.status_code >= 400:
            upstream_code = _safe_parse_upstream_error_code(response)
            backend_code, backend_status = _UPSTREAM_CODE_TO_BACKEND.get(
                upstream_code, ("gateway_upstream_error", 502)
            )
            raise GatewayClientError(backend_code, backend_status)

        try:
            data = response.json()
        except ValueError as exc:
            raise GatewayClientError("gateway_invalid_response", 502) from exc

        if not isinstance(data, dict):
            raise GatewayClientError("gateway_invalid_response", 502)

        return data

    def close(self) -> None:
        self._client.close()
