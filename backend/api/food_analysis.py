import json
import logging

import azure.functions as func

from config import get_gateway_base_url, get_gateway_timeout_seconds
from gateway_client import GatewayClient, GatewayClientError

bp = func.Blueprint()

logger = logging.getLogger(__name__)


@bp.route(route="food-analysis", methods=["POST"], auth_level=func.AuthLevel.ANONYMOUS)
def food_analysis(req: func.HttpRequest) -> func.HttpResponse:
    # DEVELOPMENT-ONLY: anonymous auth. Add real authentication/authorization
    # before this route is reachable outside a trusted local environment.
    try:
        body = req.get_json()
    except ValueError:
        return _error_response(400, "invalid_request", "Request body must be valid JSON.")

    food_description = body.get("food_description") if isinstance(body, dict) else None
    if not isinstance(food_description, str) or not food_description.strip():
        return _error_response(
            400, "invalid_request", "food_description is required and must be a non-empty string."
        )

    client = GatewayClient(base_url=get_gateway_base_url(), timeout=get_gateway_timeout_seconds())
    try:
        result = client.analyze_food_text(food_description)
    except GatewayClientError as exc:
        logger.warning("gateway request failed with code=%s", exc.code)
        return _error_response(502, "gateway_error", "The AI gateway could not complete this request.")
    finally:
        client.close()

    return func.HttpResponse(json.dumps(result), status_code=200, mimetype="application/json")


def _error_response(status_code: int, code: str, message: str) -> func.HttpResponse:
    return func.HttpResponse(
        json.dumps({"error": {"code": code, "message": message}}),
        status_code=status_code,
        mimetype="application/json",
    )
