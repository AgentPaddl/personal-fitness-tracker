from fastapi.testclient import TestClient

from app.dependencies import get_food_analysis_use_case
from app.errors import ProviderOutputInvalidError, ProviderTimeoutError, ProviderUnavailableError
from app.main import create_app
from tests.image_fixtures import make_truncated_jpeg_bytes, make_valid_jpeg_bytes, make_valid_png_bytes

import base64

_TINY_IMAGE_BASE64 = base64.b64encode(make_valid_jpeg_bytes()).decode("ascii")
_TINY_PNG_BASE64 = base64.b64encode(make_valid_png_bytes()).decode("ascii")


def test_food_analysis_success_returns_bounded_estimate(client):
    response = client.post("/v1/food-analysis", json={"food_description": "grilled chicken breast"})

    assert response.status_code == 200
    body = response.json()
    estimate = body["estimate"]

    assert "grilled chicken breast" in estimate["food_name"]
    assert 0 <= estimate["calories"] <= 10_000
    assert 0 <= estimate["protein_grams"] <= 1_000
    assert 0 <= estimate["carbohydrate_grams"] <= 1_000
    assert 0 <= estimate["fat_grams"] <= 1_000
    assert 0 <= estimate["confidence"] <= 1
    assert isinstance(estimate["warnings"], list)


def test_food_analysis_is_deterministic(client):
    payload = {"food_description": "two scrambled eggs"}
    first = client.post("/v1/food-analysis", json=payload).json()
    second = client.post("/v1/food-analysis", json=payload).json()

    assert first == second


def test_food_analysis_rejects_blank_description(client):
    response = client.post("/v1/food-analysis", json={"food_description": "   "})

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "request_invalid"


def test_food_analysis_rejects_malformed_body(client):
    response = client.post("/v1/food-analysis", json={"unexpected": 1})

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "request_invalid"


def test_food_analysis_response_never_exposes_provider_details(client):
    response = client.post("/v1/food-analysis", json={"food_description": "apple"})
    body = response.json()

    serialized = str(body).lower()
    for leaked_term in ("fake", "provider", "copilot", "model", "purpose"):
        assert leaked_term not in serialized


def _override_use_case(use_case) -> TestClient:
    app = create_app()
    app.dependency_overrides[get_food_analysis_use_case] = lambda: use_case
    return TestClient(app, raise_server_exceptions=False)


class _StubUseCase:
    def __init__(self, raise_exc: Exception):
        self._raise_exc = raise_exc

    async def execute(self, request):
        raise self._raise_exc


def test_food_analysis_maps_provider_timeout_to_504(dev_env):
    client = _override_use_case(_StubUseCase(ProviderTimeoutError()))

    response = client.post("/v1/food-analysis", json={"food_description": "apple"})

    assert response.status_code == 504
    assert response.json()["error"]["code"] == "provider_timeout"


def test_food_analysis_maps_provider_unavailable_to_502(dev_env):
    client = _override_use_case(_StubUseCase(ProviderUnavailableError()))

    response = client.post("/v1/food-analysis", json={"food_description": "apple"})

    assert response.status_code == 502
    assert response.json()["error"]["code"] == "provider_unavailable"


def test_food_analysis_maps_invalid_provider_output_to_502(dev_env):
    client = _override_use_case(_StubUseCase(ProviderOutputInvalidError()))

    response = client.post("/v1/food-analysis", json={"food_description": "apple"})

    assert response.status_code == 502
    assert response.json()["error"]["code"] == "provider_output_invalid"


def test_food_analysis_normalizes_unexpected_exceptions_without_leaking_detail(dev_env):
    client = _override_use_case(_StubUseCase(RuntimeError("raw internal sdk detail")))

    response = client.post("/v1/food-analysis", json={"food_description": "apple"})

    assert response.status_code == 500
    body = response.json()
    assert body["error"]["code"] == "internal_error"
    assert "raw internal sdk detail" not in str(body)


