"""The first gateway use case: text-based food analysis.

This module owns all food-specific orchestration: the instructions sent to
the provider, the desired output schema, and how the raw result is
interpreted. Providers never see any of this domain framing directly; they
only receive the generic ``StructuredGenerationRequest``.
"""

from __future__ import annotations

import asyncio

from pydantic import ValidationError

from app.errors import GatewayError, ProviderOutputInvalidError, ProviderTimeoutError, ProviderUnavailableError
from app.providers.base import GenerationMessage, StructuredGenerationRequest, StructuredGenerationProvider
from app.schemas.food_analysis import FoodAnalysisEstimate, FoodAnalysisRequest, FoodAnalysisResponse

_SYSTEM_INSTRUCTIONS = (
    "You are a nutrition estimation assistant. Given a short food or meal "
    "description, return a structured nutrition estimate matching the "
    "requested schema. Values are estimates, not authoritative facts."
)


class FoodAnalysisUseCase:
    """Orchestrates a text food-analysis request against a provider."""

    def __init__(
        self,
        provider: StructuredGenerationProvider,
        timeout_seconds: float,
        model_purpose: str,
    ):
        self._provider = provider
        self._timeout_seconds = timeout_seconds
        self._model_purpose = model_purpose

    async def execute(self, request: FoodAnalysisRequest) -> FoodAnalysisResponse:
        generation_request = StructuredGenerationRequest(
            model_purpose=self._model_purpose,
            messages=[
                GenerationMessage(role="system", content=_SYSTEM_INSTRUCTIONS),
                GenerationMessage(role="user", content=self._build_user_message(request)),
            ],
            output_json_schema=FoodAnalysisEstimate.model_json_schema(),
            timeout_seconds=self._timeout_seconds,
        )

        result = await self._generate_with_timeout(generation_request)

        try:
            estimate = FoodAnalysisEstimate.model_validate(result.data)
        except ValidationError as exc:
            raise ProviderOutputInvalidError() from exc

        return FoodAnalysisResponse(estimate=estimate)

    async def _generate_with_timeout(self, generation_request: StructuredGenerationRequest):
        try:
            return await asyncio.wait_for(
                self._provider.generate(generation_request), timeout=self._timeout_seconds
            )
        except asyncio.TimeoutError as exc:
            raise ProviderTimeoutError() from exc
        except GatewayError:
            raise
        except Exception as exc:
            # Final normalization boundary: a real provider adapter's raw
            # transport/SDK exceptions must never leak past the use case.
            raise ProviderUnavailableError() from exc

    @staticmethod
    def _build_user_message(request: FoodAnalysisRequest) -> str:
        return f"Food description: {request.food_description}"
