"""HTTP routes for the Personal AI Gateway.

Public responses never include provider or model identifiers.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends

from app.dependencies import get_food_analysis_use_case, get_provider
from app.errors import ProviderUnavailableError
from app.providers.base import StructuredGenerationProvider
from app.schemas.food_analysis import FoodAnalysisRequest, FoodAnalysisResponse
from app.security import require_authenticated_caller
from app.use_cases.food_analysis import FoodAnalysisUseCase

health_router = APIRouter()
v1_router = APIRouter(prefix="/v1", dependencies=[Depends(require_authenticated_caller)])


@health_router.get("/healthz")
async def healthz() -> dict[str, str]:
    return {"status": "ok"}


@health_router.get("/readyz")
async def readyz(provider: StructuredGenerationProvider = Depends(get_provider)) -> dict[str, str]:
    # Uses the provider's own cheap readiness check (never a billed
    # generation call); a real adapter can later report meaningful
    # connectivity/auth health here.
    try:
        ready = await provider.check_ready()
    except Exception:
        ready = False

    if not ready:
        raise ProviderUnavailableError()

    return {"status": "ready"}


@v1_router.post("/food-analysis", response_model=FoodAnalysisResponse)
async def analyze_food(
    request: FoodAnalysisRequest,
    use_case: FoodAnalysisUseCase = Depends(get_food_analysis_use_case),
) -> FoodAnalysisResponse:
    return await use_case.execute(request)
