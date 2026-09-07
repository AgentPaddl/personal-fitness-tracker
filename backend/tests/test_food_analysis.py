import json

import azure.functions as func
import pytest

from api.food_analysis import food_analysis
from gateway_client import GatewayClient, GatewayClientError
from tests.image_fixtures import (
    make_tail_truncated_jpeg_bytes,
    make_tail_truncated_png_bytes,
    make_truncated_jpeg_bytes,
    make_valid_jpeg_bytes,
    make_valid_png_bytes,
)

_BOUNDARY = "test-boundary-123"
_VALID_JPEG_BYTES = make_valid_jpeg_bytes()
_VALID_PNG_BYTES = make_valid_png_bytes()


def _request(body: dict | bytes | None, headers: dict[str, str] | None = None) -> func.HttpRequest:
    raw_body = body if isinstance(body, (bytes, type(None))) else json.dumps(body).encode()
    return func.HttpRequest(
        method="POST",
        url="/api/food-analysis",
        body=raw_body or b"",
        headers={"Content-Type": "application/json", **(headers or {})},
    )


def _multipart_request(
    *,
    image_bytes: bytes | None = None,
    mime_type: str = "image/jpeg",
    food_description: str | None = None,
    include_image_field: bool = True,
    extra_form_fields: dict[str, str] | None = None,
) -> func.HttpRequest:
    if image_bytes is None:
        image_bytes = _VALID_JPEG_BYTES
    parts = []
    if include_image_field:
        parts.append(
            f'--{_BOUNDARY}\r\nContent-Disposition: form-data; name="image"; filename="photo.jpg"\r\n'
            f"Content-Type: {mime_type}\r\n\r\n".encode()
            + (image_bytes or b"")
            + b"\r\n"
        )
    if food_description is not None:
        parts.append(
            f'--{_BOUNDARY}\r\nContent-Disposition: form-data; name="food_description"\r\n\r\n'
            f"{food_description}\r\n".encode()
        )
    for name, value in (extra_form_fields or {}).items():
        parts.append(
            f'--{_BOUNDARY}\r\nContent-Disposition: form-data; name="{name}"\r\n\r\n'
            f"{value}\r\n".encode()
        )
    parts.append(f"--{_BOUNDARY}--\r\n".encode())
    raw_body = b"".join(parts)
    return func.HttpRequest(
        method="POST",
        url="/api/food-analysis",
        body=raw_body,
        headers={"Content-Type": f"multipart/form-data; boundary={_BOUNDARY}"},
    )


@pytest.fixture(autouse=True)
def _development_mode(monkeypatch):
    # This route has no production authentication yet; tests must opt in
    # explicitly, matching what is required in a real deployment.
    monkeypatch.setenv("APP_ENV", "development")


def test_food_analysis_rejects_missing_description():
    response = food_analysis(_request({}))

    assert response.status_code == 400
    assert json.loads(response.get_body())["error"]["code"] == "invalid_request"


def test_food_analysis_rejects_invalid_json():
    response = food_analysis(_request(b"not json"))

    assert response.status_code == 400
    assert json.loads(response.get_body())["error"]["code"] == "invalid_request"


def test_food_analysis_rejects_description_over_length_bound():
    response = food_analysis(_request({"food_description": "x" * 2001}))

    assert response.status_code == 400
    assert json.loads(response.get_body())["error"]["code"] == "invalid_request"


def test_food_analysis_denied_outside_development_mode_without_easy_auth(monkeypatch):
    monkeypatch.setenv("APP_ENV", "production")

    response = food_analysis(_request({"food_description": "an apple"}))

    assert response.status_code == 401
    assert json.loads(response.get_body())["error"]["code"] == "authentication_required"


def test_food_analysis_denied_with_spoofed_principal_header_when_easy_auth_disabled(monkeypatch):
    # EASY_AUTH_ENABLED is a server-side-only flag; a caller must never be
    # able to grant itself trust just by sending Easy Auth's identity
    # header while the flag itself is off (or not yet configured).
    monkeypatch.setenv("APP_ENV", "production")

    request = _request(
        {"food_description": "an apple"}, headers={"X-MS-CLIENT-PRINCIPAL-ID": "spoofed-user-id"}
    )
    response = food_analysis(request)

    assert response.status_code == 401
    assert json.loads(response.get_body())["error"]["code"] == "authentication_required"


