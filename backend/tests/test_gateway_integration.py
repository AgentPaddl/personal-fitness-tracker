"""In-process integration/contract test: backend GatewayClient -> gateway FastAPI app -> FakeProvider.

This is not an end-to-end test: it runs entirely in-process using
Starlette's TestClient (no real network server or credentials required),
so it does not prove the gateway can run as a standalone process. See
ai-gateway/tests/test_smoke_process.py for that. This test proves the
backend and gateway contracts are wire-compatible in-process.

Requires ai-gateway's dependencies to be installed alongside the backend's
(see requirements-dev.txt).
"""

from __future__ import annotations

import sys
from pathlib import Path

_AI_GATEWAY_ROOT = Path(__file__).resolve().parents[2] / "ai-gateway"
if str(_AI_GATEWAY_ROOT) not in sys.path:
    sys.path.insert(0, str(_AI_GATEWAY_ROOT))

from fastapi.testclient import TestClient  # noqa: E402  (path set up above)

from app.config import get_settings  # noqa: E402
from app.dependencies import get_provider  # noqa: E402
from app.main import create_app  # noqa: E402

from gateway_client import GatewayClient  # noqa: E402


def test_backend_reaches_fake_provider_through_gateway_in_process(monkeypatch):
    # Explicit, test-only development configuration for the in-process
    # gateway instance created below.
    monkeypatch.setenv("APP_ENV", "development")
    monkeypatch.setenv("GATEWAY_DEV_AUTH_BYPASS", "true")
    monkeypatch.setenv("AI_PROVIDER", "fake")
    get_settings.cache_clear()
    get_provider.cache_clear()

    gateway_app = create_app()
    gateway_test_client = TestClient(gateway_app, base_url="http://gateway.local")
    client = GatewayClient(client=gateway_test_client)

    try:
        result = client.analyze_food_text("grilled chicken breast")
    finally:
        client.close()
        get_settings.cache_clear()
        get_provider.cache_clear()

    estimate = result["estimate"]
    assert "grilled chicken breast" in estimate["food_name"]
    assert 0 <= estimate["confidence"] <= 1
    assert "fake" not in str(result).lower()
