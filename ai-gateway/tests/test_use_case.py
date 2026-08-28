"""Unit tests for FoodAnalysisUseCase using in-test stub providers.

No magic control strings; each scenario is a distinct, explicit provider
implementation. Timeout enforcement uses a provider that genuinely sleeps
longer than a short configured timeout, proving real cancellation rather
than a hardcoded shortcut.
"""

from __future__ import annotations

import asyncio

import pytest

from app.errors import ProviderOutputInvalidError, ProviderTimeoutError, ProviderUnavailableError
from app.providers.base import StructuredGenerationRequest, StructuredGenerationResult, StructuredGenerationProvider
from app.schemas.food_analysis import FoodAnalysisRequest
from app.use_cases.food_analysis import FoodAnalysisUseCase

_VALID_DATA = {
    "food_name": "chicken breast",
    "calories": 200.0,
    "protein_grams": 30.0,
    "carbohydrate_grams": 0.0,
    "fat_grams": 5.0,
    "confidence": 0.9,
    "warnings": [],
}


class _StubProvider(StructuredGenerationProvider):
    def __init__(self, data: dict | None = None, raise_exc: Exception | None = None):
        self._data = data
        self._raise_exc = raise_exc

    async def generate(self, request: StructuredGenerationRequest) -> StructuredGenerationResult:
        if self._raise_exc is not None:
            raise self._raise_exc
        return StructuredGenerationResult(data=self._data or {})


class _SlowProvider(StructuredGenerationProvider):
    """Genuinely waits past a short timeout, then would return valid data."""

    def __init__(self, delay_seconds: float):
        self.delay_seconds = delay_seconds
        self.completed = False

    async def generate(self, request: StructuredGenerationRequest) -> StructuredGenerationResult:
        await asyncio.sleep(self.delay_seconds)
        self.completed = True
        return StructuredGenerationResult(data=_VALID_DATA)


def _food_request() -> FoodAnalysisRequest:
    return FoodAnalysisRequest(food_description="grilled chicken breast")


def test_execute_returns_valid_estimate():
    use_case = FoodAnalysisUseCase(
        provider=_StubProvider(data=_VALID_DATA), timeout_seconds=1.0, model_purpose="food_text_v1"
    )

    response = asyncio.run(use_case.execute(_food_request()))

    assert response.estimate.food_name == "chicken breast"


def test_execute_rejects_invalid_provider_output():
    invalid_data = {**_VALID_DATA, "calories": -1, "confidence": 2.0}
    use_case = FoodAnalysisUseCase(
        provider=_StubProvider(data=invalid_data), timeout_seconds=1.0, model_purpose="food_text_v1"
    )

    with pytest.raises(ProviderOutputInvalidError):
        asyncio.run(use_case.execute(_food_request()))


def test_execute_normalizes_unexpected_provider_exception():
    use_case = FoodAnalysisUseCase(
        provider=_StubProvider(raise_exc=RuntimeError("raw sdk failure")),
        timeout_seconds=1.0,
        model_purpose="food_text_v1",
    )

    with pytest.raises(ProviderUnavailableError):
        asyncio.run(use_case.execute(_food_request()))


def test_execute_enforces_real_timeout_and_cancels_provider():
    slow_provider = _SlowProvider(delay_seconds=1.0)
    use_case = FoodAnalysisUseCase(provider=slow_provider, timeout_seconds=0.05, model_purpose="food_text_v1")

    with pytest.raises(ProviderTimeoutError):
        asyncio.run(use_case.execute(_food_request()))

    # The provider's sleep must have been cancelled, not merely ignored.
    assert slow_provider.completed is False
