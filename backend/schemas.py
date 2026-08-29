"""Backend-owned public API contract for food analysis.

The backend defines and validates its own request/response schemas rather
than forwarding the gateway's JSON verbatim. Only the fields declared here
are ever returned to the client; unknown/internal fields from the gateway
(provider name, model, token usage, debugging data, etc.) are dropped by
construction because the mapping only ever reads the declared attributes.
"""

from __future__ import annotations

from pydantic import BaseModel, Field, field_validator

#: Conservative, end-to-end-verified image formats only. Matches the
#: gateway's own accepted set (`ai-gateway/app/schemas/food_analysis.py`).
#: The iOS client always re-encodes to JPEG before upload; PNG is accepted
#: for other callers/tests. HEIC is intentionally not accepted.
SUPPORTED_IMAGE_MIME_TYPES = frozenset({"image/jpeg", "image/png"})

#: Conservative cap on the raw uploaded file. The iOS client resizes and
#: compresses before upload, so a compliant client's photo is always far
#: below this. Matches the gateway's own `MAX_IMAGE_BYTES` (chosen to fit
#: within the currently-configured vision model's advertised
#: `max_prompt_image_size` - see `ai-gateway/app/schemas/food_analysis.py`).
MAX_IMAGE_BYTES = 3 * 1024 * 1024

#: Maximum length for the optional text field accompanying an image upload,
#: matching the text-only contract's limit.
MAX_FOOD_DESCRIPTION_LENGTH = 2000


class FoodAnalysisPublicRequest(BaseModel):
    food_description: str = Field(min_length=1, max_length=2000)

    @field_validator("food_description")
    @classmethod
    def _reject_blank(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("food_description must not be blank.")
        return stripped


class FoodAnalysisPublicEstimate(BaseModel):
    food_name: str = Field(min_length=1, max_length=200)
    calories: float = Field(ge=0, le=10_000)
    protein_grams: float = Field(ge=0, le=1_000)
    carbohydrate_grams: float = Field(ge=0, le=1_000)
    fat_grams: float = Field(ge=0, le=1_000)
    confidence: float = Field(ge=0, le=1)
    warnings: list[str] = Field(default_factory=list, max_length=20)


class FoodAnalysisPublicResponse(BaseModel):
    estimate: FoodAnalysisPublicEstimate


def map_gateway_response_to_public(gateway_response: object) -> FoodAnalysisPublicResponse:
    """Explicitly map a validated internal gateway response to the public contract.

    Raises ``pydantic.ValidationError`` if the gateway response does not
    contain a conforming estimate; callers must treat that as an upstream
    error, never as trusted data to pass through.
    """

    if not isinstance(gateway_response, dict):
        raise ValueError("Gateway response must be a JSON object.")

    estimate = FoodAnalysisPublicEstimate.model_validate(gateway_response.get("estimate"))
    return FoodAnalysisPublicResponse(estimate=estimate)