def test_food_analysis_denied_outside_development_mode_with_easy_auth_enabled_but_no_header(monkeypatch):
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.setenv("EASY_AUTH_ENABLED", "true")

    response = food_analysis(_request({"food_description": "an apple"}))

    assert response.status_code == 401
    assert json.loads(response.get_body())["error"]["code"] == "authentication_required"


def test_food_analysis_allowed_outside_development_mode_with_easy_auth_principal_header(monkeypatch):
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.setenv("EASY_AUTH_ENABLED", "true")

    request = _request(
        {"food_description": "an apple"}, headers={"X-MS-CLIENT-PRINCIPAL-ID": "real-user-id"}
    )
    response = food_analysis(request)

    # An Easy-Auth-authenticated request should never be blocked purely by
    # APP_ENV=production; it will still fail downstream (gateway
    # unreachable in this unit test), but never with 401/403.
    assert response.status_code != 401
    assert response.status_code != 403


def test_food_analysis_success_maps_to_public_contract(monkeypatch):
    gateway_result = {
        "estimate": {
            "food_name": "apple",
            "calories": 95.0,
            "protein_grams": 0.5,
            "carbohydrate_grams": 25.0,
            "fat_grams": 0.3,
            "confidence": 0.8,
            "warnings": [],
        }
    }

    def fake_analyze(self, food_description):
        assert food_description == "an apple"
        return gateway_result

    monkeypatch.setattr(GatewayClient, "analyze_food_text", fake_analyze)
    monkeypatch.setattr(GatewayClient, "close", lambda self: None)

    response = food_analysis(_request({"food_description": "an apple"}))

    assert response.status_code == 200
    expected = gateway_result.copy()
    expected["estimate"] = {**gateway_result["estimate"], "assumptions": []}
    assert json.loads(response.get_body()) == expected


def _refinement_request(
    *,
    source_kind: str = "text",
    food_description: str | None = "Eine Schüssel Reis",
    iteration: object = 1,
) -> dict:
    payload = {
        "refinement": {
            "correction_text": "Ich habe nur die Hälfte gegessen.",
            "current_estimate": {
                "food_name": "Reisschüssel",
                "calories": 620,
                "protein_grams": 24,
                "carbohydrate_grams": 86,
                "fat_grams": 18,
                "confidence": 0.72,
                "warnings": ["Portion unsicher"],
                "assumptions": ["Reis wurde als gekocht interpretiert"],
            },
            "source_kind": source_kind,
            "iteration": iteration,
        }
    }
    if food_description is not None:
        payload["food_description"] = food_description
    return payload


def test_food_analysis_valid_text_refinement_sends_exact_gateway_payload(monkeypatch):
    captured = {}
    gateway_result = _gateway_result()

    def fake_refine(self, payload):
        captured["payload"] = payload
        return gateway_result

    monkeypatch.setattr(GatewayClient, "analyze_food_refinement", fake_refine)
    monkeypatch.setattr(GatewayClient, "close", lambda self: None)

    request_payload = _refinement_request()
    response = food_analysis(_request(request_payload))

    assert response.status_code == 200
    assert captured["payload"] == request_payload
    assert "image" not in captured["payload"]


@pytest.mark.parametrize(
    ("source_kind", "food_description"),
    [("image", None), ("text_and_image", "Eine Schüssel Reis")],
)
def test_food_analysis_accepts_non_text_refinement_sources_without_image_bytes(
    monkeypatch, source_kind, food_description
):
    captured = {}

    def fake_refine(self, payload):
        captured["payload"] = payload
        return _gateway_result()

    monkeypatch.setattr(GatewayClient, "analyze_food_refinement", fake_refine)
    monkeypatch.setattr(GatewayClient, "close", lambda self: None)

    response = food_analysis(
        _request(_refinement_request(source_kind=source_kind, food_description=food_description))
    )

    assert response.status_code == 200
    assert "image" not in captured["payload"]


