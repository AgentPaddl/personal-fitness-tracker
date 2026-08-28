import json
import logging

import azure.functions as func
from pydantic import ValidationError

from config import get_gateway_base_url, get_gateway_timeout_seconds, is_development_mode
from gateway_client import GatewayClient, GatewayClientError
from schemas import FoodAnalysisPublicRequest, map_gateway_response_to_public

bp = func.Blueprint()

logger = logging.getLogger(__name__)


@bp.route(route="food-analysis", methods=["POST"], auth_level=func.AuthLevel.ANONYMOUS)
def food_analysis(req: func.HttpRequest) -> func.HttpResponse:
    # DEVELOPMENT-ONLY: this route has no production authentication yet, so
    # it fails closed unless APP_ENV=development is explicitly set. Add real
    # authentication/authorization before removing this gate.
    if not is_development_mode():
        return _error_response(
            403,
            "not_implemented",
            "This endpoint is only available with APP_ENV=development until "
            "production authentication is implemented.",
        )

    try:
        body = req.get_json()
    except ValueError:
        return _error_response(400, "invalid_request", "Request body must be valid JSON.")

    try:
        public_request = FoodAnalysisPublicRequest.model_validate(body)
    except ValidationError:
        return _error_response(
            400, "invalid_request", "food_description is required and must be a 1-2000 character string."
        )

    client = GatewayClient(base_url=get_gateway_base_url(), timeout=get_gateway_timeout_seconds())
    try:
        gateway_response = client.analyze_food_text(public_request.food_description)
    except GatewayClientError as exc:
        logger.warning("gateway request failed with code=%s", exc.code)
        return _error_response(exc.http_status, exc.code, exc.message)
    finally:
        client.close()

    try:
        public_response = map_gateway_response_to_public(gateway_response)
    except (ValueError, TypeError):
        logger.warning("gateway returned an unexpected response shape")
        return _error_response(
            502, "gateway_invalid_response", "The AI gateway returned an unexpected response."
        )

    return func.HttpResponse(
        public_response.model_dump_json(), status_code=200, mimetype="application/json"
    )


def _error_response(status_code: int, code: str, message: str) -> func.HttpResponse:
    return func.HttpResponse(
        json.dumps({"error": {"code": code, "message": message}}),
        status_code=status_code,
        mimetype="application/json",
    )
