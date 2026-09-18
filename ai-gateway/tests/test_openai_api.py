from copy import deepcopy
import asyncio
import base64
import json
import logging
from decimal import Decimal

import httpx2

import pytest

from app.errors import (
    ModelUnavailableError, ProviderAuthenticationError, ProviderOutputInvalidError,
    ProviderRateLimitedError, ProviderTimeoutError, ProviderUnavailableError, ServiceNotReadyError,
)
from app.providers.base import Attachment, GenerationMessage, StructuredGenerationRequest
from app.providers.openai_api import AzureOpenAIProvider
from app.providers.pricing import GPT_54_MINI, PriceTable, resolve_profiles
from app.providers.strict_schema import to_strict_schema
from app.schemas.food_analysis import FoodAnalysisEstimate, FoodAnalysisRequest
from app.use_cases.food_analysis import FoodAnalysisUseCase
from tests.image_fixtures import make_valid_jpeg_bytes, make_valid_png_bytes


@pytest.fixture(autouse=True)
def _local_adapter_environment(monkeypatch):
    monkeypatch.setenv("APP_ENV", "test")


def test_entra_requires_independent_dispatch_guard():
    async def token():
        pytest.fail("Credential must not be requested")

    with pytest.raises(ValueError):
        AzureOpenAIProvider(endpoint="https://benchmark.openai.azure.com", model_routes={"text": "mini"},
                            token_provider=token)


@pytest.mark.parametrize("environment", ["production", "development"])
def test_entra_cannot_dispatch_by_renaming_environment(monkeypatch, environment):
    monkeypatch.setenv("APP_ENV", environment)
    monkeypatch.setenv("AI_PILOT_ENABLED", "true")
    calls = []

    async def token():
        calls.append("token")
        return "not-a-real-token"

    def denied():
        raise ServiceNotReadyError()

    async def run():
        provider = AzureOpenAIProvider(
            endpoint="https://benchmark.openai.azure.com", model_routes={"purpose-test": "mini"},
            token_provider=token, dispatch_guard=denied,
            prices=PriceTable(version=GPT_54_MINI.price_version, currency="USD", deployments={"mini": GPT_54_MINI.price}),
            profile_bindings={"mini": GPT_54_MINI.identifier},
            transport=httpx2.MockTransport(lambda request: calls.append("dispatch")),
        )
        try:
            with pytest.raises(ServiceNotReadyError):
                await provider.generate(_request())
        finally:
            await provider.aclose()

    asyncio.run(run())
    assert calls == []


@pytest.mark.parametrize("app_env", ["production", None, "staging"])
@pytest.mark.parametrize("profile", [False, True])
def test_direct_generation_enforces_local_only_guard(monkeypatch, app_env, profile):
    calls = []

    def handler(request):
        calls.append(request)
        return httpx2.Response(200, json=_completion())

    async def run():
        provider = (_profile_provider if profile else _provider)(handler)
        if app_env is None:
            monkeypatch.delenv("APP_ENV", raising=False)
        else:
            monkeypatch.setenv("APP_ENV", app_env)
        try:
            with pytest.raises(ServiceNotReadyError):
                await provider.generate(_request())
        finally:
            await provider.aclose()

    asyncio.run(run())
    assert calls == []


def test_analysis_route_with_existing_adapter_cannot_bypass_production_guard(monkeypatch):
    from fastapi.testclient import TestClient
    from app.dependencies import get_food_analysis_use_case
    from app.main import create_app
    from app.security import require_authenticated_caller

    provider = _provider(lambda request: pytest.fail("Production SDK dispatch"))
    gateway_app = create_app()
    gateway_app.dependency_overrides[require_authenticated_caller] = lambda: None
    gateway_app.dependency_overrides[get_food_analysis_use_case] = lambda: FoodAnalysisUseCase(provider, 1, "purpose-test")
    monkeypatch.setenv("APP_ENV", "production")
    try:
        with TestClient(gateway_app, raise_server_exceptions=False) as client:
            response = client.post("/v1/food-analysis", json={"food_description": "synthetic guard input"})
        assert response.status_code == 503
        assert response.json()["error"]["code"] == "service_not_ready"
        assert "synthetic guard input" not in response.text
        assert "azure" not in response.text
    finally:
        asyncio.run(provider.aclose())