@pytest.mark.parametrize("iteration", [1, 3])
def test_food_analysis_accepts_refinement_iteration_bounds(monkeypatch, iteration):
    monkeypatch.setattr(GatewayClient, "analyze_food_refinement", lambda self, payload: _gateway_result())
    monkeypatch.setattr(GatewayClient, "close", lambda self: None)

    response = food_analysis(_request(_refinement_request(iteration=iteration)))

    assert response.status_code == 200


@pytest.mark.parametrize("iteration", [0, 4, True, 1.5])
def test_food_analysis_rejects_invalid_refinement_iteration(iteration):
    response = food_analysis(_request(_refinement_request(iteration=iteration)))

    assert response.status_code == 400
    assert json.loads(response.get_body())["error"]["code"] == "invalid_request"


@pytest.mark.parametrize("correction_text", ["", "   ", "x" * 1001])
def test_food_analysis_rejects_invalid_correction_text(correction_text):
    payload = _refinement_request()
    payload["refinement"]["correction_text"] = correction_text

    response = food_analysis(_request(payload))

    assert response.status_code == 400


def test_food_analysis_accepts_maximum_correction_length(monkeypatch):
    payload = _refinement_request()
    payload["refinement"]["correction_text"] = "x" * 1000
    monkeypatch.setattr(GatewayClient, "analyze_food_refinement", lambda self, payload: _gateway_result())
    monkeypatch.setattr(GatewayClient, "close", lambda self: None)

    response = food_analysis(_request(payload))

    assert response.status_code == 200


@pytest.mark.parametrize(
    "missing_field", ["correction_text", "current_estimate", "source_kind", "iteration"]
)
def test_food_analysis_requires_every_refinement_field(missing_field):
    payload = _refinement_request()
    del payload["refinement"][missing_field]

    response = food_analysis(_request(payload))

    assert response.status_code == 400


@pytest.mark.parametrize(
    "missing_field",
    [
        "food_name",
        "calories",
        "protein_grams",
        "carbohydrate_grams",
        "fat_grams",
        "confidence",
        "warnings",
        "assumptions",
    ],
)
def test_food_analysis_requires_complete_refinement_estimate(missing_field):
    payload = _refinement_request()
    del payload["refinement"]["current_estimate"][missing_field]

    response = food_analysis(_request(payload))

    assert response.status_code == 400


@pytest.mark.parametrize("field", ["warnings", "assumptions"])
@pytest.mark.parametrize("value", [["x" * 501], ["note"] * 21, [""]])
def test_food_analysis_validates_refinement_notes_independently(field, value):
    payload = _refinement_request()
    payload["refinement"]["current_estimate"][field] = value

    response = food_analysis(_request(payload))

    assert response.status_code == 400


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("calories", -0.1),
        ("calories", 10_000.1),
        ("protein_grams", -0.1),
        ("protein_grams", 1_000.1),
        ("carbohydrate_grams", -0.1),
        ("carbohydrate_grams", 1_000.1),
        ("fat_grams", -0.1),
        ("fat_grams", 1_000.1),
        ("confidence", -0.1),
        ("confidence", 1.1),
    ],
)
def test_food_analysis_rejects_each_numeric_value_outside_bounds(field, value):
    payload = _refinement_request()
    payload["refinement"]["current_estimate"][field] = value

    response = food_analysis(_request(payload))

    assert response.status_code == 400


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("calories", 0),
        ("calories", 10_000),
        ("protein_grams", 0),
        ("protein_grams", 1_000),
        ("carbohydrate_grams", 0),
        ("carbohydrate_grams", 1_000),
        ("fat_grams", 0),
        ("fat_grams", 1_000),
        ("confidence", 0),
        ("confidence", 1),
    ],
)
def test_food_analysis_accepts_each_numeric_boundary(monkeypatch, field, value):
    payload = _refinement_request()
    payload["refinement"]["current_estimate"][field] = value
    monkeypatch.setattr(GatewayClient, "analyze_food_refinement", lambda self, payload: _gateway_result())
    monkeypatch.setattr(GatewayClient, "close", lambda self: None)

    response = food_analysis(_request(payload))

    assert response.status_code == 200


