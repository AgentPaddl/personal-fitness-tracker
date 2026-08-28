"""Public request/response contracts for the food analysis use case.

These schemas are the gateway's public contract. They intentionally do not
include any provider or model identifier.
"""

from __future__ import annotations

from pydantic import BaseModel, Field, field_validator


class FoodAnalysisRequest(BaseModel):
    """A text description of a food item or meal to analyze."""

    food_description: str = Field(min_length=1, max_length=2000)

    @field_validator("food_description")
    @classmethod
    def _reject_blank(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("food_description must not be blank.")
        return stripped


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
