"""True end-to-end test: backend GatewayClient -> gateway FastAPI app -> FakeProvider.

Runs entirely in-process using an httpx ASGI transport (no real network
server or credentials required). Requires ai-gateway's dependencies to be
installed alongside the backend's (see requirements-dev.txt).
"""

from __future__ import annotations

import sys
from pathlib import Path

_AI_GATEWAY_ROOT = Path(__file__).resolve().parents[2] / "ai-gateway"
if str(_AI_GATEWAY_ROOT) not in sys.path:
    sys.path.insert(0, str(_AI_GATEWAY_ROOT))

from fastapi.testclient import TestClient  # noqa: E402  (path set up above)

from app.main import create_app  # noqa: E402

from gateway_client import GatewayClient  # noqa: E402


def test_backend_reaches_fake_provider_through_gateway_in_process():
    gateway_app = create_app()
    gateway_test_client = TestClient(gateway_app, base_url="http://gateway.local")
    client = GatewayClient(client=gateway_test_client)

    try:
        result = client.analyze_food_text("grilled chicken breast")
    finally:
        client.close()

    estimate = result["estimate"]
    assert estimate["food_name"] == "grilled chicken breast"
    assert 0 <= estimate["confidence"] <= 1
    assert "fake" not in str(result).lower()