@pytest.mark.parametrize("field", ["warnings", "assumptions"])
def test_food_analysis_accepts_note_count_and_length_boundaries(monkeypatch, field):
    payload = _refinement_request()
    payload["refinement"]["current_estimate"][field] = ["x" * 500] * 20
    monkeypatch.setattr(GatewayClient, "analyze_food_refinement", lambda self, payload: _gateway_result())
    monkeypatch.setattr(GatewayClient, "close", lambda self: None)

    response = food_analysis(_request(payload))

    assert response.status_code == 200


def test_food_analysis_rejects_invalid_refinement_source_kind():
    response = food_analysis(_request(_refinement_request(source_kind="video")))

    assert response.status_code == 400


@pytest.mark.parametrize(
    ("source_kind", "food_description"),
    [("text", None), ("text_and_image", None), ("image", "Eine Schüssel Reis")],
)
def test_food_analysis_rejects_contradictory_refinement_source(source_kind, food_description):
    response = food_analysis(
        _request(_refinement_request(source_kind=source_kind, food_description=food_description))
    )

    assert response.status_code == 400


@pytest.mark.parametrize(
    "mutate",
    [
        lambda payload: payload.update({"unexpected": "value"}),
        lambda payload: payload["refinement"].update({"unexpected": "value"}),
        lambda payload: payload["refinement"]["current_estimate"].update({"internal": "value"}),
        lambda payload: payload.update({"image": {"data_base64": "not-allowed"}}),
    ],
)
def test_food_analysis_rejects_unknown_or_image_fields_in_json_refinement(mutate):
    payload = _refinement_request()
    mutate(payload)

    response = food_analysis(_request(payload))

    assert response.status_code == 400


def test_food_analysis_rejects_multipart_refinement_without_gateway_call(monkeypatch):
    def fail_if_called(*args, **kwargs):
        raise AssertionError("gateway must not be called")

    monkeypatch.setattr(GatewayClient, "analyze_food_image", fail_if_called)

    response = food_analysis(
        _multipart_request(extra_form_fields={"refinement": json.dumps(_refinement_request()["refinement"])})
    )

    assert response.status_code == 400
    assert json.loads(response.get_body())["error"]["code"] == "invalid_request"


def test_food_analysis_refinement_requires_authentication_before_gateway_call(monkeypatch):
    monkeypatch.setenv("APP_ENV", "production")

    def fail_if_called(*args, **kwargs):
        raise AssertionError("gateway must not be called")

    monkeypatch.setattr(GatewayClient, "analyze_food_refinement", fail_if_called)

    response = food_analysis(_request(_refinement_request()))

    assert response.status_code == 401


def test_food_analysis_refinement_forwards_request_id(monkeypatch):
    captured = {}

    def fake_refine(self, payload):
        captured["request_id"] = self._headers["X-Request-Id"]
        return _gateway_result()

    monkeypatch.setattr(GatewayClient, "analyze_food_refinement", fake_refine)
    monkeypatch.setattr(GatewayClient, "close", lambda self: None)

    response = food_analysis(
        _request(_refinement_request(), headers={"X-Request-Id": "refinement-request-123"})
    )

    assert response.status_code == 200
    assert response.headers["X-Request-Id"] == "refinement-request-123"
    assert captured["request_id"] == "refinement-request-123"


def test_food_analysis_refinement_normalizes_gateway_error(monkeypatch):
    def fake_refine(self, payload):
        raise GatewayClientError("gateway_timeout", 504)

    monkeypatch.setattr(GatewayClient, "analyze_food_refinement", fake_refine)
    monkeypatch.setattr(GatewayClient, "close", lambda self: None)

    response = food_analysis(_request(_refinement_request()))

    assert response.status_code == 504
    assert json.loads(response.get_body())["error"]["code"] == "gateway_timeout"