def test_strict_schema_preserves_original_business_constraints():
    original = FoodAnalysisEstimate.model_json_schema()
    before = deepcopy(original)

    strict = to_strict_schema(original)

    assert original == before
    assert strict["additionalProperties"] is False
    assert strict["required"] == list(original["properties"])
    assert "maximum" not in strict["properties"]["calories"]
    assert "maxItems" not in strict["properties"]["warnings"]
    assert "maxLength" not in strict["properties"]["warnings"]["items"]
    assert original["properties"]["calories"]["maximum"] == 10_000


def test_strict_schema_translates_nested_references_and_nullable_fields():
    original = {
        "type": "object",
        "properties": {"records": {"type": "array", "items": {"$ref": "#/$defs/Record"}}},
        "$defs": {"Record": {
            "type": "object",
            "properties": {"value": {"anyOf": [{"type": "number", "minimum": 0}, {"type": "null"}], "default": None}},
        }},
    }

    strict = to_strict_schema(original)

    record = strict["$defs"]["Record"]
    assert record["additionalProperties"] is False
    assert record["required"] == ["value"]
    assert "default" not in record["properties"]["value"]
    assert record["properties"]["value"]["anyOf"][0] == {"type": "number"}


@pytest.mark.parametrize("schema", [
    {"type": "array", "items": {"type": "string"}},
    {"type": "object", "allOf": []},
    {"type": "object", "properties": {"value": {"$ref": "https://example.invalid/schema"}}},
    {"type": "object", "properties": {"value": {"$ref": "#/$defs/Missing"}}},
    {"type": "object", "additionalProperties": {"type": "string"}},
])
def test_strict_schema_fails_closed_for_unsupported_shapes(schema):
    with pytest.raises(ValueError):
        to_strict_schema(schema)


def _completion(data=None, **overrides):
    return {
        "id": "completion-test", "created": 1, "object": "chat.completion",
        "model": "model-snapshot-1",
        "choices": [{"index": 0, "finish_reason": "stop", "message": {
            "role": "assistant", "content": json.dumps(data if data is not None else {"value": 2}),
        }}],
        "usage": {"prompt_tokens": 100, "completion_tokens": 20, "total_tokens": 120,
                  "prompt_tokens_details": {"cached_tokens": 40},
                  "completion_tokens_details": {"reasoning_tokens": 5}},
        **overrides,
    }


def _prices():
    return PriceTable.model_validate({
        "version": "test-prices-v1", "currency": "USD", "deployments": {
            "deployment-test": {"model": "model-snapshot-1", "input_per_million": "0.44",
                                "cached_input_per_million": "0.11", "output_per_million": "1.76"},
        },
    })


def _request(**overrides):
    return StructuredGenerationRequest(**{
        "model_purpose": "purpose-test", "messages": [GenerationMessage("user", "synthetic input")],
        "timeout_seconds": 1.0, "output_json_schema": {
            "type": "object", "properties": {"value": {"type": "integer", "minimum": 0, "maximum": 10}},
        }, **overrides,
    })


def _profile_prices():
    return PriceTable(version=GPT_54_MINI.price_version, currency="USD",
                      deployments={"deployment-test": GPT_54_MINI.price})


def test_reviewed_profile_reserve_and_price_binding():
    assert GPT_54_MINI.reserve_usd(2000) == Decimal("0.2343")
    assert GPT_54_MINI.reserve_usd(1000) == Decimal("0.22935")
    assert GPT_54_MINI.reserve_usd(2000) * 18 == Decimal("4.2174")
    profiles = resolve_profiles({"deployment-test": GPT_54_MINI.identifier},
                                {"purpose-test": "deployment-test"}, _profile_prices(), 2000)
    assert profiles == {"deployment-test": GPT_54_MINI}


def _profile_provider(handler, **overrides):
    return _provider(handler, **{
        "prices": _profile_prices(), "profile_bindings": {"deployment-test": GPT_54_MINI.identifier},
        **overrides,
    })


def _profile_completion(data=None, **overrides):
    return _completion(data, **{"model": GPT_54_MINI.price.model, "service_tier": "default", **overrides})


