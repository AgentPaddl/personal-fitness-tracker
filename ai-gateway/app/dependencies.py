"""FastAPI dependency wiring: settings -> provider -> use case."""

from __future__ import annotations

from functools import lru_cache

from app.config import Settings, get_settings
from app.providers.base import StructuredGenerationProvider
from app.providers.fake import FakeProvider
from app.use_cases.food_analysis import FoodAnalysisUseCase


def _build_provider(settings: Settings) -> StructuredGenerationProvider:
    if settings.ai_provider == "fake":
        return FakeProvider()
    if settings.ai_provider == "copilot":
        # Imported lazily so the optional Copilot SDK dependency is only
        # required when it is actually configured/used.
        from app.providers.github_copilot import GitHubCopilotProvider

        return GitHubCopilotProvider(
            model_routes=settings.copilot_model_routes(),
            github_token=settings.copilot_github_token,
            vision_required_purposes=frozenset({settings.food_image_model_purpose}),
        )
    # Unreachable: Settings.validate() already rejects other values.
    raise ValueError(f"Unsupported AI_PROVIDER '{settings.ai_provider}'.")


@lru_cache
def get_provider() -> StructuredGenerationProvider:
    return _build_provider(get_settings())


def get_food_analysis_use_case() -> FoodAnalysisUseCase:
    settings = get_settings()
    return FoodAnalysisUseCase(
        provider=get_provider(),
        timeout_seconds=settings.ai_provider_timeout_seconds,
        model_purpose=settings.food_text_model_purpose,
        image_model_purpose=settings.food_image_model_purpose,
    )
