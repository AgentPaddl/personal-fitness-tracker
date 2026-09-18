from fastapi.testclient import TestClient

from app.dependencies import get_food_analysis_use_case
from app.errors import ProviderOutputInvalidError, ProviderTimeoutError, ProviderUnavailableError
from app.main import create_app
from tests.image_fixtures import (
    make_tail_truncated_jpeg_bytes,
    make_tail_truncated_png_bytes,
    make_truncated_jpeg_bytes,
    make_valid_jpeg_bytes,
    make_valid_png_bytes,
)

import base64

import pytest

_TINY_IMAGE_BASE64 = base64.b64encode(make_valid_jpeg_bytes()).decode("ascii")
_TINY_PNG_BASE64 = base64.b64encode(make_valid_png_bytes()).decode("ascii")

_CURRENT_ESTIMATE = {
    "food_name": "rice bowl",
    "calories": 620.0,
    "protein_grams": 24.0,
    "carbohydrate_grams": 86.0,
    "fat_grams": 18.0,
    "confidence": 0.72,
    "warnings": ["Portion size is uncertain."],
    "assumptions": ["Rice weight was interpreted as cooked."],
}


def _refinement_payload(
    *, source_kind: str = "text", iteration: int = 1, food_description: str | None = "rice bowl"
) -> dict:
    payload = {
        "refinement": {
            "correction_text": "I ate only half of it.",
            "current_estimate": dict(_CURRENT_ESTIMATE),
            "source_kind": source_kind,
            "iteration": iteration,
        }
    }
    if food_description is not None:
        payload["food_description"] = food_description
    return payload


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
    assert isinstance(estimate["assumptions"], list)


@pytest.mark.parametrize("mutation", ["none", "scaled", "independent", "maximum_notes", "duplicate", "duplicate_reference",
                                      "invented_source", "incomplete", "empty", "missing", "no_contract",
                                      "zero_basis", "negative", "nan", "boolean", "overflow"])
def test_declared_text_nutrition_is_calculated_once(mutation):
    import asyncio
    from copy import deepcopy
    from app.benchmark import load_cases
    from app.providers.base import GenerationMetadata, StructuredGenerationResult, TokenUsage
    from app.providers.strict_schema import to_strict_schema
    from app.schemas.food_analysis import FoodAnalysisRequest
    from app.use_cases.food_analysis import FoodAnalysisUseCase

    case = next(case for case, _ in load_cases()[1] if case["id"] == "T2")
    payload = deepcopy(case["payload"])
    components = [
        {"quantity_source": "200 g Joghurt", "nutrition_source": "Je 100 g Joghurt: 60 kcal, Eiweiss 4 g, Kohlenhydrate 5 g, Fett 2 g.",
         "quantity_grams": "200", "basis_grams": "100", "calories": "60", "protein_grams": "4", "carbohydrate_grams": "5", "fat_grams": "2"},
        {"quantity_source": "40 g Haferflocken", "nutrition_source": "Je 100 g Haferflocken: 380 kcal, Eiweiss 13 g, Kohlenhydrate 60 g, Fett 7 g.",
         "quantity_grams": "40", "basis_grams": "100", "calories": "380", "protein_grams": "13", "carbohydrate_grams": "60", "fat_grams": "7"},
    ]
    data = {**_CURRENT_ESTIMATE, "calories": 276, "protein_grams": 20.2,
            "declared_nutrition": {"complete": True, "components": components}}
    if mutation == "scaled":
        payload["food_description"] = payload["food_description"].replace("200 g", "125.5 g").replace("40 g", "20 g")
        components[0].update(quantity_source="125.5 g Joghurt", quantity_grams="125.5")
        components[1].update(quantity_source="20 g Haferflocken", quantity_grams="20")
    elif mutation == "maximum_notes":
        data["assumptions"] = [f"Assumption {index}" for index in range(19)]
        data["warnings"] = [f"Warning {index}" for index in range(20)]
    elif mutation == "duplicate":
        components.append(deepcopy(components[0]))
    elif mutation == "independent":
        payload["food_description"] = "15.5 g Quark. Je 25 g Quark: 60 kcal, Eiweiss 1.5 g, Kohlenhydrate 5.1 g, Fett 0.35 g."
        components[:] = [{
            "quantity_source": "15.5 g Quark", "nutrition_source": "Je 25 g Quark: 60 kcal, Eiweiss 1.5 g, Kohlenhydrate 5.1 g, Fett 0.35 g.",
            "quantity_grams": "15.5", "basis_grams": "25", "calories": "60", "protein_grams": "1.5",
            "carbohydrate_grams": "5.1", "fat_grams": "0.35",
        }]
    elif mutation == "duplicate_reference":
        components[1]["nutrition_source"] = components[0]["nutrition_source"]
    elif mutation == "invented_source":
        components[0]["nutrition_source"] = "not supplied"
    elif mutation == "incomplete":
        data["declared_nutrition"] = {"complete": False, "components": []}
    elif mutation == "empty":
        components.clear()
    elif mutation == "no_contract":
        del data["declared_nutrition"]
    elif mutation == "missing":
        del components[0]["protein_grams"]
    elif mutation in {"zero_basis", "negative", "nan", "boolean", "overflow"}:
        field, value = {"zero_basis": ("basis_grams", "0"), "negative": ("calories", "-1"),
                        "nan": ("calories", "NaN"), "boolean": ("calories", True),
                        "overflow": ("quantity_grams", "10000")}[mutation]
        components[0][field] = value
        if mutation == "overflow":
            components[0]["calories"] = "10000"

    metadata = GenerationMetadata("synthetic", "test", "test", None, 1, "success", TokenUsage(10, 20))

    class Provider:
        calls = 0

        async def generate(self, request):
            self.calls += 1
            self.request = request
            return StructuredGenerationResult(data=data, metadata=metadata)

    provider = Provider()
    use_case = FoodAnalysisUseCase(provider, 1, "food_text_v1")
    if mutation in {"none", "scaled", "independent", "maximum_notes"}:
        response = asyncio.run(use_case.execute(FoodAnalysisRequest.model_validate(payload)))
        expected = {
            "none": case["expected"],
            "maximum_notes": case["expected"],
            "scaled": {"calories": 151.3, "protein_grams": 7.62, "carbohydrate_grams": 18.275, "fat_grams": 3.91},
            "independent": {"calories": 37.2, "protein_grams": 0.93, "carbohydrate_grams": 3.162, "fat_grams": 0.217},
        }[mutation]
        assert {field: getattr(response.estimate, field) for field in expected} == expected
        assert "declared_nutrition" not in response.model_dump()["estimate"]
        assert response.estimate.assumptions[1:] == data["assumptions"]
        assert response.estimate.warnings == data["warnings"]
    else:
        with pytest.raises(ProviderOutputInvalidError) as caught:
            asyncio.run(use_case.execute(FoodAnalysisRequest.model_validate(payload)))
        assert caught.value.metadata is metadata
    assert provider.calls == 1
    strict = to_strict_schema(provider.request.output_json_schema)
    assert "declared_nutrition" in strict["required"]
    assert provider.request.output_json_schema["properties"]["assumptions"]["maxItems"] == 19
    assert not provider.request.attachments