def test_food_analysis_drops_unknown_gateway_fields(monkeypatch):
    # The gateway response includes fields that must never reach the
    # client: provider/model identifiers, token usage, and debug data.
    gateway_result = {
        "estimate": {
            "food_name": "apple",
            "calories": 95.0,
            "protein_grams": 0.5,
            "carbohydrate_grams": 25.0,
            "fat_grams": 0.3,
            "confidence": 0.8,
            "warnings": ["warning"],
            "assumptions": ["assumption"],
            "internal_score": 99,
        },
        "provider": "fake",
        "model": "internal-test-model",
        "usage": {"prompt_tokens": 42, "completion_tokens": 7},
        "debug": {"trace_id": "abc-123"},
    }

    def fake_analyze(self, food_description):
        return gateway_result

    monkeypatch.setattr(GatewayClient, "analyze_food_text", fake_analyze)
    monkeypatch.setattr(GatewayClient, "close", lambda self: None)

    response = food_analysis(_request({"food_description": "an apple"}))
    body = json.loads(response.get_body())

    assert response.status_code == 200
    assert set(body.keys()) == {"estimate"}
    assert set(body["estimate"].keys()) == {
        "food_name",
        "calories",
        "protein_grams",
        "carbohydrate_grams",
        "fat_grams",
        "confidence",
        "warnings",
        "assumptions",
    }
    assert body["estimate"]["warnings"] == ["warning"]
    assert body["estimate"]["assumptions"] == ["assumption"]
    serialized = json.dumps(body).lower()
    for leaked_term in ("provider", "model", "usage", "debug", "trace_id", "token"):
        assert leaked_term not in serialized


def test_food_analysis_rejects_malformed_gateway_response(monkeypatch):
    def fake_analyze(self, food_description):
        return {"estimate": {"food_name": "apple"}}  # missing required fields

    monkeypatch.setattr(GatewayClient, "analyze_food_text", fake_analyze)
    monkeypatch.setattr(GatewayClient, "close", lambda self: None)

    response = food_analysis(_request({"food_description": "an apple"}))

    assert response.status_code == 502
    assert json.loads(response.get_body())["error"]["code"] == "gateway_invalid_response"


def test_food_analysis_normalizes_gateway_client_errors(monkeypatch):
    def fake_analyze(self, food_description):
        raise GatewayClientError("gateway_unreachable", 503, "The AI gateway is unreachable.")

    monkeypatch.setattr(GatewayClient, "analyze_food_text", fake_analyze)
    monkeypatch.setattr(GatewayClient, "close", lambda self: None)

    response = food_analysis(_request({"food_description": "an apple"}))

    assert response.status_code == 503
    body = json.loads(response.get_body())
    assert body["error"]["code"] == "gateway_unreachable"


def test_food_analysis_normalizes_gateway_timeout(monkeypatch):
    def fake_analyze(self, food_description):
        raise GatewayClientError("gateway_timeout", 504, "The AI gateway did not respond in time.")

    monkeypatch.setattr(GatewayClient, "analyze_food_text", fake_analyze)
    monkeypatch.setattr(GatewayClient, "close", lambda self: None)

    response = food_analysis(_request({"food_description": "an apple"}))

    assert response.status_code == 504
    assert json.loads(response.get_body())["error"]["code"] == "gateway_timeout"


def test_food_analysis_preserves_gateway_rate_limited_as_429(monkeypatch):
    def fake_analyze(self, food_description):
        raise GatewayClientError("gateway_rate_limited", 429)

    monkeypatch.setattr(GatewayClient, "analyze_food_text", fake_analyze)
    monkeypatch.setattr(GatewayClient, "close", lambda self: None)

    response = food_analysis(_request({"food_description": "an apple"}))

    assert response.status_code == 429
    assert json.loads(response.get_body())["error"]["code"] == "gateway_rate_limited"


def test_food_analysis_preserves_gateway_service_unavailable_as_503(monkeypatch):
    def fake_analyze(self, food_description):
        raise GatewayClientError("gateway_service_unavailable", 503)

    monkeypatch.setattr(GatewayClient, "analyze_food_text", fake_analyze)
    monkeypatch.setattr(GatewayClient, "close", lambda self: None)

    response = food_analysis(_request({"food_description": "an apple"}))

    assert response.status_code == 503
    assert json.loads(response.get_body())["error"]["code"] == "gateway_service_unavailable"


