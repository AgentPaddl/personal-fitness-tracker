"""Internal HTTP client for the Personal AI Gateway.

This client forwards only the gateway's already-normalized response body;
it never adds provider or model detail and never logs request/response
bodies (which may contain user food descriptions). It distinguishes
connectivity failures, timeouts, and gateway-side errors so the backend can
map each to an appropriate public status code.
"""

from __future__ import annotations

from typing import Any

import httpx


class GatewayClientError(Exception):
    """Normalized error raised when the gateway cannot fulfil a request."""

    def __init__(self, code: str, http_status: int, message: str = "Gateway request failed."):
        super().__init__(message)
        self.code = code
        self.http_status = http_status
        self.message = message


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
            raise GatewayClientError(
                "gateway_timeout", 504, "The AI gateway did not respond in time."
            ) from exc
        except httpx.RequestError as exc:
            raise GatewayClientError(
                "gateway_unreachable", 503, "The AI gateway is unreachable."
            ) from exc

        if response.status_code >= 500:
            raise GatewayClientError(
                "gateway_upstream_error", 502, "The AI gateway reported an error."
            )
        if response.status_code >= 400:
            raise GatewayClientError(
                "gateway_rejected_request", 502, "The AI gateway rejected the request."
            )

        try:
            data = response.json()
        except ValueError as exc:
            raise GatewayClientError(
                "gateway_invalid_response", 502, "The AI gateway returned an invalid response."
            ) from exc

        if not isinstance(data, dict):
            raise GatewayClientError(
                "gateway_invalid_response", 502, "The AI gateway returned an invalid response."
            )

        return data

    def close(self) -> None:
        self._client.close()