@pytest.mark.parametrize("field, maximum", [
    ("calories", 10000), ("protein_grams", 1000),
    ("carbohydrate_grams", 1000), ("fat_grams", 1000),
])
@pytest.mark.parametrize("increment", ["0", "0.000000000000001"])
def test_declared_totals_are_bounded_before_float_rounding(field, maximum, increment):
    from app.schemas.food_analysis import TextNutritionExtraction
    from app.use_cases.food_analysis import FoodAnalysisUseCase

    components = []
    for name, amount in [("first", str(maximum)), ("second", increment)]:
        components.append({
            "quantity_source": f"1 g {name}", "nutrition_source": f"{name}: {amount} {field} per 1 g",
            "quantity_grams": "1", "basis_grams": "1", "calories": "0", "protein_grams": "0",
            "carbohydrate_grams": "0", "fat_grams": "0", field: amount,
        })
    description = "; ".join(component[key] for component in components for key in ("quantity_source", "nutrition_source"))
    extraction = TextNutritionExtraction.model_validate({
        **_CURRENT_ESTIMATE, "declared_nutrition": {"complete": True, "components": components},
    })
    if increment == "0":
        assert getattr(FoodAnalysisUseCase._declared_estimate(extraction, description), field) == maximum
    else:
        with pytest.raises(ValueError):
            FoodAnalysisUseCase._declared_estimate(extraction, description)


def test_food_analysis_is_deterministic(client):
    payload = {"food_description": "two scrambled eggs"}
    first = client.post("/v1/food-analysis", json=payload).json()
    second = client.post("/v1/food-analysis", json=payload).json()

    assert first == second


def test_food_analysis_accepts_text_refinement_and_returns_distinct_deterministic_result(client):
    payload = _refinement_payload()

    first = client.post("/v1/food-analysis", json=payload)
    second = client.post("/v1/food-analysis", json=payload)
    initial = client.post("/v1/food-analysis", json={"food_description": "rice bowl"})

    assert first.status_code == 200
    assert first.json() == second.json()
    assert first.json() != initial.json()


def test_food_analysis_accepts_refinement_of_image_source_without_image_bytes(client):
    response = client.post(
        "/v1/food-analysis",
        json=_refinement_payload(source_kind="image", food_description=None),
    )

    assert response.status_code == 200


