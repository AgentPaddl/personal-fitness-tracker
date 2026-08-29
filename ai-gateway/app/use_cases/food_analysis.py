"""The first gateway use case: text/image-based food analysis.

This module owns all food-specific orchestration: the instructions sent to
the provider, the desired output schema, and how the raw result is
interpreted. Providers never see any of this domain framing directly; they
only receive the generic ``StructuredGenerationRequest``.
"""

from __future__ import annotations

import asyncio

from pydantic import ValidationError

from app.errors import GatewayError, ProviderOutputInvalidError, ProviderTimeoutError, ProviderUnavailableError
from app.providers.base import Attachment, GenerationMessage, StructuredGenerationRequest, StructuredGenerationProvider
from app.schemas.food_analysis import FoodAnalysisEstimate, FoodAnalysisRequest, FoodAnalysisResponse

_TEXT_SYSTEM_INSTRUCTIONS = (
    "You are a nutrition estimation assistant. Given a short food or meal "
    "description, return a structured nutrition estimate matching the "
    "requested schema. Values are estimates, not authoritative facts."
)

_IMAGE_SYSTEM_INSTRUCTIONS = (
    "You are a nutrition estimation assistant. Given a photo of food (and "
    "optionally a short text description), visually estimate the food "
    "and its portion size, and return a structured nutrition estimate "
    "matching the requested schema. If the image shows multiple foods, "
    "return one combined estimate for the whole visible meal. Values are "
    "estimates, not authoritative facts - reflect any uncertainty about "
    "what is visible using the schema's confidence/warnings fields rather "
    "than refusing to answer."
)


class FoodAnalysisUseCase:
    """Orchestrates a text and/or image food-analysis request against a provider."""

    def __init__(
        self,
        provider: StructuredGenerationProvider,
        timeout_seconds: float,
        model_purpose: str,
        image_model_purpose: str = "food_image_v1",
    ):
        self._provider = provider
        self._timeout_seconds = timeout_seconds
        self._model_purpose = model_purpose
        self._image_model_purpose = image_model_purpose

    async def execute(self, request: FoodAnalysisRequest) -> FoodAnalysisResponse:
        has_image = request.image is not None
        generation_request = StructuredGenerationRequest(
            model_purpose=self._image_model_purpose if has_image else self._model_purpose,
            messages=[
                GenerationMessage(
                    role="system", content=_IMAGE_SYSTEM_INSTRUCTIONS if has_image else _TEXT_SYSTEM_INSTRUCTIONS
                ),
                GenerationMessage(role="user", content=self._build_user_message(request)),
            ],
            output_json_schema=FoodAnalysisEstimate.model_json_schema(),
            timeout_seconds=self._timeout_seconds,
            attachments=self._build_attachments(request),
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
        if request.image is not None and request.food_description:
            return (
                f"Food description: {request.food_description}\n"
                "An image of the food is attached; use both the description and "
                "the image to inform your estimate."
            )
        if request.image is not None:
            return "A photo of the food is attached. Estimate the food and its portion from the image alone."
        return f"Food description: {request.food_description}"

    @staticmethod
    def _build_attachments(request: FoodAnalysisRequest) -> list[Attachment]:
        if request.image is None:
            return []
        return [Attachment(kind="image", media_type=request.image.media_type, data=request.image.data_base64)]
