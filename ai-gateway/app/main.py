"""FastAPI application factory for the Personal AI Gateway."""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.requests import Request
from fastapi.responses import JSONResponse

from app.api.routes import health_router, v1_router
from app.errors import GatewayError


def create_app() -> FastAPI:
    app = FastAPI(title="Personal AI Gateway", version="1.0.0")

    app.include_router(health_router)
    app.include_router(v1_router)

    @app.exception_handler(GatewayError)
    async def _handle_gateway_error(_: Request, exc: GatewayError) -> JSONResponse:
        # Normalized, public-safe error shape; never leaks provider details.
        return JSONResponse(
            status_code=exc.http_status,
            content={"error": {"code": exc.code, "message": exc.message}},
        )

    return app


app = create_app()