def test_food_analysis_normalizes_unknown_gateway_error_to_502(monkeypatch):
    def fake_analyze(self, food_description):
        raise GatewayClientError("gateway_upstream_error", 502)

    monkeypatch.setattr(GatewayClient, "analyze_food_text", fake_analyze)
    monkeypatch.setattr(GatewayClient, "close", lambda self: None)

    response = food_analysis(_request({"food_description": "an apple"}))

    assert response.status_code == 502
    assert json.loads(response.get_body())["error"]["code"] == "gateway_upstream_error"


def _gateway_result() -> dict:
    return {
        "estimate": {
            "food_name": "pasta with tomato sauce",
            "calories": 450.0,
            "protein_grams": 12.0,
            "carbohydrate_grams": 70.0,
            "fat_grams": 10.0,
            "confidence": 0.6,
            "warnings": ["Portion size estimated from image only."],
            "assumptions": [],
        }
    }


def test_food_analysis_image_only_success(monkeypatch):
    captured = {}

    def fake_analyze_image(self, image_bytes, mime_type, food_description=None):
        captured["image_bytes"] = image_bytes
        captured["mime_type"] = mime_type
        captured["food_description"] = food_description
        return _gateway_result()

    monkeypatch.setattr(GatewayClient, "analyze_food_image", fake_analyze_image)
    monkeypatch.setattr(GatewayClient, "close", lambda self: None)

    response = food_analysis(_multipart_request())

    assert response.status_code == 200
    assert json.loads(response.get_body()) == _gateway_result()
    assert captured["mime_type"] == "image/jpeg"
    assert captured["food_description"] is None
    assert captured["image_bytes"] == _VALID_JPEG_BYTES


def test_food_analysis_image_with_text(monkeypatch):
    captured = {}

    def fake_analyze_image(self, image_bytes, mime_type, food_description=None):
        captured["food_description"] = food_description
        return _gateway_result()

    monkeypatch.setattr(GatewayClient, "analyze_food_image", fake_analyze_image)
    monkeypatch.setattr(GatewayClient, "close", lambda self: None)

    response = food_analysis(_multipart_request(food_description="a bowl of pasta"))

    assert response.status_code == 200
    assert captured["food_description"] == "a bowl of pasta"


def test_food_analysis_rejects_missing_image_field():
    response = food_analysis(_multipart_request(include_image_field=False))

    assert response.status_code == 400
    assert json.loads(response.get_body())["error"]["code"] == "image_required"


def test_food_analysis_rejects_empty_image_payload():
    response = food_analysis(_multipart_request(image_bytes=b""))

    assert response.status_code == 400
    assert json.loads(response.get_body())["error"]["code"] == "image_empty"


def test_food_analysis_rejects_unsupported_image_mime_type():
    response = food_analysis(_multipart_request(mime_type="image/gif"))

    assert response.status_code == 415
    assert json.loads(response.get_body())["error"]["code"] == "unsupported_media_type"


def test_food_analysis_rejects_oversized_image():
    from schemas import MAX_IMAGE_BYTES

    response = food_analysis(_multipart_request(image_bytes=b"x" * (MAX_IMAGE_BYTES + 1)))

    assert response.status_code == 413
    assert json.loads(response.get_body())["error"]["code"] == "image_too_large"


def test_food_analysis_rejects_arbitrary_bytes_labeled_as_jpeg():
    response = food_analysis(_multipart_request(image_bytes=b"not an image, just plain bytes......."))

    assert response.status_code == 400
    assert json.loads(response.get_body())["error"]["code"] == "image_content_invalid"


def test_food_analysis_rejects_png_declared_as_jpeg():
    response = food_analysis(_multipart_request(image_bytes=_VALID_PNG_BYTES, mime_type="image/jpeg"))

    assert response.status_code == 400
    assert json.loads(response.get_body())["error"]["code"] == "image_content_invalid"


def test_food_analysis_rejects_jpeg_declared_as_png():
    response = food_analysis(_multipart_request(image_bytes=_VALID_JPEG_BYTES, mime_type="image/png"))

    assert response.status_code == 400
    assert json.loads(response.get_body())["error"]["code"] == "image_content_invalid"


def test_food_analysis_rejects_truncated_corrupt_jpeg():
    response = food_analysis(_multipart_request(image_bytes=make_truncated_jpeg_bytes()))

    assert response.status_code == 400
    assert json.loads(response.get_body())["error"]["code"] == "image_content_invalid"