@pytest.mark.parametrize("image", [False, True])
def test_profile_sdk_exact_request_and_output_cap(image):
    calls = []

    def handler(request):
        calls.append(request)
        return httpx2.Response(200, json=_profile_completion())

    async def run():
        provider = _profile_provider(handler)
        attachments = [Attachment("image", "image/png", base64.b64encode(make_valid_png_bytes()).decode())] if image else []
        generation = _request(max_output_tokens=9000, attachments=attachments)
        try:
            assert await provider.check_ready() is False
            return await provider.generate(generation), generation
        finally:
            await provider.aclose()

    (result, generation) = asyncio.run(run())
    assert len(calls) == 1
    assert str(calls[0].url) == "https://example.openai.azure.com/openai/v1/chat/completions"
    messages = [{"role": "user", "content": "synthetic input"}]
    if image:
        messages.append({"role": "user", "content": [{"type": "image_url", "image_url": {
            "url": f"data:image/png;base64,{generation.attachments[0].data}", "detail": "high",
        }}]})
    assert json.loads(calls[0].content) == {
        "model": "deployment-test", "messages": messages, "store": False, "stream": False, "n": 1,
        "max_completion_tokens": 2000, "reasoning_effort": "none", "service_tier": "default",
        "response_format": {"type": "json_schema", "json_schema": {
            "name": "structured_result", "strict": True, "schema": to_strict_schema(generation.output_json_schema),
        }},
    }
    assert result.metadata.estimated_cost_usd == Decimal("0.0001518")
    assert result.metadata.profile_id == GPT_54_MINI.identifier


@pytest.mark.parametrize("overrides", [
    {"model": "gpt-5.4-mini"}, {"model": "gpt-5.4-mini-2026-03-18"}, {"model": None},
    {"service_tier": "priority"}, {"service_tier": None},
])
def test_profile_rejects_unknown_model_or_tier(overrides):
    calls = []

    def handler(request):
        calls.append(request)
        return httpx2.Response(200, json=_profile_completion(**overrides))

    async def run():
        provider = _profile_provider(handler)
        try:
            with pytest.raises(ModelUnavailableError) as caught:
                await provider.generate(_request())
            assert caught.value.metadata.estimated_cost_usd is None
            assert caught.value.metadata.status == "profile_mismatch"
        finally:
            await provider.aclose()

    asyncio.run(run())
    assert len(calls) == 1


@pytest.mark.parametrize("change", ["missing", "version", "deployment", "model", "input", "cache", "output", "cap"])
def test_reviewed_profile_rejects_configuration_drift(change):
    bindings = {"deployment-test": GPT_54_MINI.identifier}
    prices = _profile_prices().model_dump(mode="json")
    if change == "missing":
        bindings = {}
    elif change == "version":
        bindings["deployment-test"] = "gpt-5.4-mini-2026-03-18-dz-v1"
    elif change == "deployment":
        bindings = {"other-deployment": GPT_54_MINI.identifier}
    elif change == "model":
        prices["deployments"]["deployment-test"]["model"] = "gpt-5.4-mini"
    elif change in {"input", "cache", "output"}:
        field = {"input": "input_per_million", "cache": "cached_input_per_million", "output": "output_per_million"}[change]
        prices["deployments"]["deployment-test"][field] = "0.01"
    with pytest.raises(ValueError):
        resolve_profiles(bindings, {"purpose-test": "deployment-test"}, PriceTable.model_validate(prices),
                         2001 if change == "cap" else 2000)


def _provider(handler, **overrides):
    return AzureOpenAIProvider(**{
        "endpoint": "https://example.openai.azure.com", "api_key": "not-a-real-key",
        "model_routes": {"purpose-test": "deployment-test"}, "prices": _prices(),
        "transport": httpx2.MockTransport(handler), **overrides,
    })


def test_sdk_text_request_is_strict_stateless_single_call_with_metadata():
    calls = []

    def handler(request):
        calls.append(request)
        return httpx2.Response(200, json=_completion(), headers={"x-request-id": "request-test"})

    async def run():
        provider = _provider(handler)
        try:
            assert provider._client.max_retries == 0
            return await provider.generate(_request(max_output_tokens=123))
        finally:
            await provider.aclose()
            assert provider._client.is_closed()

    result = asyncio.run(run())
    assert len(calls) == 1
    payload = json.loads(calls[0].content)
    assert str(calls[0].url) == "https://example.openai.azure.com/openai/v1/chat/completions"
    assert payload["model"] == "deployment-test"
    assert payload["store"] is False
    assert payload["max_completion_tokens"] == 123
    assert payload["response_format"]["json_schema"]["strict"] is True
    assert "tools" not in payload
    assert result.data == {"value": 2}
    assert result.metadata.requested_deployment == "deployment-test"
    assert result.metadata.returned_model == "model-snapshot-1"
    assert result.metadata.provider_request_id == "request-test"
    assert result.metadata.duration_ms >= 0
    assert result.metadata.usage.reasoning_tokens == 5
    assert result.metadata.estimated_cost_usd == Decimal("0.000066")


