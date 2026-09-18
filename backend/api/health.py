import json
import logging
import os

import azure.functions as func
import httpx

from config import get_gateway_base_url, get_gateway_service_token

bp = func.Blueprint()

logger = logging.getLogger(__name__)


@bp.route(route="health", methods=["GET"], auth_level=func.AuthLevel.ANONYMOUS)
def health(req: func.HttpRequest) -> func.HttpResponse:
    # Health = "this process is alive", nothing more. Never reveals the
    # gateway URL or any other internal configuration.
    return func.HttpResponse(
        json.dumps({"status": "ok"}),
        status_code=200,
        mimetype="application/json",
    )


@bp.route(route="readiness", methods=["GET"], auth_level=func.AuthLevel.ANONYMOUS)
def readiness(req: func.HttpRequest) -> func.HttpResponse:
    """Distinct from /api/health: readiness = the gateway can actually
    serve a real request right now - including its own Copilot auth and
    vision-capable model-routing checks (its `/readyz`, not just process
    liveness via `/healthz`). Still never a billed generation call. Never
    reveals the gateway's URL, provider, or model identifiers in the
    response body.
    """

    try:
        options = {}
        if os.environ.get("AI_API_ONLY_ENABLED", "false") != "false":
            from workload_identity import gateway_access_token

            if os.environ.get("AI_API_ONLY_ENABLED") != "true":
                raise ValueError()
            options = {"headers": {"Authorization": "Bearer " + gateway_access_token(),
                                   "X-Service-Token": get_gateway_service_token() or ""}, "follow_redirects": False}
        response = httpx.get(f"{get_gateway_base_url()}/readyz", timeout=3.0, **options)
        gateway_ready = response.status_code == 200
    except Exception:
        gateway_ready = False

    if not gateway_ready:
        logger.warning("readiness check failed: gateway not ready")
        return func.HttpResponse(
            json.dumps({"status": "not_ready"}),
            status_code=503,
            mimetype="application/json",
        )

    return func.HttpResponse(
        json.dumps({"status": "ready"}),
        status_code=200,
        mimetype="application/json",
    )
