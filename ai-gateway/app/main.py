"""FastAPI application factory for the Personal AI Gateway."""

from __future__ import annotations

import logging
import time
import uuid
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError
from fastapi.requests import Request
from fastapi.responses import JSONResponse

from app.api.routes import health_router, v1_router
from app.dependencies import get_provider
from app.errors import GatewayError, InternalGatewayError, RequestValidationFailedError

logger = logging.getLogger("app.request")

#: Header the backend forwards its own correlation ID on. Never contains
#: food/image content - just an opaque identifier for cross-service log
#: correlation.
_REQUEST_ID_HEADER = "X-Request-Id"


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

    @app.middleware("http")
    async def _request_logging(request: Request, call_next):
        # Reuses the backend's correlation ID if forwarded, otherwise mints
        # one. Never logs request/response bodies (food descriptions,
        # images, model output) - only structural metadata.
        request_id = request.headers.get(_REQUEST_ID_HEADER) or str(uuid.uuid4())
        request.state.request_id = request_id
        start = time.perf_counter()
        try:
            response = await call_next(request)
        except Exception:
            latency_ms = round((time.perf_counter() - start) * 1000, 1)
            logger.warning(
                "request failed path=%s method=%s request_id=%s latency_ms=%s",
                request.url.path, request.method, request_id, latency_ms,
            )
            raise
        latency_ms = round((time.perf_counter() - start) * 1000, 1)
        response.headers[_REQUEST_ID_HEADER] = request_id
        logger.info(
            "request path=%s method=%s status=%s request_id=%s latency_ms=%s",
            request.url.path, request.method, response.status_code, request_id, latency_ms,
        )
        return response

    app.include_router(health_router)
    app.include_router(v1_router)

    @app.exception_handler(GatewayError)
    async def _handle_gateway_error(request: Request, exc: GatewayError) -> JSONResponse:
        # Normalized, public-safe error shape; never leaks provider details.
        # Includes the correlation ID only - never internal error detail.
        request_id = getattr(request.state, "request_id", None)
        return JSONResponse(
            status_code=exc.http_status,
            content={"error": {"code": exc.code, "message": exc.message, "request_id": request_id}},
        )

    @app.exception_handler(RequestValidationError)
    async def _handle_request_validation_error(request: Request, exc: RequestValidationError) -> JSONResponse:
        # Keep FastAPI's built-in body/query validation on the same
        # normalized error envelope as the rest of the public API.
        normalized = RequestValidationFailedError("The request body failed validation.")
        request_id = getattr(request.state, "request_id", None)
        return JSONResponse(
            status_code=normalized.http_status,
            content={"error": {"code": normalized.code, "message": normalized.message, "request_id": request_id}},
        )

    @app.exception_handler(Exception)
    async def _handle_unexpected_error(request: Request, exc: Exception) -> JSONResponse:
        # Final safe boundary: no raw exception detail ever reaches the client.
        fallback = InternalGatewayError()
        request_id = getattr(request.state, "request_id", None)
        return JSONResponse(
            status_code=fallback.http_status,
            content={"error": {"code": fallback.code, "message": fallback.message, "request_id": request_id}},
        )

    return app


app = create_app()