def test_food_analysis_rejects_truncated_corrupt_png():
    response = food_analysis(
        _multipart_request(image_bytes=make_truncated_jpeg_bytes()[:5] + b"\x00" * 15, mime_type="image/png")
    )

    assert response.status_code == 400
    assert json.loads(response.get_body())["error"]["code"] == "image_content_invalid"


def test_food_analysis_rejects_jpeg_tail_truncated_by_tens_of_bytes():
    # Structurally valid headers (would pass Image.verify() alone), but
    # missing scan data/EOI near the end - only caught by a full decode.
    response = food_analysis(_multipart_request(image_bytes=make_tail_truncated_jpeg_bytes()))

    assert response.status_code == 400
    assert json.loads(response.get_body())["error"]["code"] == "image_content_invalid"


def test_food_analysis_rejects_png_tail_truncated_by_a_few_bytes():
    # Missing only a few trailing bytes of the IEND chunk; pixel data is
    # intact, so this is only caught by an explicit completeness check.
    response = food_analysis(
        _multipart_request(image_bytes=make_tail_truncated_png_bytes(), mime_type="image/png")
    )

    assert response.status_code == 400
    assert json.loads(response.get_body())["error"]["code"] == "image_content_invalid"


def test_food_analysis_valid_png_is_accepted(monkeypatch):
    def fake_analyze_image(self, image_bytes, mime_type, food_description=None):
        return {
            "estimate": {
                "food_name": "pasta",
                "calories": 400.0,
                "protein_grams": 10.0,
                "carbohydrate_grams": 60.0,
                "fat_grams": 8.0,
                "confidence": 0.5,
                "warnings": [],
            }
        }

    monkeypatch.setattr(GatewayClient, "analyze_food_image", fake_analyze_image)
    monkeypatch.setattr(GatewayClient, "close", lambda self: None)

    response = food_analysis(_multipart_request(image_bytes=_VALID_PNG_BYTES, mime_type="image/png"))

    assert response.status_code == 200


def test_read_bounded_never_reads_more_than_the_limit_plus_one():
    from api.food_analysis import _read_bounded

    class _SpyStream:
        def __init__(self, data: bytes):
            self._data = data
            self.last_requested_size: int | None = None

        def read(self, size: int | None = None) -> bytes:
            self.last_requested_size = size
            assert size is not None, "must never call read() unbounded"
            return self._data[:size]

    huge_data = b"x" * (10 * 1024 * 1024)
    stream = _SpyStream(huge_data)

    result = _read_bounded(stream, max_bytes=3 * 1024 * 1024)

    assert stream.last_requested_size == 3 * 1024 * 1024 + 1
    assert len(result) == 3 * 1024 * 1024 + 1


def test_food_analysis_rejects_malformed_multipart_body():
    request = func.HttpRequest(
        method="POST",
        url="/api/food-analysis",
        body=b"this is not a valid multipart body",
        headers={"Content-Type": f"multipart/form-data; boundary={_BOUNDARY}"},
    )

    response = food_analysis(request)

    assert response.status_code == 400
    assert json.loads(response.get_body())["error"]["code"] in ("invalid_request", "image_required")


def test_food_analysis_image_maps_gateway_error(monkeypatch):
    def fake_analyze_image(self, image_bytes, mime_type, food_description=None):
        raise GatewayClientError("gateway_unreachable", 503, "The AI gateway is unreachable.")

    monkeypatch.setattr(GatewayClient, "analyze_food_image", fake_analyze_image)
    monkeypatch.setattr(GatewayClient, "close", lambda self: None)

    response = food_analysis(_multipart_request())

    assert response.status_code == 503
    assert json.loads(response.get_body())["error"]["code"] == "gateway_unreachable"


def test_food_analysis_image_denied_outside_development_mode_without_easy_auth(monkeypatch):
    monkeypatch.setenv("APP_ENV", "production")

    response = food_analysis(_multipart_request())

    assert response.status_code == 401
    assert json.loads(response.get_body())["error"]["code"] == "authentication_required"
