import json
import logging

import azure.functions as func
from pydantic import ValidationError

from config import get_gateway_base_url, get_gateway_timeout_seconds, is_development_mode
from gateway_client import GatewayClient, GatewayClientError
from image_validation import image_content_matches_declared_type
from schemas import (
    MAX_FOOD_DESCRIPTION_LENGTH,
    MAX_IMAGE_BYTES,
    SUPPORTED_IMAGE_MIME_TYPES,
    FoodAnalysisPublicRequest,
    map_gateway_response_to_public,
)

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

    content_type = (req.headers.get("Content-Type") or "").lower()
    if content_type.startswith("multipart/form-data"):
        return _handle_image_analysis(req)
    return _handle_text_analysis(req)


def _handle_text_analysis(req: func.HttpRequest) -> func.HttpResponse:
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

    return _respond_with_gateway_result(gateway_response)


def _handle_image_analysis(req: func.HttpRequest) -> func.HttpResponse:
    # Malformed multipart bodies raise inside werkzeug's parser (triggered
    # lazily by accessing .files/.form); never let that raw exception
    # escape as an unhandled 500.
    try:
        files = req.files
        form = req.form
    except Exception:
        return _error_response(400, "invalid_request", "Request body must be valid multipart/form-data.")

    image_file = files.get("image") if files else None
    if image_file is None:
        return _error_response(400, "image_required", "An 'image' file field is required.")

    # Bounded read: never load more than MAX_IMAGE_BYTES + 1 bytes into
    # memory here, regardless of how large the uploaded file claims/turns
    # out to be. This bounds *this* processing step only - by the time this
    # code runs, the Azure Functions host/worker has already received and
    # buffered the full HTTP request body (see backend/AGENTS.md for the
    # precise, non-overclaiming statement of what this check does and does
    # not guarantee).
    image_bytes = _read_bounded(image_file.stream, MAX_IMAGE_BYTES)
    if not image_bytes:
        return _error_response(400, "image_empty", "The uploaded image must not be empty.")
    if len(image_bytes) > MAX_IMAGE_BYTES:
        return _error_response(
            413, "image_too_large", f"The uploaded image exceeds the {MAX_IMAGE_BYTES}-byte limit."
        )

    mime_type = (image_file.mimetype or "").lower()
    if mime_type not in SUPPORTED_IMAGE_MIME_TYPES:
        return _error_response(
            415,
            "unsupported_media_type",
            f"Unsupported image type '{mime_type}'. Supported: {sorted(SUPPORTED_IMAGE_MIME_TYPES)}.",
        )

    if not image_content_matches_declared_type(image_bytes, mime_type):
        return _error_response(
            400,
            "image_content_invalid",
            "The uploaded file is not a valid, undamaged image of the declared type.",
        )

    raw_description = (form.get("food_description") if form else None) or None
    food_description = raw_description.strip() if raw_description else None
    if food_description and len(food_description) > MAX_FOOD_DESCRIPTION_LENGTH:
        return _error_response(
            400, "invalid_request", f"food_description must be at most {MAX_FOOD_DESCRIPTION_LENGTH} characters."
        )

    client = GatewayClient(base_url=get_gateway_base_url(), timeout=get_gateway_timeout_seconds())
    try:
        gateway_response = client.analyze_food_image(image_bytes, mime_type, food_description=food_description)
    except GatewayClientError as exc:
        logger.warning("gateway request failed with code=%s", exc.code)
        return _error_response(exc.http_status, exc.code, exc.message)
    finally:
        client.close()

    return _respond_with_gateway_result(gateway_response)


def _respond_with_gateway_result(gateway_response: dict) -> func.HttpResponse:
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


def _read_bounded(stream, max_bytes: int) -> bytes:
    """Reads at most `max_bytes + 1` bytes from `stream`, never the whole
    (potentially much larger) stream. The `+ 1` lets the caller distinguish
    "exactly at the limit" from "over the limit" without reading further.
    """

    return stream.read(max_bytes + 1)


def _error_response(status_code: int, code: str, message: str) -> func.HttpResponse:
    return func.HttpResponse(
        json.dumps({"error": {"code": code, "message": message}}),
        status_code=status_code,
        mimetype="application/json",
    )
