"""Tests for Phase 6 production-hardening behavior: service-token
authentication, request-id propagation, and the concurrency limiter.

All credential-free; no real Copilot calls.
"""

from __future__ import annotations

import asyncio

import pytest
from fastapi.testclient import TestClient

from app.concurrency import ConcurrencyLimiter
from app.config import Settings
from app.dependencies import get_food_analysis_use_case
from app.errors import ServiceSaturatedError
from app.main import create_app
from app.providers.base import StructuredGenerationRequest, StructuredGenerationResult, StructuredGenerationProvider
from app.use_cases.food_analysis import FoodAnalysisUseCase

_VALID_DATA = {
    "food_name": "apple",
    "calories": 95.0,
    "protein_grams": 0.5,
    "carbohydrate_grams": 25.0,
    "fat_grams": 0.3,
    "confidence": 0.9,
    "warnings": [],
}


# --- Service-token authentication ---------------------------------------


def test_v1_route_rejects_missing_service_token(monkeypatch):
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.setenv("GATEWAY_SERVICE_TOKEN", "correct-token")
    monkeypatch.setenv("AI_PROVIDER", "copilot")
    monkeypatch.setenv(
        "COPILOT_MODEL_ROUTES_JSON", '{"food_text_v1": "gpt-5", "food_image_v1": "gpt-5"}'
    )

    from app.config import get_settings
    from app.dependencies import get_provider

    get_settings.cache_clear()
    get_provider.cache_clear()

    response = TestClient(create_app(), raise_server_exceptions=False).post(
        "/v1/food-analysis", json={"food_description": "apple"}
    )

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "authentication_required"


def test_v1_route_rejects_wrong_service_token(monkeypatch):
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.setenv("GATEWAY_SERVICE_TOKEN", "correct-token")
    monkeypatch.setenv("AI_PROVIDER", "copilot")
    monkeypatch.setenv(
        "COPILOT_MODEL_ROUTES_JSON", '{"food_text_v1": "gpt-5", "food_image_v1": "gpt-5"}'
    )

    from app.config import get_settings
    from app.dependencies import get_provider

    get_settings.cache_clear()
    get_provider.cache_clear()

    response = TestClient(create_app(), raise_server_exceptions=False).post(
        "/v1/food-analysis",
        json={"food_description": "apple"},
        headers={"X-Service-Token": "wrong-token"},
    )

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "authentication_required"


def test_v1_route_accepts_correct_service_token(monkeypatch):
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.setenv("GATEWAY_SERVICE_TOKEN", "correct-token")
    monkeypatch.setenv("AI_PROVIDER", "copilot")
    monkeypatch.setenv(
        "COPILOT_MODEL_ROUTES_JSON", '{"food_text_v1": "gpt-5", "food_image_v1": "gpt-5"}'
    )

    from app.config import get_settings
    from app.dependencies import get_provider

    get_settings.cache_clear()
    get_provider.cache_clear()

    app = create_app()

    class _StubUseCase:
        async def execute(self, request):
            from app.schemas.food_analysis import FoodAnalysisEstimate, FoodAnalysisResponse

            return FoodAnalysisResponse(estimate=FoodAnalysisEstimate.model_validate(_VALID_DATA))

    app.dependency_overrides[get_food_analysis_use_case] = lambda: _StubUseCase()

    response = TestClient(app, raise_server_exceptions=False).post(
        "/v1/food-analysis",
        json={"food_description": "apple"},
        headers={"X-Service-Token": "correct-token"},
    )

    assert response.status_code == 200


def test_production_requires_gateway_service_token():
    settings = Settings(
        app_env="production",
        ai_provider="copilot",
        copilot_model_routes_json='{"food_text_v1": "gpt-5", "food_image_v1": "gpt-5"}',
        gateway_service_token=None,
    )
    with pytest.raises(ValueError, match="GATEWAY_SERVICE_TOKEN"):
        settings.validate()


# --- Concurrency limit validation ---------------------------------------


def test_ai_provider_max_concurrency_out_of_bounds_rejected():
    settings = Settings(app_env="development", ai_provider_max_concurrency=0)
    with pytest.raises(ValueError, match="AI_PROVIDER_MAX_CONCURRENCY"):
        settings.validate()

    settings = Settings(app_env="development", ai_provider_max_concurrency=21)
    with pytest.raises(ValueError, match="AI_PROVIDER_MAX_CONCURRENCY"):
        settings.validate()


# --- Request-id propagation ----------------------------------------------


def test_response_echoes_provided_request_id(client):
    response = client.post(
        "/v1/food-analysis",
        json={"food_description": "apple"},
        headers={"X-Request-Id": "test-request-id-123"},
    )

    assert response.headers["X-Request-Id"] == "test-request-id-123"


def test_error_response_includes_request_id(dev_env):
    app = create_app()

    class _FailingUseCase:
        async def execute(self, request):
            from app.errors import ProviderTimeoutError

            raise ProviderTimeoutError()

    app.dependency_overrides[get_food_analysis_use_case] = lambda: _FailingUseCase()
    client = TestClient(app, raise_server_exceptions=False)

    response = client.post(
        "/v1/food-analysis",
        json={"food_description": "apple"},
        headers={"X-Request-Id": "req-abc"},
    )

    assert response.json()["error"]["request_id"] == "req-abc"


def test_response_generates_request_id_when_not_provided(client):
    response = client.post("/v1/food-analysis", json={"food_description": "apple"})

    assert response.headers["X-Request-Id"]


# --- Concurrency limiter behavior -----------------------------------------


class _SlowProvider(StructuredGenerationProvider):
    def __init__(self, release_event: asyncio.Event):
        self._release_event = release_event
        self.entered = asyncio.Event()

    async def generate(self, request: StructuredGenerationRequest) -> StructuredGenerationResult:
        self.entered.set()
        await self._release_event.wait()
        return StructuredGenerationResult(data=_VALID_DATA)


def test_concurrency_limiter_rejects_when_saturated():
    async def _run():
        release_event = asyncio.Event()
        provider = _SlowProvider(release_event)
        limiter = ConcurrencyLimiter(max_concurrent=1)
        use_case = FoodAnalysisUseCase(
            provider=provider, timeout_seconds=5.0, model_purpose="food_text_v1", concurrency_limiter=limiter
        )

        from app.schemas.food_analysis import FoodAnalysisRequest

        request = FoodAnalysisRequest(food_description="apple")

        first_task = asyncio.create_task(use_case.execute(request))
        await provider.entered.wait()

        with pytest.raises(ServiceSaturatedError):
            await use_case.execute(request)

        release_event.set()
        await first_task

    asyncio.run(_run())


def test_concurrency_limiter_allows_sequential_requests():
    async def _run():
        release_event = asyncio.Event()
        release_event.set()
        provider = _SlowProvider(release_event)
        limiter = ConcurrencyLimiter(max_concurrent=1)
        use_case = FoodAnalysisUseCase(
            provider=provider, timeout_seconds=5.0, model_purpose="food_text_v1", concurrency_limiter=limiter
        )

        from app.schemas.food_analysis import FoodAnalysisRequest

        request = FoodAnalysisRequest(food_description="apple")

        await use_case.execute(request)
        await use_case.execute(request)  # must not raise: the first slot was released

    asyncio.run(_run())