@pytest.mark.parametrize("profile", [False, True])
def test_sdk_output_validated_against_original_bounds_with_usage_on_error(profile):
    async def run():
        completion = (_profile_completion if profile else _completion)({"value": 11})
        provider = (_profile_provider if profile else _provider)(lambda request: httpx2.Response(200, json=completion))
        try:
            with pytest.raises(ProviderOutputInvalidError) as caught:
                await provider.generate(_request())
            assert caught.value.metadata.usage_known
            assert caught.value.metadata.estimated_cost_usd == Decimal("0.0001518" if profile else "0.000066")
        finally:
            await provider.aclose()

    asyncio.run(run())


@pytest.mark.parametrize("data", [
    {}, {"value": 1, "extra": True}, {"value": "2"}, {"value": True},
    {"value": -1}, {"value": 11}, [], None,
])
def test_result_shape_and_business_validation_reject_without_repair(data):
    completion = _completion()
    completion["choices"][0]["message"]["content"] = json.dumps(data)
    _assert_failure(completion, ProviderOutputInvalidError, "invalid_output")


def _assert_failure(completion, error_type, status):
    calls = []

    def handler(request):
        calls.append(request)
        return httpx2.Response(200, json=completion, headers={"x-request-id": "request-test"})

    async def run():
        provider = _provider(handler)
        try:
            with pytest.raises(error_type) as caught:
                await provider.generate(_request())
            assert caught.value.metadata.status == status
            assert caught.value.metadata.provider_request_id == "request-test"
            assert caught.value.metadata.usage_known
        finally:
            await provider.aclose()

    asyncio.run(run())
    assert len(calls) == 1


@pytest.mark.parametrize(("changes", "status"), [
    ({"message": {"role": "assistant", "refusal": "sensitive refusal", "content": None}}, "refused"),
    ({"finish_reason": "content_filter"}, "refused"),
    ({"finish_reason": "length"}, "truncated"),
    ({"finish_reason": "tool_calls"}, "invalid_output"),
    ({"message": {"role": "assistant", "content": "```json\n{}\n```"}}, "invalid_output"),
    ({"message": {"role": "assistant", "content": '{"value":1,"value":2}'}}, "invalid_output"),
    ({"message": {"role": "assistant", "content": '{"value":NaN}'}}, "invalid_output"),
    ({"message": {"role": "assistant", "content": '{"value":1e999}'}}, "invalid_output"),
])
def test_refusal_truncation_and_invalid_json(changes, status):
    completion = _completion()
    completion["choices"][0].update(changes)
    _assert_failure(completion, ProviderOutputInvalidError, status)


@pytest.mark.parametrize("choices", [[], [_completion()["choices"][0]] * 2])
def test_requires_exactly_one_response_choice(choices):
    _assert_failure(_completion(choices=choices), ProviderOutputInvalidError, "invalid_output")


@pytest.mark.parametrize("profile", [False, True])
@pytest.mark.parametrize(("http_status", "error_type", "status"), [
    (401, ProviderAuthenticationError, "authentication_failed"),
    (403, ProviderAuthenticationError, "authentication_failed"),
    (404, ModelUnavailableError, "model_unavailable"),
    (408, ProviderTimeoutError, "timeout"),
    (429, ProviderRateLimitedError, "rate_limited"),
    (504, ProviderTimeoutError, "timeout"),
    (500, ProviderUnavailableError, "unavailable"),
    (503, ProviderUnavailableError, "unavailable"),
    (400, ProviderUnavailableError, "unavailable"),
    (307, ProviderUnavailableError, "unavailable"),
])
def test_http_errors_never_retry_redirect_or_leak_content(http_status, error_type, status, caplog, profile):
    calls = []
    secret_marker = "sensitive-provider-error-marker"
    caplog.set_level(logging.DEBUG)

    def handler(request):
        calls.append(request)
        return httpx2.Response(http_status, json={"error": {"message": secret_marker}}, headers={
            "x-request-id": "request-test", "retry-after": "0", "x-should-retry": "true",
            "location": "https://elsewhere.invalid/",
        })

    async def run():
        provider = (_profile_provider if profile else _provider)(handler)
        try:
            with pytest.raises(error_type) as caught:
                await provider.generate(_request())
            assert caught.value.metadata.status == status
            assert caught.value.metadata.estimated_cost_usd is None
            assert caught.value.metadata.usage is None
            assert secret_marker not in str(caught.value)
        finally:
            await provider.aclose()

    asyncio.run(run())
    assert len(calls) == 1
    assert secret_marker not in caplog.text
    assert "synthetic input" not in caplog.text
    assert "not-a-real-key" not in caplog.text


