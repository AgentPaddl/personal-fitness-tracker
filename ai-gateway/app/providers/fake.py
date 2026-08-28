"""Deterministic provider used for local development and tests.

FakeProvider never calls any real AI service and requires no credentials.
It supports a few description markers so tests can exercise error paths:

- ``__TIMEOUT__``   -> raises ProviderTimeoutError
- ``__UNAVAILABLE__`` -> raises ProviderUnavailableError
- ``__INVALID__``   -> returns schema-invalid data (out-of-bounds values)
"""

from __future__ import annotations

from app.errors import ProviderTimeoutError, ProviderUnavailableError
from app.providers.base import ProviderRequest, ProviderResponse, StructuredGenerationProvider

_SUPPORTED_TASKS = frozenset({"food_analysis_text"})


class FakeProvider(StructuredGenerationProvider):
    async def generate(self, request: ProviderRequest) -> ProviderResponse:
        if request.task not in _SUPPORTED_TASKS:
            raise ProviderUnavailableError()

        description = str(request.payload.get("food_description", ""))

        if "__TIMEOUT__" in description:
            raise ProviderTimeoutError()
        if "__UNAVAILABLE__" in description:
            raise ProviderUnavailableError()
        if "__INVALID__" in description:
            # Deliberately schema-invalid: negative calories, blank name.
            return ProviderResponse(
                data={
                    "food_name": "",
                    "calories": -1,
                    "protein_grams": 0,
                    "carbohydrate_grams": 0,
                    "fat_grams": 0,
                    "confidence": 2.0,
                    "warnings": [],
                }
            )

        seed = sum(ord(char) for char in description) or 1
        warnings: list[str] = []
        if len(description) < 4:
            warnings.append("food_description is very short; estimate may be unreliable.")

        return ProviderResponse(
            data={
                "food_name": description[:200],
                "calories": float(50 + seed % 900),
                "protein_grams": float(seed % 60),
                "carbohydrate_grams": float(seed % 120),
                "fat_grams": float(seed % 40),
                "confidence": round(0.5 + (seed % 50) / 100, 2),
                "warnings": warnings,
            }
        )
