"""Public request/response contracts for the food analysis use case.

These schemas are the gateway's public contract. They intentionally do not
include any provider or model identifier.
"""

from __future__ import annotations

import base64

from pydantic import BaseModel, Field, field_validator, model_validator

#: Conservative, end-to-end-verified image formats only. The iOS client
#: always re-encodes to JPEG before upload; PNG is accepted for other
#: callers/tests. HEIC is intentionally not accepted here (uncertain
#: support through the SDK's image-attachment path).
SUPPORTED_IMAGE_MEDIA_TYPES = frozenset({"image/jpeg", "image/png"})

#: Conservative cap on the *decoded* image payload. The iOS client resizes
#: and compresses before upload, so a compliant client's photo is always
#: far below this; it exists to bound worst-case memory/latency here and
#: at the backend boundary that forwards to us.
MAX_IMAGE_BYTES = 5 * 1024 * 1024


class ImageAttachment(BaseModel):
    """A single inline base64-encoded image, forwarded to the provider as a
    generic attachment. Never persisted; used only for one generation call.
    """

    media_type: str
    data_base64: str = Field(min_length=1)

    @field_validator("media_type")
    @classmethod
    def _require_supported_media_type(cls, value: str) -> str:
        normalized = value.strip().lower()
        if normalized not in SUPPORTED_IMAGE_MEDIA_TYPES:
            raise ValueError(f"Unsupported image media type '{value}'. Supported: {sorted(SUPPORTED_IMAGE_MEDIA_TYPES)}.")
        return normalized

    @field_validator("data_base64")
    @classmethod
    def _require_decodable_and_bounded(cls, value: str) -> str:
        try:
            decoded = base64.b64decode(value, validate=True)
        except (ValueError, TypeError) as exc:
            raise ValueError("data_base64 must be valid base64.") from exc
        if not decoded:
            raise ValueError("data_base64 must not decode to an empty payload.")
        if len(decoded) > MAX_IMAGE_BYTES:
            raise ValueError(f"Image payload exceeds the {MAX_IMAGE_BYTES}-byte limit.")
        return value


class FoodAnalysisRequest(BaseModel):
    """A food item or meal to analyze: text description, an image, or both.

    At least one of ``food_description``/``image`` must be present.
    """

    food_description: str | None = Field(default=None, max_length=2000)
    image: ImageAttachment | None = None

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
    def _require_text_or_image(self) -> "FoodAnalysisRequest":
        if self.food_description is None and self.image is None:
            raise ValueError("Either food_description or image must be provided.")
        return self


class FoodAnalysisEstimate(BaseModel):
    """A structured, bounded nutrition estimate for a single food item."""

    food_name: str = Field(min_length=1, max_length=200)
    calories: float = Field(ge=0, le=10_000)
    protein_grams: float = Field(ge=0, le=1_000)
    carbohydrate_grams: float = Field(ge=0, le=1_000)
    fat_grams: float = Field(ge=0, le=1_000)
    confidence: float = Field(ge=0, le=1)
    warnings: list[str] = Field(default_factory=list, max_length=20)


class FoodAnalysisResponse(BaseModel):
    """Public response envelope. Contains no provider or model details."""

    estimate: FoodAnalysisEstimate
