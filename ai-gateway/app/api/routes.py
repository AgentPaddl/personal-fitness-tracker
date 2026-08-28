"""HTTP routes for the Personal AI Gateway.

Public responses never include provider or model identifiers.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends

from app.dependencies import get_food_analysis_use_case
from app.schemas.food_analysis import FoodAnalysisRequest, FoodAnalysisResponse
from app.security import require_authenticated_caller
from app.use_cases.food_analysis import FoodAnalysisUseCase

health_router = APIRouter()
v1_router = APIRouter(prefix="/v1", dependencies=[Depends(require_authenticated_caller)])


@health_router.get("/healthz")
async def healthz() -> dict[str, str]:
    return {"status": "ok"}


@health_router.get("/readyz")
async def readyz() -> dict[str, str]:
    # Confirms the gateway can build its configured provider without error.
    from app.dependencies import get_provider

    get_provider()
    return {"status": "ready"}


@v1_router.post("/food-analysis", response_model=FoodAnalysisResponse)
async def analyze_food(
    request: FoodAnalysisRequest,
    use_case: FoodAnalysisUseCase = Depends(get_food_analysis_use_case),
) -> FoodAnalysisResponse:
    return await use_case.execute(request)