@pytest.mark.parametrize("mode", ["transport_timeout", "connection", "deadline"])
def test_transport_failures_and_deadline_are_single_attempt(mode):
    calls = []

    async def handler(request):
        calls.append(request)
        if mode == "transport_timeout":
            raise httpx2.ReadTimeout("sensitive detail", request=request)
        if mode == "connection":
            raise httpx2.ConnectError("sensitive detail", request=request)
        await asyncio.Event().wait()

    async def run():
        provider = _provider(handler)
        try:
            expected = ProviderUnavailableError if mode == "connection" else ProviderTimeoutError
            with pytest.raises(expected) as caught:
                await provider.generate(_request(timeout_seconds=0.02))
            assert caught.value.metadata.usage is None
            assert caught.value.metadata.estimated_cost_usd is None
            assert "sensitive detail" not in str(caught.value)
        finally:
            await provider.aclose()

    asyncio.run(run())
    assert len(calls) == 1


@pytest.mark.parametrize("changes", [
    {"usage": None}, {"usage": {}},
    {"usage": {"prompt_tokens": 1, "completion_tokens": -1}},
    {"usage": {"prompt_tokens": 1, "completion_tokens": 2, "total_tokens": 99}},
    {"usage": {"prompt_tokens": 1, "completion_tokens": 2}},
    {"usage": {"prompt_tokens": 1, "completion_tokens": 2, "prompt_tokens_details": {"cached_tokens": 9}}},
    {"model": "different-model"}, {"model": None},
])
def test_unknown_or_inconsistent_usage_and_price_never_mean_zero_cost(changes):
    async def run():
        provider = _provider(lambda request: httpx2.Response(200, json=_completion(**changes)))
        try:
            result = await provider.generate(_request())
            assert result.data == {"value": 2}
            assert result.metadata.estimated_cost_usd is None
        finally:
            await provider.aclose()

    asyncio.run(run())


def test_missing_price_table_and_unmapped_deployment_are_unknown():
    async def run():
        for prices in (None, PriceTable(version="empty-v1", currency="USD", deployments={})):
            provider = _provider(lambda request: httpx2.Response(200, json=_completion()), prices=prices)
            try:
                result = await provider.generate(_request())
                assert result.metadata.usage_known
                assert result.metadata.estimated_cost_usd is None
            finally:
                await provider.aclose()

    asyncio.run(run())


def _food_data():
    return {
        "food_name": "synthetic-meal-marker", "calories": 200, "protein_grams": 10,
        "carbohydrate_grams": 20, "fat_grams": 5, "confidence": 0.6,
        "warnings": [], "assumptions": [],
    }


@pytest.mark.parametrize("mode", ["text", "jpeg", "png", "refinement"])
def test_food_use_case_through_sdk_for_text_images_and_refinement(mode, caplog):
    calls = []
    caplog.set_level(logging.DEBUG)
    encoded = base64.b64encode(make_valid_png_bytes() if mode == "png" else make_valid_jpeg_bytes()).decode("ascii")
    payload = {"food_description": "synthetic-description-marker"}
    if mode in {"jpeg", "png"}:
        payload["image"] = {"media_type": f"image/{mode}", "data_base64": encoded}
    elif mode == "refinement":
        payload = {"refinement": {
            "correction_text": "synthetic-correction-marker", "current_estimate": _food_data(),
            "source_kind": "image", "iteration": 2,
        }}

    def handler(request):
        calls.append(json.loads(request.content))
        return httpx2.Response(200, json=_completion(_food_data()))

    async def run():
        provider = _provider(handler, model_routes={"text-purpose": "text-deployment", "image-purpose": "image-deployment"})
        try:
            use_case = FoodAnalysisUseCase(provider, 1, "text-purpose", "image-purpose", max_output_tokens=321)
            return await use_case.execute(FoodAnalysisRequest.model_validate(payload))
        finally:
            await provider.aclose()

    result = asyncio.run(run())
    assert result.model_dump() == {"estimate": _food_data()}
    assert len(calls) == 1
    assert calls[0]["max_completion_tokens"] == 321
    assert calls[0]["model"] == ("image-deployment" if mode in {"jpeg", "png"} else "text-deployment")
    serialized = json.dumps(calls[0]["messages"])
    if mode in {"jpeg", "png"}:
        assert f"data:image/{mode};base64,{encoded}" in serialized
    else:
        assert "image_url" not in serialized
    if mode == "refinement":
        assert "synthetic-correction-marker" in serialized
        assert "No image is attached" in serialized
    for marker in (encoded, "synthetic-description-marker", "synthetic-correction-marker", "synthetic-meal-marker"):
        assert marker not in caplog.text