def test_food_analysis_accepts_image_only(client):
    response = client.post(
        "/v1/food-analysis",
        json={"image": {"media_type": "image/jpeg", "data_base64": _TINY_IMAGE_BASE64}},
    )

    assert response.status_code == 200
    estimate = response.json()["estimate"]
    assert 0 <= estimate["calories"] <= 10_000


def test_food_analysis_accepts_text_and_image(client):
    response = client.post(
        "/v1/food-analysis",
        json={
            "food_description": "a bowl of pasta",
            "image": {"media_type": "image/jpeg", "data_base64": _TINY_IMAGE_BASE64},
        },
    )

    assert response.status_code == 200


def test_food_analysis_rejects_neither_text_nor_image(client):
    response = client.post("/v1/food-analysis", json={})

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "request_invalid"


def test_food_analysis_rejects_unsupported_image_media_type(client):
    response = client.post(
        "/v1/food-analysis",
        json={"image": {"media_type": "image/gif", "data_base64": _TINY_IMAGE_BASE64}},
    )

    assert response.status_code == 422


def test_food_analysis_rejects_non_base64_image_payload(client):
    response = client.post(
        "/v1/food-analysis",
        json={"image": {"media_type": "image/jpeg", "data_base64": "not-base64!!!"}},
    )

    assert response.status_code == 422


def test_food_analysis_rejects_oversized_image_payload(client):
    oversized = base64.b64encode(b"x" * (3 * 1024 * 1024 + 1)).decode("ascii")
    response = client.post(
        "/v1/food-analysis",
        json={"image": {"media_type": "image/jpeg", "data_base64": oversized}},
    )

    assert response.status_code == 422


def test_food_analysis_rejects_oversized_encoded_string_before_decoding(client):
    # Invalid base64 alphabet, but the length check must reject this before
    # any attempt to decode it (which would otherwise raise a different,
    # decode-specific error rather than the length-bound one).
    from app.schemas.food_analysis import MAX_IMAGE_BYTES
    import math

    max_encoded_length = 4 * math.ceil(MAX_IMAGE_BYTES / 3)
    oversized_garbage = "!" * (max_encoded_length + 1)

    response = client.post(
        "/v1/food-analysis",
        json={"image": {"media_type": "image/jpeg", "data_base64": oversized_garbage}},
    )

    assert response.status_code == 422


def test_food_analysis_rejects_arbitrary_bytes_labeled_as_jpeg(client):
    garbage_base64 = base64.b64encode(b"not an image, just random bytes......").decode("ascii")

    response = client.post(
        "/v1/food-analysis",
        json={"image": {"media_type": "image/jpeg", "data_base64": garbage_base64}},
    )

    assert response.status_code == 422


def test_food_analysis_rejects_png_declared_as_jpeg(client):
    response = client.post(
        "/v1/food-analysis",
        json={"image": {"media_type": "image/jpeg", "data_base64": _TINY_PNG_BASE64}},
    )

    assert response.status_code == 422


def test_food_analysis_rejects_jpeg_declared_as_png(client):
    response = client.post(
        "/v1/food-analysis",
        json={"image": {"media_type": "image/png", "data_base64": _TINY_IMAGE_BASE64}},
    )

    assert response.status_code == 422


def test_food_analysis_rejects_truncated_corrupt_jpeg(client):
    truncated_base64 = base64.b64encode(make_truncated_jpeg_bytes()).decode("ascii")

    response = client.post(
        "/v1/food-analysis",
        json={"image": {"media_type": "image/jpeg", "data_base64": truncated_base64}},
    )

    assert response.status_code == 422


def test_food_analysis_valid_png_is_accepted(client):
    response = client.post(
        "/v1/food-analysis",
        json={"image": {"media_type": "image/png", "data_base64": _TINY_PNG_BASE64}},
    )

    assert response.status_code == 200
