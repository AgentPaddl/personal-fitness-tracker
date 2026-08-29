import json
import logging

import azure.functions as func
import httpx

from config import get_gateway_base_url

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
    """Distinct from /api/health: readiness = the dependency required to
    serve a real request (the gateway) is actually reachable right now.

    Calls the gateway's own anonymous `/healthz` (never a billed
    generation call) with a short timeout. Never reveals the gateway's URL
    or any other internal configuration in the response body.
    """

    try:
        response = httpx.get(f"{get_gateway_base_url()}/healthz", timeout=3.0)
        gateway_reachable = response.status_code == 200
    except httpx.HTTPError:
        gateway_reachable = False

    if not gateway_reachable:
        logger.warning("readiness check failed: gateway unreachable")
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
