"""Backend-owned public API contract for food analysis.

The backend defines and validates its own request/response schemas rather
than forwarding the gateway's JSON verbatim. Only the fields declared here
are ever returned to the client; unknown/internal fields from the gateway
(provider name, model, token usage, debugging data, etc.) are dropped by
construction because the mapping only ever reads the declared attributes.
"""

from __future__ import annotations

from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

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

MAX_ESTIMATE_NOTES = 20
MAX_ESTIMATE_NOTE_LENGTH = 500

EstimateNote = Annotated[str, Field(min_length=1, max_length=MAX_ESTIMATE_NOTE_LENGTH)]


class FoodAnalysisPublicEstimate(BaseModel):
    food_name: str = Field(min_length=1, max_length=200)
    calories: float = Field(ge=0, le=10_000)
    protein_grams: float = Field(ge=0, le=1_000)
    carbohydrate_grams: float = Field(ge=0, le=1_000)
    fat_grams: float = Field(ge=0, le=1_000)
    confidence: float = Field(ge=0, le=1)
    warnings: list[EstimateNote] = Field(default_factory=list, max_length=MAX_ESTIMATE_NOTES)
    assumptions: list[EstimateNote] = Field(default_factory=list, max_length=MAX_ESTIMATE_NOTES)


class RefinementCurrentEstimate(FoodAnalysisPublicEstimate):
    """Complete current review state required for a stateless refinement."""

    model_config = ConfigDict(extra="forbid")

    warnings: list[EstimateNote] = Field(max_length=MAX_ESTIMATE_NOTES)
    assumptions: list[EstimateNote] = Field(max_length=MAX_ESTIMATE_NOTES)


class FoodAnalysisPublicRefinement(BaseModel):
    """Bounded text correction for one existing nutrition estimate."""

    model_config = ConfigDict(extra="forbid")

    correction_text: str = Field(min_length=1, max_length=1000)
    current_estimate: RefinementCurrentEstimate
    source_kind: Literal["text", "image", "text_and_image"]
    iteration: int = Field(strict=True, ge=1, le=3)

    @field_validator("correction_text")
    @classmethod
    def _reject_blank_correction(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("correction_text must not be blank.")
        return stripped


class FoodAnalysisPublicRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    food_description: str | None = Field(default=None, max_length=MAX_FOOD_DESCRIPTION_LENGTH)
    refinement: FoodAnalysisPublicRefinement | None = None

    @field_validator("food_description")
    @classmethod
    def _reject_blank(cls, value: str | None) -> str | None:
        if value is None:
            return None
        stripped = value.strip()
        if not stripped:
            raise ValueError("food_description must not be blank.")
        return stripped

    @model_validator(mode="after")
    def _validate_mode(self) -> "FoodAnalysisPublicRequest":
        if self.refinement is None:
            if self.food_description is None:
                raise ValueError("food_description is required for an initial text analysis.")
            return self

        has_original_text = self.food_description is not None
        if self.refinement.source_kind == "image" and has_original_text:
            raise ValueError("source_kind 'image' must not include food_description.")
        if self.refinement.source_kind in {"text", "text_and_image"} and not has_original_text:
            raise ValueError(
                f"source_kind '{self.refinement.source_kind}' requires the original food_description."
            )
        return self


class FoodAnalysisPublicResponse(BaseModel):
    estimate: FoodAnalysisPublicEstimate


def map_public_refinement_to_gateway(request: FoodAnalysisPublicRequest) -> dict:
    """Map only validated, allow-listed public refinement fields."""

    refinement = request.refinement
    if refinement is None:
        raise ValueError("A refinement request is required.")

    estimate = refinement.current_estimate
    payload = {
        "refinement": {
            "correction_text": refinement.correction_text,
            "current_estimate": {
                "food_name": estimate.food_name,
                "calories": estimate.calories,
                "protein_grams": estimate.protein_grams,
                "carbohydrate_grams": estimate.carbohydrate_grams,
                "fat_grams": estimate.fat_grams,
                "confidence": estimate.confidence,
                "warnings": estimate.warnings,
                "assumptions": estimate.assumptions,
            },
            "source_kind": refinement.source_kind,
            "iteration": refinement.iteration,
        }
    }
    if request.food_description is not None:
        payload["food_description"] = request.food_description
    return payload


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