def test_food_analysis_accepts_text_and_image_sourced_refinement_without_image_bytes(client):
    response = client.post(
        "/v1/food-analysis",
        json=_refinement_payload(source_kind="text_and_image"),
    )

    assert response.status_code == 200


@pytest.mark.parametrize("iteration", [1, 3])
def test_food_analysis_accepts_refinement_iteration_bounds(client, iteration):
    response = client.post("/v1/food-analysis", json=_refinement_payload(iteration=iteration))

    assert response.status_code == 200


@pytest.mark.parametrize("iteration", [0, 4, True])
def test_food_analysis_rejects_refinement_iteration_outside_bounds(client, iteration):
    response = client.post("/v1/food-analysis", json=_refinement_payload(iteration=iteration))

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "request_invalid"


@pytest.mark.parametrize("correction_text", ["", "   ", "x" * 1001])
def test_food_analysis_rejects_invalid_refinement_correction_text(client, correction_text):
    payload = _refinement_payload()
    payload["refinement"]["correction_text"] = correction_text

    response = client.post("/v1/food-analysis", json=payload)

    assert response.status_code == 422


def test_food_analysis_rejects_missing_refinement_current_estimate(client):
    payload = _refinement_payload()
    del payload["refinement"]["current_estimate"]

    response = client.post("/v1/food-analysis", json=payload)

    assert response.status_code == 422


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
def test_food_analysis_requires_complete_refinement_current_estimate(client, missing_field):
    payload = _refinement_payload()
    del payload["refinement"]["current_estimate"][missing_field]

    response = client.post("/v1/food-analysis", json=payload)

    assert response.status_code == 422


def test_food_analysis_rejects_invalid_refinement_current_estimate(client):
    payload = _refinement_payload()
    payload["refinement"]["current_estimate"]["calories"] = -1

    response = client.post("/v1/food-analysis", json=payload)

    assert response.status_code == 422


def test_food_analysis_rejects_invalid_refinement_source_kind(client):
    payload = _refinement_payload(source_kind="video")

    response = client.post("/v1/food-analysis", json=payload)

    assert response.status_code == 422


@pytest.mark.parametrize(
    ("source_kind", "food_description", "include_image"),
    [
        ("text", None, False),
        ("text_and_image", None, False),
        ("image", "rice bowl", False),
        ("text", "rice bowl", True),
    ],
)
def test_food_analysis_rejects_contradictory_refinement_modes(
    client, source_kind, food_description, include_image
):
    payload = _refinement_payload(source_kind=source_kind, food_description=food_description)
    if include_image:
        payload["image"] = {"media_type": "image/jpeg", "data_base64": _TINY_IMAGE_BASE64}

    response = client.post("/v1/food-analysis", json=payload)

    assert response.status_code == 422


@pytest.mark.parametrize("field", ["warnings", "assumptions"])
def test_food_analysis_validates_warning_and_assumption_item_lengths_separately(client, field):
    payload = _refinement_payload()
    payload["refinement"]["current_estimate"][field] = ["x" * 501]

    response = client.post("/v1/food-analysis", json=payload)

    assert response.status_code == 422


@pytest.mark.parametrize("field", ["warnings", "assumptions"])
def test_food_analysis_validates_warning_and_assumption_counts_separately(client, field):
    payload = _refinement_payload()
    payload["refinement"]["current_estimate"][field] = ["bounded note"] * 21

    response = client.post("/v1/food-analysis", json=payload)

    assert response.status_code == 422


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


def test_food_analysis_rejects_jpeg_tail_truncated_by_tens_of_bytes(client):
    # Structurally valid headers (would pass Image.verify() alone), but
    # missing scan data/EOI near the end - only caught by a full decode.
    truncated_base64 = base64.b64encode(make_tail_truncated_jpeg_bytes()).decode("ascii")

    response = client.post(
        "/v1/food-analysis",
        json={"image": {"media_type": "image/jpeg", "data_base64": truncated_base64}},
    )

    assert response.status_code == 422


def test_food_analysis_rejects_png_tail_truncated_by_a_few_bytes(client):
    # Missing only a few trailing bytes of the IEND chunk; pixel data is
    # intact, so this is only caught by an explicit completeness check.
    truncated_base64 = base64.b64encode(make_tail_truncated_png_bytes()).decode("ascii")

    response = client.post(
        "/v1/food-analysis",
        json={"image": {"media_type": "image/png", "data_base64": truncated_base64}},
    )

    assert response.status_code == 422


def test_food_analysis_valid_png_is_accepted(client):
    response = client.post(
        "/v1/food-analysis",
        json={"image": {"media_type": "image/png", "data_base64": _TINY_PNG_BASE64}},
    )

    assert response.status_code == 200
