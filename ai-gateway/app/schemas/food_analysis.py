"""Public request/response contracts for the food analysis use case.

These schemas are the gateway's public contract. They intentionally do not
include any provider or model identifier.
"""

from __future__ import annotations

import base64
import math

from pydantic import BaseModel, Field, field_validator, model_validator

from app.image_validation import image_content_matches_declared_type

#: Conservative, end-to-end-verified image formats only. The iOS client
#: always re-encodes to JPEG before upload; PNG is accepted for other
#: callers/tests. HEIC is intentionally not accepted here (uncertain
#: support through the SDK's image-attachment path).
SUPPORTED_IMAGE_MEDIA_TYPES = frozenset({"image/jpeg", "image/png"})

#: Conservative cap on the *decoded* image payload. The iOS client resizes
#: and compresses before upload, so a compliant client's photo is always
#: far below this; it exists to bound worst-case memory/latency here and
#: at the backend boundary that forwards to us. Chosen to be <= the
#: smallest `max_prompt_image_size` advertised by our currently-configured
#: vision-capable model (`gpt-5-mini` reports exactly 3145728 bytes as of
#: 2026-08-29) so gateway readiness (`check_ready()`) can be genuinely
#: true rather than optimistic about provider compatibility.
MAX_IMAGE_BYTES = 3 * 1024 * 1024

#: The maximum possible base64-encoded length for a payload that decodes to
#: at most MAX_IMAGE_BYTES bytes (base64 encodes 3 bytes as 4 characters,
#: rounding up - this exactly accounts for padding). Any encoded string
#: longer than this can never decode within the size limit, so it is
#: rejected before spending a full base64 decode/allocation on it.
_MAX_IMAGE_BASE64_LENGTH = 4 * math.ceil(MAX_IMAGE_BYTES / 3)


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
        # Cheap length check first: rejects an oversized payload before
        # ever allocating a decode buffer for it.
        if len(value) > _MAX_IMAGE_BASE64_LENGTH:
            raise ValueError(
                f"data_base64 exceeds the maximum encoded length ({_MAX_IMAGE_BASE64_LENGTH} characters) "
                f"for a {MAX_IMAGE_BYTES}-byte image."
            )
        try:
            decoded = base64.b64decode(value, validate=True)
        except (ValueError, TypeError) as exc:
            raise ValueError("data_base64 must be valid base64.") from exc
        if not decoded:
            raise ValueError("data_base64 must not decode to an empty payload.")
        # Defense-in-depth: the length pre-check above already makes this
        # unreachable for well-formed base64, but is kept as an explicit,
        # authoritative check on the actually-decoded size.
        if len(decoded) > MAX_IMAGE_BYTES:
            raise ValueError(f"Image payload exceeds the {MAX_IMAGE_BYTES}-byte limit.")
        return value

    @model_validator(mode="after")
    def _require_content_matches_declared_type(self) -> "ImageAttachment":
        decoded = base64.b64decode(self.data_base64, validate=True)
        if not image_content_matches_declared_type(decoded, self.media_type):
            raise ValueError(
                "Image content is not a valid, undamaged image matching the declared media_type."
            )
        return self


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
