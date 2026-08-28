"""FastAPI application factory for the Personal AI Gateway."""

from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError
from fastapi.requests import Request
from fastapi.responses import JSONResponse

from app.api.routes import health_router, v1_router
from app.dependencies import get_provider
from app.errors import GatewayError, InternalGatewayError, RequestValidationFailedError


@asynccontextmanager
async def _lifespan(app: FastAPI):
    yield
    # Releases any long-lived provider resources (e.g. a Copilot CLI
    # process/connection) instead of leaking them on process exit. Only
    # closes a provider that was actually built; never builds one just to
    # shut it down.
    if get_provider.cache_info().currsize:
        try:
            await get_provider().aclose()
        except Exception:
            pass


def create_app() -> FastAPI:
    app = FastAPI(title="Personal AI Gateway", version="1.0.0", lifespan=_lifespan)

    app.include_router(health_router)
    app.include_router(v1_router)

    @app.exception_handler(GatewayError)
    async def _handle_gateway_error(_: Request, exc: GatewayError) -> JSONResponse:
        # Normalized, public-safe error shape; never leaks provider details.
        return JSONResponse(
            status_code=exc.http_status,
            content={"error": {"code": exc.code, "message": exc.message}},
        )

    @app.exception_handler(RequestValidationError)
    async def _handle_request_validation_error(_: Request, exc: RequestValidationError) -> JSONResponse:
        # Keep FastAPI's built-in body/query validation on the same
        # normalized error envelope as the rest of the public API.
        normalized = RequestValidationFailedError("The request body failed validation.")
        return JSONResponse(
            status_code=normalized.http_status,
            content={"error": {"code": normalized.code, "message": normalized.message}},
        )

    @app.exception_handler(Exception)
    async def _handle_unexpected_error(_: Request, exc: Exception) -> JSONResponse:
        # Final safe boundary: no raw exception detail ever reaches the client.
        fallback = InternalGatewayError()
        return JSONResponse(
            status_code=fallback.http_status,
            content={"error": {"code": fallback.code, "message": fallback.message}},
        )

    return app


app = create_app()
