import json
import logging
import time
import uuid

import azure.functions as func
from pydantic import ValidationError

from config import get_gateway_base_url, get_gateway_service_token, get_gateway_timeout_seconds
from gateway_client import GatewayClient, GatewayClientError
from image_validation import image_content_matches_declared_type
from schemas import (
    MAX_FOOD_DESCRIPTION_LENGTH,
    MAX_IMAGE_BYTES,
    SUPPORTED_IMAGE_MIME_TYPES,
    FoodAnalysisPublicRequest,
    map_gateway_response_to_public,
)
from security import caller_is_authenticated

bp = func.Blueprint()

logger = logging.getLogger(__name__)

_REQUEST_ID_HEADER = "X-Request-Id"


@bp.route(route="food-analysis", methods=["POST"], auth_level=func.AuthLevel.ANONYMOUS)
def food_analysis(req: func.HttpRequest) -> func.HttpResponse:
    request_id = req.headers.get(_REQUEST_ID_HEADER) or str(uuid.uuid4())
    start = time.perf_counter()

    if not caller_is_authenticated(req.headers.get("X-API-Key")):
        return _log_and_respond(
            request_id, start, "unknown",
            _error_response(401, "authentication_required", "A valid API key is required.", request_id),
        )

    content_type = (req.headers.get("Content-Type") or "").lower()
    if content_type.startswith("multipart/form-data"):
        response = _handle_image_analysis(req, request_id)
        use_case = "image"
    else:
        response = _handle_text_analysis(req, request_id)
        use_case = "text"

    return _log_and_respond(request_id, start, use_case, response)


def _log_and_respond(
    request_id: str, start: float, use_case: str, response: func.HttpResponse
) -> func.HttpResponse:
    # Structured, content-free logging: never the food description, image
    # bytes, or raw gateway/provider response - only request metadata.
    latency_ms = round((time.perf_counter() - start) * 1000, 1)
    logger.info(
        "food_analysis request_id=%s use_case=%s status=%s latency_ms=%s",
        request_id, use_case, response.status_code, latency_ms,
    )
    response.headers[_REQUEST_ID_HEADER] = request_id
    return response


def _handle_text_analysis(req: func.HttpRequest, request_id: str) -> func.HttpResponse:
    try:
        body = req.get_json()
    except ValueError:
        return _error_response(400, "invalid_request", "Request body must be valid JSON.", request_id)

    try:
        public_request = FoodAnalysisPublicRequest.model_validate(body)
    except ValidationError:
        return _error_response(
            400,
            "invalid_request",
            "food_description is required and must be a 1-2000 character string.",
            request_id,
        )

    client = _make_gateway_client(request_id)
    try:
        gateway_response = client.analyze_food_text(public_request.food_description)
    except GatewayClientError as exc:
        logger.warning("gateway request failed request_id=%s code=%s", request_id, exc.code)
        return _error_response(exc.http_status, exc.code, exc.message, request_id)
    finally:
        client.close()

    return _respond_with_gateway_result(gateway_response, request_id)


def _handle_image_analysis(req: func.HttpRequest, request_id: str) -> func.HttpResponse:
    # Malformed multipart bodies raise inside werkzeug's parser (triggered
    # lazily by accessing .files/.form); never let that raw exception
    # escape as an unhandled 500.
    try:
        files = req.files
        form = req.form
    except Exception:
        return _error_response(
            400, "invalid_request", "Request body must be valid multipart/form-data.", request_id
        )

    image_file = files.get("image") if files else None
    if image_file is None:
        return _error_response(400, "image_required", "An 'image' file field is required.", request_id)

    # Bounded read: never load more than MAX_IMAGE_BYTES + 1 bytes into
    # memory here, regardless of how large the uploaded file claims/turns
    # out to be. This bounds *this* processing step only - by the time this
    # code runs, the Azure Functions host/worker has already received and
    # buffered the full HTTP request body (see backend/AGENTS.md for the
    # precise, non-overclaiming statement of what this check does and does
    # not guarantee).
    image_bytes = _read_bounded(image_file.stream, MAX_IMAGE_BYTES)
    if not image_bytes:
        return _error_response(400, "image_empty", "The uploaded image must not be empty.", request_id)
    if len(image_bytes) > MAX_IMAGE_BYTES:
        return _error_response(
            413, "image_too_large", f"The uploaded image exceeds the {MAX_IMAGE_BYTES}-byte limit.", request_id
        )

    mime_type = (image_file.mimetype or "").lower()
    if mime_type not in SUPPORTED_IMAGE_MIME_TYPES:
        return _error_response(
            415,
            "unsupported_media_type",
            f"Unsupported image type '{mime_type}'. Supported: {sorted(SUPPORTED_IMAGE_MIME_TYPES)}.",
            request_id,
        )

    if not image_content_matches_declared_type(image_bytes, mime_type):
        return _error_response(
            400,
            "image_content_invalid",
            "The uploaded file is not a valid, undamaged image of the declared type.",
            request_id,
        )

    raw_description = (form.get("food_description") if form else None) or None
    food_description = raw_description.strip() if raw_description else None
    if food_description and len(food_description) > MAX_FOOD_DESCRIPTION_LENGTH:
        return _error_response(
            400,
            "invalid_request",
            f"food_description must be at most {MAX_FOOD_DESCRIPTION_LENGTH} characters.",
            request_id,
        )

    client = _make_gateway_client(request_id)
    try:
        gateway_response = client.analyze_food_image(image_bytes, mime_type, food_description=food_description)
    except GatewayClientError as exc:
        logger.warning("gateway request failed request_id=%s code=%s", request_id, exc.code)
        return _error_response(exc.http_status, exc.code, exc.message, request_id)
    finally:
        client.close()
    # Release the (potentially several-MB) decoded image buffer as soon as
    # it is no longer needed, rather than keeping it referenced for the
    # rest of the request.
    del image_bytes

    return _respond_with_gateway_result(gateway_response, request_id)


def _make_gateway_client(request_id: str) -> GatewayClient:
    return GatewayClient(
        base_url=get_gateway_base_url(),
        timeout=get_gateway_timeout_seconds(),
        service_token=get_gateway_service_token(),
        request_id=request_id,
    )


def _respond_with_gateway_result(gateway_response: dict, request_id: str) -> func.HttpResponse:
    try:
        public_response = map_gateway_response_to_public(gateway_response)
    except (ValueError, TypeError):
        logger.warning("gateway returned an unexpected response shape request_id=%s", request_id)
        return _error_response(
            502, "gateway_invalid_response", "The AI gateway returned an unexpected response.", request_id
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


def _error_response(status_code: int, code: str, message: str, request_id: str) -> func.HttpResponse:
    return func.HttpResponse(
        json.dumps({"error": {"code": code, "message": message, "request_id": request_id}}),
        status_code=status_code,
        mimetype="application/json",
    )