@pytest.mark.parametrize("overrides", [
    {"model_purpose": "unknown-purpose"}, {"max_output_tokens": 0},
    {"attachments": [Attachment("file", "application/pdf", "abc")]},
    {"attachments": [Attachment("image", "image/jpeg", "not-base64")]},
    {"output_json_schema": {"type": "object", "allOf": []}},
])
def test_invalid_requests_never_dispatch_or_fallback(overrides):
    async def run():
        provider = _provider(lambda request: pytest.fail("unexpected provider dispatch"))
        try:
            expected = ModelUnavailableError if "model_purpose" in overrides else ProviderOutputInvalidError
            with pytest.raises(expected):
                await provider.generate(_request(**overrides))
            assert await provider.check_ready() is False
        finally:
            await provider.aclose()

    asyncio.run(run())


def test_configured_output_limit_cannot_be_raised_by_request():
    calls = []

    def handler(request):
        calls.append(json.loads(request.content))
        return httpx2.Response(200, json=_completion())

    async def run():
        provider = _provider(handler, max_output_tokens=99)
        try:
            await provider.generate(_request(max_output_tokens=2000))
        finally:
            await provider.aclose()

    asyncio.run(run())
    assert calls[0]["max_completion_tokens"] == 99


def test_prompt_filter_error_is_a_refusal_without_usage():
    calls = []

    def handler(request):
        calls.append(request)
        return httpx2.Response(400, json={"error": {"code": "content_filter", "message": "sensitive"}})

    async def run():
        provider = _provider(handler)
        try:
            with pytest.raises(ProviderOutputInvalidError) as caught:
                await provider.generate(_request())
            assert caught.value.metadata.status == "refused"
            assert caught.value.metadata.usage is None
            assert caught.value.metadata.estimated_cost_usd is None
        finally:
            await provider.aclose()

    asyncio.run(run())
    assert len(calls) == 1


@pytest.mark.parametrize("change", ["missing", "total", "cache", "reasoning", "negative_reasoning", "boolean_reasoning"])
def test_profile_unknown_usage_is_not_free(change):
    response = _profile_completion()
    if change == "missing":
        response["usage"] = None
    elif change == "total":
        response["usage"]["total_tokens"] = 999
    elif change == "cache":
        response["usage"]["prompt_tokens_details"] = None
    else:
        response["usage"]["completion_tokens_details"]["reasoning_tokens"] = {
            "reasoning": 21, "negative_reasoning": -1, "boolean_reasoning": True,
        }[change]

    async def run():
        provider = _profile_provider(lambda request: httpx2.Response(200, json=response))
        try:
            result = await provider.generate(_request())
            assert result.metadata.estimated_cost_usd is None
        finally:
            await provider.aclose()

    asyncio.run(run())


@pytest.mark.parametrize("change", ["schema", "truncated", "effective_output", "input"])
def test_profile_invalid_response_never_repairs(change):
    response = _profile_completion({} if change == "schema" else {"value": 2})
    if change == "truncated":
        response["choices"][0]["finish_reason"] = "length"
    elif change == "effective_output":
        response["usage"].update(completion_tokens=1001, total_tokens=1101)
    elif change == "input":
        response["usage"].update(prompt_tokens=272001, total_tokens=272021)
    calls = []

    def handler(request):
        calls.append(request)
        return httpx2.Response(200, json=response)

    async def run():
        provider = _profile_provider(handler)
        try:
            with pytest.raises(ProviderOutputInvalidError) as caught:
                await provider.generate(_request(max_output_tokens=1000))
            assert caught.value.metadata.usage_known
            assert caught.value.metadata.status == {
                "schema": "invalid_output", "truncated": "truncated",
                "effective_output": "bound_violation", "input": "bound_violation",
            }[change]
        finally:
            await provider.aclose()

    asyncio.run(run())
    assert len(calls) == 1