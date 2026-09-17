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
import asyncio
import json
from pathlib import Path

import httpx2
import pytest

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


def test_backend_refinement_contract_reaches_gateway_without_image_bytes(monkeypatch):
    monkeypatch.setenv("APP_ENV", "development")
    monkeypatch.setenv("GATEWAY_DEV_AUTH_BYPASS", "true")
    monkeypatch.setenv("AI_PROVIDER", "fake")
    get_settings.cache_clear()
    get_provider.cache_clear()

    gateway_app = create_app()
    gateway_test_client = TestClient(gateway_app, base_url="http://gateway.local")
    client = GatewayClient(client=gateway_test_client)
    payload = {
        "refinement": {
            "correction_text": "I ate only half.",
            "current_estimate": {
                "food_name": "rice bowl",
                "calories": 620.0,
                "protein_grams": 24.0,
                "carbohydrate_grams": 86.0,
                "fat_grams": 18.0,
                "confidence": 0.72,
                "warnings": [],
                "assumptions": [],
            },
            "source_kind": "image",
            "iteration": 1,
        }
    }

    try:
        result = client.analyze_food_refinement(payload)
    finally:
        client.close()
        get_settings.cache_clear()
        get_provider.cache_clear()

    assert "image" not in payload
    assert set(result["estimate"]) == {
        "food_name",
        "calories",
        "protein_grams",
        "carbohydrate_grams",
        "fat_grams",
        "confidence",
        "warnings",
        "assumptions",
    }


@pytest.mark.parametrize("outcome", ["success", "refusal", "rate_limit", "invalid"])
def test_azure_mock_preserves_gateway_and_backend_public_contract(monkeypatch, outcome):
    from app.dependencies import get_food_analysis_use_case
    from app.providers.openai_api import AzureOpenAIProvider
    from app.use_cases.food_analysis import FoodAnalysisUseCase
    from gateway_client import GatewayClientError
    from schemas import map_gateway_response_to_public

    monkeypatch.setenv("APP_ENV", "development")
    monkeypatch.setenv("GATEWAY_DEV_AUTH_BYPASS", "true")
    monkeypatch.setenv("AI_PROVIDER", "fake")
    get_settings.cache_clear()
    get_provider.cache_clear()
    estimate = {
        "food_name": "synthetic meal", "calories": 200, "protein_grams": 10,
        "carbohydrate_grams": 20, "fat_grams": 5, "confidence": 0.5,
        "warnings": [], "assumptions": [],
    }
    calls = []

    def handler(request):
        calls.append(request)
        if outcome == "rate_limit":
            return httpx2.Response(429, json={"error": {"message": "sensitive-provider-marker"}})
        data = {**estimate, "calories": -1} if outcome == "invalid" else estimate
        return httpx2.Response(200, headers={"x-request-id": "private-provider-id"}, json={
            "id": "private-completion-id", "created": 1, "object": "chat.completion",
            "model": "private-model", "usage": {"prompt_tokens": 10, "completion_tokens": 20, "total_tokens": 30},
            "choices": [{"index": 0, "finish_reason": "stop", "message": {
                "role": "assistant", "content": json.dumps(data),
                "refusal": "sensitive-provider-marker" if outcome == "refusal" else None,
            }}],
        })

    provider = AzureOpenAIProvider(
        endpoint="https://example.openai.azure.com", api_key="not-a-real-key",
        model_routes={"test-purpose": "private-deployment"}, transport=httpx2.MockTransport(handler),
    )
    gateway_app = create_app()
    gateway_app.dependency_overrides[get_food_analysis_use_case] = lambda: FoodAnalysisUseCase(provider, 1, "test-purpose")
    transport_client = TestClient(gateway_app, base_url="http://gateway.local")
    client = GatewayClient(client=transport_client)
    try:
        if outcome == "success":
            result = client.analyze_food_text("synthetic description")
            assert result == {"estimate": estimate}
            assert map_gateway_response_to_public(result).model_dump() == {"estimate": estimate}
            visible = json.dumps(result)
        else:
            with pytest.raises(GatewayClientError) as caught:
                client.analyze_food_text("synthetic description")
            assert caught.value.http_status == (429 if outcome == "rate_limit" else 502)
            visible = str(caught.value)
        for marker in ("private-model", "private-deployment", "private-provider-id", "usage", "sensitive-provider-marker"):
            assert marker not in visible
        assert len(calls) == 1
    finally:
        client.close()
        asyncio.run(provider.aclose())
        get_settings.cache_clear()
        get_provider.cache_clear()
