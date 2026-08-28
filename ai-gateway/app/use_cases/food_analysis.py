"""The first gateway use case: text-based food analysis."""

from __future__ import annotations

import asyncio

from pydantic import ValidationError

from app.errors import ProviderOutputInvalidError, ProviderTimeoutError
from app.providers.base import ProviderRequest, StructuredGenerationProvider
from app.schemas.food_analysis import FoodAnalysisEstimate, FoodAnalysisRequest, FoodAnalysisResponse

_TASK = "food_analysis_text"


class FoodAnalysisUseCase:
    """Orchestrates a text food-analysis request against a provider."""

    def __init__(self, provider: StructuredGenerationProvider, timeout_seconds: float):
        self._provider = provider
        self._timeout_seconds = timeout_seconds

    async def execute(self, request: FoodAnalysisRequest) -> FoodAnalysisResponse:
        provider_request = ProviderRequest(
            task=_TASK,
            payload={"food_description": request.food_description},
            timeout_seconds=self._timeout_seconds,
        )

        try:
            response = await asyncio.wait_for(
                self._provider.generate(provider_request), timeout=self._timeout_seconds
            )
        except asyncio.TimeoutError as exc:
            raise ProviderTimeoutError() from exc

        try:
            estimate = FoodAnalysisEstimate.model_validate(response.data)
        except ValidationError as exc:
            raise ProviderOutputInvalidError() from exc

        return FoodAnalysisResponse(estimate=estimate)
