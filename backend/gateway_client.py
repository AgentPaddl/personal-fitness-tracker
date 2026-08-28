"""Internal HTTP client for the Personal AI Gateway.

This client forwards the gateway's already-normalized response as-is; it
never adds provider or model detail and never logs request/response bodies
(which may contain user food descriptions).
"""

from __future__ import annotations

from typing import Any

import httpx


class GatewayClientError(Exception):
    """Normalized error raised when the gateway cannot fulfil a request."""

    def __init__(self, code: str, message: str = "Gateway request failed."):
        super().__init__(message)
        self.code = code


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
        except httpx.RequestError as exc:
            raise GatewayClientError("gateway_unreachable", "The AI gateway is unreachable.") from exc

        if response.status_code >= 400:
            raise GatewayClientError(
                f"gateway_http_{response.status_code}", "The AI gateway returned an error."
            )

        return response.json()

    def close(self) -> None:
        self._client.close()
