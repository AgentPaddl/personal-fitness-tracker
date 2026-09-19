"""Offline CAS model, not evidence of Azure Table isolation or deployment security."""

import asyncio
import base64
import json
import logging
from pathlib import Path
from copy import deepcopy
from dataclasses import replace
from decimal import Decimal
import time
from uuid import UUID

import pytest

from app.pilot import Conflict, Coordinator, PilotError, PilotPolicy, digest
from app.providers.base import GenerationMessage, StructuredGenerationRequest, StructuredGenerationResult
from app.providers.pricing import GPT_54_MINI, PriceTable

IDENTITY = ("00000000-0000-4000-8000-000000000001", "00000000-0000-4000-8000-000000000002")
OTHER = (IDENTITY[0], "00000000-0000-4000-8000-000000000003")
SECRET = b"synthetic-test-secret-not-for-use-000"


class MemoryCAS:
    def __init__(self):
        self.rows = {}
        self.lock = asyncio.Lock()

    async def read(self, key):
        await asyncio.sleep(0)
        return deepcopy(self.rows.get(key, (None, None)))

    async def commit(self, changes):
        async with self.lock:
            if any(self.rows.get(key, (None, None))[1] != etag for key, _, etag in changes):
                raise Conflict()
            for key, data, etag in changes:
                self.rows[key] = (deepcopy(data), str(int(etag or "0") + 1))


def operation(now=None, sequence=1):
    return str(UUID(int=(int((now or time.time()) * 1000) << 80) | (7 << 76) | (2 << 62) | sequence))


def coordinator(store=None, **changes):
    limits = {"minute": 10, "day": 20, "month": 40, "concurrent": 2,
              "daily_usd": "10", "monthly_usd": "20"}
    policy = PilotPolicy.model_validate({
        "version": "synthetic-v1", "person": limits, "total": limits,
        "operation_max_age_seconds": 3600, "retention_seconds": 2678400,
        "max_text_schema_bytes": 16000, "max_image_bytes": 10000, "max_image_dimension": 512,
        "max_output_tokens": 100, "deployment_verified_until": 2000000000, **changes,
    })
    prices = PriceTable.model_validate({"version": "synthetic", "currency": "USD", "deployments": {
        "deployment": {"model": "gpt-4.1-mini-2025-04-14", "input_per_million": "1",
                       "cached_input_per_million": "0.1", "output_per_million": "2"}}})
    result = Coordinator(store or MemoryCAS(), policy, SECRET, {IDENTITY, OTHER}, prices,
                         {"text": "deployment", "image": "deployment"})
    if not result.store.rows:
        result.store.rows["ledger"] = (result.initial_ledger(), "1")
    return result


def request():
    return StructuredGenerationRequest("text", [GenerationMessage("user", "synthetic")],
                                       {"type": "object"}, 1, max_output_tokens=100)


def profile_coordinator(store=None, *, max_output_tokens=2000, **policy_changes):
    policy = coordinator(max_output_tokens=2000, **policy_changes).policy
    prices = PriceTable(version=GPT_54_MINI.price_version, currency="USD",
                        deployments={"deployment-test": GPT_54_MINI.price})
    control = Coordinator(store or MemoryCAS(), policy, SECRET, {IDENTITY, OTHER}, prices,
                          {"purpose-test": "deployment-test"},
                          profile_bindings={"deployment-test": GPT_54_MINI.identifier},
                          max_output_tokens=max_output_tokens)
    if not control.store.rows:
        control.store.rows["ledger"] = (control.initial_ledger(), "1")
    return control


@pytest.mark.parametrize("attempts, reserve", [(10, "2.343"), (14, "3.2802")])
def test_acceptance_lifetime_limit_survives_calendar_rollover_and_restart(attempts, reserve):
    from tests.test_openai_api import _request

    async def run():
        start = 1790812790
        acceptance = {"max_attempts": attempts, "max_reserved_usd": reserve,
                      "payload_sha256": ["a" * 64], "expires_at": start + 30 * 86400}
        control = profile_coordinator(acceptance=acceptance)
        generation = _request(max_output_tokens=2000)
        for sequence in range(attempts):
            instant = start + sequence * 86400
            control.clock = lambda: instant
            reservation = await control.reserve(IDENTITY, operation(instant, sequence), "synthetic",
                                                control.bound(generation), control.admission(generation))
            await control.mark_dispatched(reservation)
            await control.settle(reservation, "failed", None)
        restarted = profile_coordinator(store=control.store, acceptance=acceptance)
        restarted.clock = lambda: start + (attempts + 1) * 86400
        with pytest.raises(PilotError, match="usage limit"):
            await restarted.reserve(IDENTITY, operation(restarted.clock()), "synthetic",
                                    restarted.bound(generation), restarted.admission(generation))
        ledger = control.store.rows["ledger"][0]
        assert ledger["acceptance"] == {"attempts": attempts, "reserved": attempts * 234300000}
        assert ledger["benchmark"] is None

    asyncio.run(run())


def test_provider_429_is_one_terminal_response_but_unknown_cost_keeps_person_slot(monkeypatch):
    import httpx2
    from app.errors import ProviderRateLimitedError
    from tests.test_openai_api import _profile_provider, _request

    monkeypatch.setenv("APP_ENV", "test")
    monkeypatch.setenv("AI_PILOT_ENABLED", "true")
    calls = []

    def handler(request):
        calls.append(request)
        return httpx2.Response(429, headers={"retry-after": "60", "x-request-id": "synthetic-request"},
                               json={"error": {"code": "429", "message": "synthetic throttling"}})

    async def run():
        acceptance = {"max_attempts": 10, "max_reserved_usd": "2.343",
                      "payload_sha256": ["a" * 64], "expires_at": int(time.time()) + 3600}
        control = profile_coordinator(acceptance=acceptance)
        control.policy = control.policy.model_copy(update={
            "person": control.policy.person.model_copy(update={"concurrent": 1})})
        provider = _profile_provider(handler)
        try:
            with pytest.raises(ProviderRateLimitedError) as captured:
                await control.generate(provider, _request(max_output_tokens=2000), IDENTITY, operation(), "synthetic")
            assert captured.value.metadata.status == "rate_limited"
            assert captured.value.metadata.provider_request_id == "synthetic-request"
            assert not captured.value.metadata.usage_known
            assert captured.value.retry_after_seconds is None
            ledger = control.store.rows["ledger"][0]
            key = next(iter(ledger["active"]))
            record = control.store.rows[key][0]
            assert record["settled"] and record["state"] == "unknown"
            assert record["charged"] == record["reserved"] == 234300000
            assert ledger["acceptance"] == {"attempts": 1, "reserved": 234300000}
            assert not ledger["blocked"]
            with pytest.raises(PilotError, match="usage limit"):
                await control.generate(provider, _request(max_output_tokens=2000), IDENTITY,
                                       operation(sequence=2), "different")
            assert control.store.rows["ledger"][0] == ledger
        finally:
            await provider.aclose()

    asyncio.run(run())
    assert len(calls) == 1


def test_acceptance_is_opt_in_and_cannot_expand_setup_authorization():
    assert "acceptance" not in coordinator().policy.model_dump(mode="json")
    acceptance = {"max_attempts": 10, "max_reserved_usd": "2.343",
                  "payload_sha256": ["a" * 64], "expires_at": 1900000000}
    for changes in ({"max_attempts": 17}, {"max_reserved_usd": "3.748800001"}, {"payload_sha256": []},
                    {"expires_at": 2000000001}):
        with pytest.raises(ValueError):
            profile_coordinator(acceptance={**acceptance, **changes})


@pytest.mark.parametrize("outcome", ["success", "missing_usage", "refused", "reasoning_exhausted", "model", "tier"])
def test_profile_pilot_reservation_settlement_and_failures(monkeypatch, outcome):
    import httpx2
    from app.errors import ModelUnavailableError, ProviderOutputInvalidError
    from tests.test_openai_api import _profile_provider, _profile_completion, _request

    monkeypatch.setenv("APP_ENV", "test")
    monkeypatch.setenv("AI_PILOT_ENABLED", "true")
    calls = []
    response = _profile_completion()
    if outcome == "missing_usage":
        response["usage"] = None
    elif outcome == "refused":
        response["choices"][0]["message"]["refusal"] = "synthetic refusal"
    elif outcome == "reasoning_exhausted":
        response["choices"][0].update(finish_reason="length", message={"role": "assistant", "content": ""})
        response["usage"].update(completion_tokens=2000, total_tokens=2100,
                                 completion_tokens_details={"reasoning_tokens": 2000})
    elif outcome == "model":
        response["model"] = "gpt-5.4-mini"
    elif outcome == "tier":
        response["service_tier"] = "priority"

    async def run():
        control = profile_coordinator()
        generation, identifier = _request(max_output_tokens=2000), operation()

        def handler(request):
            calls.append(request)
            return httpx2.Response(200, json=response)

        provider = _profile_provider(handler)
        try:
            assert control.bound(generation) == 234300000
            if outcome in {"refused", "reasoning_exhausted", "model", "tier"}:
                error_type = ModelUnavailableError if outcome in {"model", "tier"} else ProviderOutputInvalidError
                with pytest.raises(error_type):
                    await control.generate(provider, generation, IDENTITY, identifier, "synthetic")
            else:
                await control.generate(provider, generation, IDENTITY, identifier, "synthetic")
            row = next(data for key, (data, _) in control.store.rows.items() if key.startswith("op-"))
            assert row["reserved"] == 234300000
            assert row["admission"] == {
                "deployment": "deployment-test", "model": GPT_54_MINI.price.model,
                "profile_id": GPT_54_MINI.identifier, "service_tier": "default",
                "price_version": GPT_54_MINI.price_version, "max_input_tokens": 272000, "max_output_tokens": 2000,
            }
            unknown = outcome in {"missing_usage", "model", "tier"}
            assert row["usage_known"] is not unknown
            expected = 234300000 if unknown else 9952800 if outcome == "reasoning_exhausted" else 151800
            assert row["charged"] == expected
            assert control.store.rows["ledger"][0]["blocked"] is (outcome in {"model", "tier"})
            with pytest.raises(PilotError):
                await control.generate(provider, generation, IDENTITY, identifier, "synthetic")
        finally:
            await provider.aclose()

    asyncio.run(run())
    assert len(calls) == 1


@pytest.mark.parametrize("truncated", [False, True])
def test_extraction_contract_keeps_output_cap_full_input_reserve_and_single_dispatch(monkeypatch, truncated):
    import httpx2
    from dataclasses import asdict
    from app.errors import ProviderOutputInvalidError
    from app.pilot import canonical
    from app.schemas.food_analysis import FoodAnalysisRequest
    from app.use_cases.food_analysis import FoodAnalysisUseCase
    from tests.test_openai_api import _profile_provider, _profile_completion, _food_data

    monkeypatch.setenv("APP_ENV", "test")
    monkeypatch.setenv("AI_PILOT_ENABLED", "true")
    calls = []
    generation_requests = []
    quantity_source = "I ate 25 g food"
    nutrition_source = "Per serving of 50 g: 80 kcal, protein 2 g, carbohydrate 3 g, fat 1 g"
    data = {**_food_data(), "declared_nutrition": {"complete": True, "components": [{
        "quantity_source": quantity_source, "nutrition_source": nutrition_source,
        "quantity_grams": "25", "basis_grams": "50", "calories": "80", "protein_grams": "2",
        "carbohydrate_grams": "3", "fat_grams": "1",
    }]}}

    def handler(request):
        calls.append(json.loads(request.content))
        response = _profile_completion(data)
        if truncated:
            response["choices"][0]["finish_reason"] = "length"
        return httpx2.Response(200, json=response)

    async def run():
        control = profile_coordinator(max_text_schema_bytes=65536)
        identifier = operation()
        provider = _profile_provider(handler)
        use_case = FoodAnalysisUseCase(provider, 1, "purpose-test", max_output_tokens=2000)

        async def dispatch(generation):
            generation_requests.append(generation)
            return await control.generate(provider, generation, IDENTITY, identifier, "synthetic")

        monkeypatch.setattr(use_case, "_generate_with_timeout", dispatch)
        payload = FoodAnalysisRequest(food_description=f"{quantity_source}. {nutrition_source}.")
        try:
            if truncated:
                with pytest.raises(ProviderOutputInvalidError) as caught:
                    await use_case.execute(payload)
                assert caught.value.metadata.status == "truncated"
                assert caught.value.metadata.usage_known
            else:
                result = await use_case.execute(payload)
                assert result.estimate.calories == 40
                assert result.estimate.protein_grams == 1
                assert "declared_nutrition" not in result.model_dump()["estimate"]
            generation = generation_requests[0]
            serialized = canonical([[asdict(message) for message in generation.messages], generation.output_json_schema])
            assert len(serialized) < 65536
            assert control.bound(generation) == 234300000
            assert control.admission(generation)["max_input_tokens"] == 272000
            assert control.admission(generation)["max_output_tokens"] == 2000
            row = next(data for key, (data, _) in control.store.rows.items() if key.startswith("op-"))
            assert row["reserved"] == 234300000
            assert row["usage_known"]
            with pytest.raises(PilotError):
                await use_case.execute(payload)
            assert len(calls) == 1
            assert calls[0]["max_completion_tokens"] == 2000
            assert "declared_nutrition" in calls[0]["response_format"]["json_schema"]["schema"]["required"]
        finally:
            await provider.aclose()

    asyncio.run(run())


@pytest.mark.parametrize("change", ["deployment", "cap", "price_version"])
def test_profile_dispatch_permit_rejects_adapter_drift(monkeypatch, change):
    from app.errors import ProviderOutputInvalidError
    from tests.test_openai_api import _profile_provider, _profile_prices, _request

    monkeypatch.setenv("APP_ENV", "test")
    monkeypatch.setenv("AI_PILOT_ENABLED", "true")
    calls = []

    def handler(request):
        calls.append(request)
        raise AssertionError("Mismatched dispatch")

    async def run():
        control = profile_coordinator()
        options = {}
        if change == "deployment":
            options = {"model_routes": {"purpose-test": "other"}, "profile_bindings": {"other": GPT_54_MINI.identifier},
                       "prices": PriceTable(version=GPT_54_MINI.price_version, currency="USD",
                                            deployments={"other": GPT_54_MINI.price})}
        elif change == "cap":
            options = {"max_output_tokens": 1000}
        provider = _profile_provider(handler, **options)
        if change == "price_version":
            provider._prices = _profile_prices().model_copy(update={"version": "unreviewed"})
        try:
            with pytest.raises(ProviderOutputInvalidError if change == "price_version" else PilotError):
                await control.generate(provider, _request(max_output_tokens=2000), IDENTITY, operation(), "synthetic")
        finally:
            await provider.aclose()

    asyncio.run(run())
    assert calls == []


@pytest.mark.parametrize("change", ["input", "effective_output", "deployment", "version", "profile", "missing_cache"])
def test_profile_settlement_checks_recorded_binding_and_bounds(change):
    from app.providers.base import GenerationMetadata, TokenUsage
    from tests.test_openai_api import _request

    class Metered:
        async def generate(self, request):
            metadata = GenerationMetadata(
                "azure_openai", "deployment-test", GPT_54_MINI.price.model, None, 1, "success",
                TokenUsage(100, 20, 40, 5), Decimal("999"), GPT_54_MINI.price_version,
                GPT_54_MINI.identifier, "default")
            if change == "input":
                metadata = replace(metadata, usage=TokenUsage(272001, 20, 0, 0))
            elif change == "effective_output":
                metadata = replace(metadata, usage=TokenUsage(100, 1001, 0, 1000))
            elif change == "deployment":
                metadata = replace(metadata, requested_deployment="other")
            elif change == "version":
                metadata = replace(metadata, price_version="unreviewed")
            elif change == "profile":
                metadata = replace(metadata, profile_id=None)
            elif change == "missing_cache":
                metadata = replace(metadata, usage=TokenUsage(100, 20, None, 5))
            return StructuredGenerationResult({}, metadata)

    async def run():
        control = profile_coordinator()
        generation = _request(max_output_tokens=1000)
        if change == "missing_cache":
            await control.generate(Metered(), generation, IDENTITY, operation(), "synthetic")
        else:
            with pytest.raises(PilotError):
                await control.generate(Metered(), generation, IDENTITY, operation(), "synthetic")
        row = next(data for key, (data, _) in control.store.rows.items() if key.startswith("op-"))
        assert row["admission"]["max_output_tokens"] == 1000
        assert row["reserved"] == 229350000
        assert control.store.rows["ledger"][0]["blocked"] is (change != "missing_cache")
        if change not in {"input", "effective_output"}:
            assert row["charged"] == row["reserved"]
            assert not row["usage_known"]

    asyncio.run(run())


class Provider:
    calls = 0

    async def generate(self, request):
        self.calls += 1
        await asyncio.sleep(0)
        return StructuredGenerationResult({})


def test_offline_benchmark_manifest_has_18_single_dispatch_attempts(monkeypatch):
    import hashlib
    import hmac
    import io
    import httpx2
    from PIL import Image
    from app import pilot_access
    from app.pilot import canonical
    from app.schemas.food_analysis import FoodAnalysisRequest
    from app.use_cases.food_analysis import FoodAnalysisUseCase
    from tests.test_openai_api import _profile_provider, _profile_completion, _food_data

    manifest = json.loads((Path(__file__).parent / "fixtures/gpt54-mini-benchmark.v1.json").read_text())
    assert manifest["max_attempts"] == len(manifest["cases"]) == 18
    assert manifest["repeats"] == 1
    assert manifest["profile"] == GPT_54_MINI.identifier
    assert manifest["price_version"] == GPT_54_MINI.price_version
    assert GPT_54_MINI.reserve_usd(manifest["max_output_tokens"]) * 18 == Decimal(manifest["max_model_reserve_usd"])
    assert len({case["id"] for case in manifest["cases"]}) == 18
    limits = {"minute": 18, "day": 18, "month": 18, "concurrent": 1,
              "daily_usd": manifest["max_model_reserve_usd"], "monthly_usd": manifest["max_model_reserve_usd"]}
    control = profile_coordinator(person=limits, total=limits, max_image_bytes=3145728,
                                  max_image_dimension=1024, max_text_schema_bytes=65536,
                                  benchmark={"run_id": "offline-v1", "manifest_sha256": hashlib.sha256(
                                      canonical(manifest)).hexdigest(), "max_attempts": 18,
                                      "max_reserved_usd": "4.2174", "expires_at": 2000000000})
    monkeypatch.setenv("APP_ENV", "test")
    monkeypatch.setenv("AI_PILOT_ENABLED", "true")
    signing_key = b"synthetic-benchmark-signing-key-not-for-use"
    assert signing_key != control.secret
    monkeypatch.setenv("AI_PILOT_SIGNING_KEY", signing_key.decode())
    monkeypatch.setattr(pilot_access, "build_coordinator", lambda: control)

    async def close():
        pass

    control.store.close = close
    calls = []

    def handler(request):
        calls.append(json.loads(request.content))
        data = _food_data()
        schema = calls[-1]["response_format"]["json_schema"]["schema"]
        if "declared_nutrition" in schema["properties"]:
            data["declared_nutrition"] = None
        return httpx2.Response(200, json=_profile_completion(data))

    async def run():
        provider = _profile_provider(handler)
        use_case = FoodAnalysisUseCase(provider, 1, "purpose-test", "purpose-test", max_output_tokens=2000)
        try:
            for sequence, case in enumerate(manifest["cases"], 1):
                payload = deepcopy(case.get("payload", {}))
                if case["mode"] == "refinement":
                    payload["refinement"] = {**case["refinement"], "current_estimate": manifest["baseline"]}
                elif case["mode"] in {"image", "label"}:
                    asset = case["asset"]
                    encoded = (Path(__file__).parent / "fixtures" / asset["file"]).read_bytes()
                    assert hashlib.sha256(encoded).hexdigest() == asset["sha256"]
                    assert len(encoded) <= 3 * 1024 * 1024
                    with Image.open(io.BytesIO(encoded)) as photo:
                        photo.load()
                        assert list(photo.size) == asset["size"]
                        assert max(photo.size) <= 1024 and not photo.getexif()
                        assert photo.format == ("JPEG" if case["mode"] == "image" else "PNG")
                    if case["mode"] == "image":
                        assert "expected" not in case
                        media_type = "image/jpeg"
                    else:
                        media_type = "image/png"
                    payload["image"] = {"media_type": media_type, "data_base64": base64.b64encode(encoded).decode()}
                identifier = operation(sequence=sequence)
                envelope = {"aud": "fitness-gateway-pilot-v1", "issued": int(time.time()),
                            "tid": IDENTITY[0], "oid": IDENTITY[1], "operation": identifier,
                            "body": hashlib.sha256(canonical(payload)).hexdigest()}
                encoded = base64.urlsafe_b64encode(canonical(envelope)).decode()
                signature = hmac.new(signing_key, encoded.encode(), hashlib.sha256).hexdigest()
                identity, verified_operation = pilot_access.verify(
                    {"X-Pilot-Authorization": encoded + "." + signature, "X-Operation-Id": identifier}, payload)
                token = pilot_access._context.set((identity, verified_operation, payload))
                try:
                    result = await use_case.execute(FoodAnalysisRequest.model_validate(payload))
                    assert result.estimate.food_name == "synthetic-meal-marker"
                    assert len(calls) == sequence
                    assert calls[-1]["max_completion_tokens"] == 2000
                    has_image = any(isinstance(message["content"], list) for message in calls[-1]["messages"])
                    assert has_image is (case["mode"] in {"image", "label"})
                    if case["mode"] == "refinement":
                        assert "No image is attached" in calls[-1]["messages"][0]["content"]
                    with pytest.raises(PilotError):
                        await use_case.execute(FoodAnalysisRequest.model_validate(payload))
                    assert len(calls) == sequence
                finally:
                    pilot_access._context.reset(token)
            records = [data for key, (data, _) in control.store.rows.items() if key.startswith("op-")]
            assert sum(record["reserved"] for record in records) == 4217400000
            from tests.test_openai_api import _request
            with pytest.raises(PilotError, match="limit"):
                await control.generate(provider, _request(max_output_tokens=2000), IDENTITY, operation(sequence=19), "extra")
            assert len(calls) == 18
        finally:
            await provider.aclose()

    asyncio.run(run())


def test_two_coordinators_same_operation_only_dispatch_once():
    async def run():
        first = coordinator()
        second = coordinator(first.store)
        provider, identifier = Provider(), operation()
        results = await asyncio.gather(*(control.generate(provider, request(), IDENTITY, identifier, "fingerprint")
                                         for control in (first, second)), return_exceptions=True)
        assert provider.calls == 1
        assert sum(isinstance(result, PilotError) for result in results) == 1
    asyncio.run(run())


def test_benchmark_lifetime_limit_survives_restart_rollover_and_parallel_admission():
    from tests.test_openai_api import _request

    async def run():
        limits = {"minute": 100, "day": 100, "month": 100, "concurrent": 20,
                  "daily_usd": "100", "monthly_usd": "100"}
        benchmark = {"run_id": "durable-v1", "manifest_sha256": "a" * 64, "max_attempts": 18,
                     "max_reserved_usd": "4.2174", "expires_at": 2000000000}
        options = {"person": limits, "total": limits, "benchmark": benchmark}
        control, provider = profile_coordinator(**options), Provider()
        start = 1789646400.0
        control.clock = lambda: start
        generation = _request(max_output_tokens=2000)
        for sequence in range(1, 18):
            await control.generate(provider, generation, IDENTITY, operation(start, sequence), str(sequence))
        resumed = [profile_coordinator(control.store, **options) for _ in range(2)]
        later = start + 40 * 86400
        for replacement in resumed:
            replacement.clock = lambda: later
        results = await asyncio.gather(*(
            replacement.generate(provider, generation, IDENTITY, operation(later, 18 + index), "last")
            for index, replacement in enumerate(resumed)), return_exceptions=True)
        assert sum(isinstance(result, PilotError) for result in results) == 1
        assert provider.calls == 18
        assert control.store.rows["ledger"][0]["benchmark"] == {
            "run_id": "durable-v1", "attempts": 18, "reserved": 4217400000}
        with pytest.raises(PilotError):
            await resumed[0].generate(provider, generation, OTHER, operation(later, 30), "extra")
        assert provider.calls == 18

    asyncio.run(run())


def test_benchmark_unknown_attempt_remains_counted_after_restart():
    from tests.test_openai_api import _request

    class Unknown(Provider):
        async def generate(self, request):
            self.calls += 1
            raise TimeoutError()

    async def run():
        benchmark = {"run_id": "unknown-v1", "manifest_sha256": "b" * 64, "max_attempts": 1,
                     "max_reserved_usd": "0.2343", "expires_at": 2000000000}
        control, provider = profile_coordinator(benchmark=benchmark), Unknown()
        generation, identifier = _request(max_output_tokens=2000), operation()
        with pytest.raises(TimeoutError):
            await control.generate(provider, generation, IDENTITY, identifier, "one")
        resumed = profile_coordinator(control.store, benchmark=benchmark)
        for next_id in (identifier, operation(sequence=2)):
            with pytest.raises(PilotError):
                await resumed.generate(provider, generation, IDENTITY, next_id, "one")
        assert provider.calls == 1
        assert control.store.rows["ledger"][0]["benchmark"]["attempts"] == 1
        assert control.store.rows["ledger"][0]["benchmark"]["reserved"] == 234300000
        assert control.store.rows["ledger"][0]["active"]

    asyncio.run(run())


@pytest.mark.parametrize("change", ["missing", "run_id", "attempts", "reserved", "budget", "expired", "manifest"])
def test_benchmark_invalid_state_or_expiry_denies_before_dispatch(change):
    from tests.test_openai_api import _request

    async def run():
        benchmark = {"run_id": "closed-v1", "manifest_sha256": "c" * 64, "max_attempts": 18,
                     "max_reserved_usd": "4.2174", "expires_at": 2000000000}
        control, provider = profile_coordinator(benchmark=benchmark), Provider()
        ledger = control.store.rows["ledger"][0]
        if change == "missing":
            del ledger["benchmark"]
        elif change == "run_id":
            ledger["benchmark"]["run_id"] = "other-v1"
        elif change == "attempts":
            ledger["benchmark"]["attempts"] = True
        elif change == "reserved":
            ledger["benchmark"]["reserved"] = -1
        elif change == "budget":
            ledger["benchmark"]["reserved"] = 4217400000
        elif change == "expired":
            control.clock = lambda: 2000000000
        elif change == "manifest":
            control = profile_coordinator(control.store, benchmark={**benchmark, "manifest_sha256": "d" * 64})
        with pytest.raises(PilotError):
            await control.generate(provider, _request(max_output_tokens=2000), IDENTITY,
                                   operation(control.clock()), "one")
        assert provider.calls == 0
        assert not any(key.startswith("op-") for key in control.store.rows)

    asyncio.run(run())


def test_crash_after_reservation_never_reclaims_operation():
    async def run():
        control = coordinator()
        identifier = operation()
        await control.reserve(IDENTITY, identifier, "fingerprint", control.bound(request()))
        replacement = coordinator(control.store)
        provider = Provider()
        with pytest.raises(PilotError, match="already accepted"):
            await replacement.generate(provider, request(), IDENTITY, identifier, "fingerprint")
        with pytest.raises(PilotError, match="different content"):
            await replacement.generate(provider, request(), IDENTITY, identifier, "different")
        assert provider.calls == 0
    asyncio.run(run())


def test_missing_usage_retains_full_context_reserve():
    async def run():
        control = coordinator()
        await control.generate(Provider(), request(), IDENTITY, operation(), "fingerprint")
        rows = [data for key, (data, _) in control.store.rows.items() if key.startswith("op-")]
        assert rows[0]["charged"] == rows[0]["reserved"] == 1047776000
        assert rows[0]["state"] == "succeeded"
        assert not rows[0]["usage_known"]
    asyncio.run(run())


def test_table_transaction_uses_same_partition_and_conditional_replace():
    from azure.core import MatchConditions
    from azure.data.tables import UpdateMode
    from app.pilot_table import AzureTableStore

    class Client:
        async def submit_transaction(self, operations, **kwargs):
            assert kwargs["logging_enable"] is False
            assert len(operations) == 2
            assert operations[0][0] == "update"
            assert operations[0][2] == {"mode": UpdateMode.REPLACE, "etag": "version-1",
                                        "match_condition": MatchConditions.IfNotModified}
            assert operations[1][0] == "create"
            assert {entry[1]["PartitionKey"] for entry in operations} == {"pilot-v1"}

    asyncio.run(AzureTableStore(Client()).commit([("ledger", {"count": 1}, "version-1"),
                                                ("op-synthetic", {"state": "pending"}, None)]))


def test_direct_azure_requires_coordinator_permit(monkeypatch):
    from tests.test_openai_api import _provider, _request

    monkeypatch.setenv("APP_ENV", "test")
    monkeypatch.setenv("AI_PILOT_ENABLED", "true")

    async def run():
        provider = _provider(lambda request: pytest.fail("Unapproved dispatch"))
        try:
            with pytest.raises(PilotError):
                await provider.generate(_request())
        finally:
            await provider.aclose()
    asyncio.run(run())


def test_direct_gateway_with_service_token_cannot_assert_identity(monkeypatch):
    from fastapi.testclient import TestClient
    from app.main import create_app
    from app.dependencies import get_food_analysis_use_case
    from app.use_cases.food_analysis import FoodAnalysisUseCase

    monkeypatch.setenv("APP_ENV", "test")
    monkeypatch.setenv("GATEWAY_SERVICE_TOKEN", "synthetic-service")
    monkeypatch.setenv("AI_PILOT_ENABLED", "true")
    app = create_app()
    provider = Provider()
    app.dependency_overrides[get_food_analysis_use_case] = lambda: FoodAnalysisUseCase(provider, 1, "text")
    response = TestClient(app, raise_server_exceptions=False).post(
        "/v1/food-analysis", json={"food_description": "synthetic"},
        headers={"X-Service-Token": "synthetic-service", "X-Pilot-Identity": IDENTITY[1],
                 "X-Operation-Id": operation()})
    assert response.status_code == 403
    assert provider.calls == 0


@pytest.mark.parametrize("scope", ["person", "total"])
@pytest.mark.parametrize("limit", ["minute", "day", "month", "daily_usd", "monthly_usd", "concurrent"])
def test_person_and_global_limits_across_coordinators(scope, limit):
    async def run():
        template = coordinator().policy.model_dump(mode="json")[scope]
        template[limit] = "1.1" if limit.endswith("usd") else 1
        control = coordinator(**{scope: template})
        await control.reserve(IDENTITY, operation(sequence=1), "one", control.bound(request()))
        second = coordinator(control.store, **{scope: template})
        who = OTHER if scope == "total" else IDENTITY
        with pytest.raises(PilotError, match="limit"):
            await second.generate(Provider(), request(), who, operation(sequence=2), "two")
    asyncio.run(run())


def test_concurrent_distinct_operations_share_global_budget():
    async def run():
        limits = coordinator().policy.total.model_dump(mode="json")
        limits["daily_usd"] = "1.1"
        first = coordinator(total=limits)
        second = coordinator(first.store, total=limits)
        results = await asyncio.gather(first.reserve(IDENTITY, operation(sequence=1), "one", first.bound(request())),
                                       second.reserve(OTHER, operation(sequence=2), "two", second.bound(request())),
                                       return_exceptions=True)
        assert sum(isinstance(result, str) for result in results) == 1
        assert sum(isinstance(result, PilotError) for result in results) == 1
    asyncio.run(run())


@pytest.mark.parametrize("phase", ["read", "reserve", "dispatch", "settle"])
def test_store_failure_or_lost_write_ack_never_redispatches(phase):
    async def run():
        control = coordinator()
        real_read, real_commit = control.store.read, control.store.commit
        writes = 0

        async def commit(changes):
            nonlocal writes
            writes += 1
            await real_commit(changes)
            if {"reserve": 1, "dispatch": 2, "settle": 3}.get(phase) == writes:
                raise OSError("synthetic-sensitive-store-detail")

        async def read(key):
            if phase == "read":
                raise OSError("synthetic-sensitive-store-detail")
            return await real_read(key)

        control.store.commit, control.store.read = commit, read
        provider, identifier = Provider(), operation()
        with pytest.raises(PilotError):
            await control.generate(provider, request(), IDENTITY, identifier, "one")
        assert provider.calls == (1 if phase == "settle" else 0)
        if phase != "read":
            with pytest.raises(PilotError):
                await control.generate(provider, request(), IDENTITY, identifier, "one")
            assert provider.calls == (1 if phase == "settle" else 0)
    asyncio.run(run())


def test_timeout_after_dispatch_stays_unknown_with_reserve_and_slot():
    class TimedOut(Provider):
        async def generate(self, request):
            self.calls += 1
            await asyncio.Event().wait()

    async def run():
        control, provider, identifier = coordinator(), TimedOut(), operation()
        short_request = replace(request(), timeout_seconds=0.01)
        with pytest.raises(TimeoutError):
            await control.generate(provider, short_request, IDENTITY, identifier, "one")
        row = next(data for key, (data, _) in control.store.rows.items() if key.startswith("op-"))
        assert row["state"] == "unknown" and row["charged"] == row["reserved"]
        assert control.store.rows["ledger"][0]["active"]
        with pytest.raises(PilotError):
            await control.generate(provider, short_request, IDENTITY, identifier, "one")
        assert provider.calls == 1
    asyncio.run(run())


def test_actual_cost_reconciliation_never_double_counts_cache_or_reasoning():
    from app.providers.base import GenerationMetadata, TokenUsage

    class Metered(Provider):
        async def generate(self, request):
            return StructuredGenerationResult({}, GenerationMetadata(
                "azure_openai", "deployment", "gpt-4.1-mini-2025-04-14", None, 1, "success",
                TokenUsage(100, 20, 40, 5), Decimal("999"), "synthetic"))

    async def run():
        control = coordinator()
        await control.generate(Metered(), request(), IDENTITY, operation(), "one")
        row = next(data for key, (data, _) in control.store.rows.items() if key.startswith("op-"))
        assert row["charged"] == 104000
        assert row["usage_known"]
        assert not control.store.rows["ledger"][0]["active"]
        assert {value["cost"] for value in control.store.rows["ledger"][0]["buckets"].values()} == {104000}
    asyncio.run(run())


@pytest.mark.parametrize("reason", ["output", "text", "missing_price", "model", "expired", "ledger", "identity", "old_operation"])
def test_missing_or_unbounded_admission_prevents_provider_call(reason):
    async def run():
        control, provider, generation = coordinator(), Provider(), request()
        identity, identifier = IDENTITY, operation()
        if reason == "output":
            generation = replace(generation, max_output_tokens=None)
        elif reason == "text":
            generation = replace(generation, messages=[GenerationMessage("user", "x" * 20000)])
        elif reason == "missing_price":
            control.prices.deployments.clear()
        elif reason == "model":
            control.prices.deployments["deployment"] = control.prices.deployments["deployment"].model_copy(update={"model": "unverified"})
        elif reason == "expired":
            control.clock = lambda: 2000000001
        elif reason == "ledger":
            control.store.rows.clear()
        elif reason == "identity":
            identity = (OTHER[1], OTHER[1])
        elif reason == "old_operation":
            identifier = operation(time.time() - 86400)
        with pytest.raises(PilotError):
            await control.generate(provider, generation, identity, identifier, "one")
        assert provider.calls == 0
    asyncio.run(run())


@pytest.mark.parametrize("mode", ["text", "image", "refinement"])
@pytest.mark.parametrize("profile", [False, True])
def test_full_backend_gateway_sdk_pilot_contract(monkeypatch, caplog, mode, profile):
    monkeypatch.syspath_prepend(str(Path(__file__).resolve().parents[2] / "backend"))
    import azure.functions as func
    import httpx2
    from fastapi.testclient import TestClient
    from api.food_analysis import food_analysis
    from gateway_client import GatewayClient
    from app.dependencies import get_food_analysis_use_case
    from app.main import create_app
    from app import pilot_access
    from app.use_cases.food_analysis import FoodAnalysisUseCase
    from tests.test_openai_api import _provider, _completion, _food_data, _profile_provider, _profile_completion
    from tests.image_fixtures import make_valid_jpeg_bytes

    control = profile_coordinator() if profile else coordinator()

    async def close():
        pass

    control.store.close = close
    signing_key = "synthetic-signing-secret-not-real-000"
    settings = {"APP_ENV": "test", "AI_PILOT_ENABLED": "true", "EASY_AUTH_ENABLED": "true",
                "GATEWAY_SERVICE_TOKEN": "synthetic-service", "AI_PILOT_SIGNING_KEY": signing_key,
                "AI_PILOT_ALLOWLIST_JSON": json.dumps([{"tid": IDENTITY[0], "oid": IDENTITY[1]}]),
                "AI_PILOT_TENANT_ID": IDENTITY[0], "AI_PILOT_AUDIENCE": "synthetic-api",
                "AI_PILOT_CLIENT_ID": OTHER[1], "AI_PILOT_SCOPE": "Analysis.Invoke",
                "AI_PILOT_ISSUER": f"https://login.microsoftonline.com/{IDENTITY[0]}/v2.0"}
    for name, value in settings.items():
        monkeypatch.setenv(name, value)
    claims = {"tid": IDENTITY[0], "oid": IDENTITY[1], "aud": "synthetic-api", "azp": OTHER[1],
              "scp": "Analysis.Invoke", "iss": settings["AI_PILOT_ISSUER"]}
    principal = base64.b64encode(json.dumps({"auth_typ": "aad", "claims": [
        {"typ": name, "val": value} for name, value in claims.items()]}).encode()).decode()
    identifier = operation()
    headers = {"Content-Type": "application/json", "X-MS-CLIENT-PRINCIPAL-ID": IDENTITY[1],
               "X-MS-CLIENT-PRINCIPAL": principal, "X-Operation-Id": identifier,
               "X-Request-Id": "diagnostic-only", "X-Pilot-Authorization": "client-forgery"}
    payload = {"food_description": "synthetic-description-marker"}
    if mode == "refinement":
        payload = {"refinement": {"correction_text": "synthetic-correction-marker", "current_estimate": _food_data(),
                                  "source_kind": "image", "iteration": 1}}
    raw = json.dumps(payload).encode()
    if mode == "image":
        headers["Content-Type"] = "multipart/form-data; boundary=pilot-test"
        raw = (b'--pilot-test\r\nContent-Disposition: form-data; name="image"; filename="test.jpg"\r\n'
               b'Content-Type: image/jpeg\r\n\r\n' + make_valid_jpeg_bytes() + b'\r\n--pilot-test--\r\n')
    calls = []

    def handler(request):
        calls.append(request)
        data = _food_data()
        if mode == "text":
            data["declared_nutrition"] = None
        completion = _profile_completion(data) if profile else _completion(data, model="gpt-4.1-mini-2025-04-14")
        return httpx2.Response(200, json=completion)

    provider = (_profile_provider(handler) if profile else
                _provider(handler, model_routes={"text": "deployment", "image": "deployment"}, prices=control.prices))
    app = create_app()
    app.dependency_overrides[get_food_analysis_use_case] = lambda: FoodAnalysisUseCase(
        provider, 1, "purpose-test" if profile else "text", "purpose-test" if profile else "image",
        max_output_tokens=2000 if profile else 100)
    monkeypatch.setattr(pilot_access, "build_coordinator", lambda: control)
    real_init = GatewayClient.__init__
    clients = []

    def init(self, **kwargs):
        client = TestClient(app, raise_server_exceptions=False)
        clients.append(client)
        real_init(self, **{**kwargs, "client": client})

    monkeypatch.setattr(GatewayClient, "__init__", init)
    caplog.set_level(logging.DEBUG)
    try:
        response = food_analysis(func.HttpRequest(method="POST", url="/api/food-analysis", headers=headers, body=raw))
        assert response.status_code == 200
        assert json.loads(response.get_body()) == {"estimate": _food_data()}
        assert response.headers["X-Request-Id"] == "diagnostic-only"
        repeated = food_analysis(func.HttpRequest(method="POST", url="/api/food-analysis", headers=headers, body=raw))
        assert repeated.status_code == 409
        assert json.loads(repeated.get_body())["error"]["code"] == "operation_consumed"
        assert len(calls) == 1
        for marker in (identifier, IDENTITY[1], signing_key, "synthetic-description-marker", "synthetic-correction-marker"):
            assert marker not in caplog.text
        stored = json.dumps(control.store.rows)
        assert "synthetic-description-marker" not in stored
        assert "synthetic-meal-marker" not in stored
    finally:
        for client in clients:
            client.close()
        asyncio.run(provider.aclose())


@pytest.mark.parametrize("change", ["body", "identity", "operation", "expired", "future", "audience", "signature"])
def test_signed_assertion_tampering_rejected(monkeypatch, change):
    import hashlib
    import hmac
    from app.pilot_access import verify
    from app.pilot import canonical

    monkeypatch.setenv("AI_PILOT_ENABLED", "true")
    monkeypatch.setenv("AI_PILOT_SIGNING_KEY", SECRET.decode())
    payload = {"food_description": "synthetic"}
    identifier = operation()
    envelope = {"tid": IDENTITY[0], "oid": IDENTITY[1], "operation": identifier,
                "issued": int(time.time()), "body": hashlib.sha256(canonical(payload)).hexdigest(),
                "aud": "fitness-gateway-pilot-v1"}
    if change == "expired":
        envelope["issued"] -= 61
    if change == "future":
        envelope["issued"] += 10
    if change == "audience":
        envelope["aud"] = "another-service"
    encoded = base64.urlsafe_b64encode(canonical(envelope)).decode()
    signature = hmac.new(SECRET, encoded.encode(), hashlib.sha256).hexdigest()
    if change == "identity":
        envelope["oid"] = OTHER[1]
        encoded = base64.urlsafe_b64encode(canonical(envelope)).decode()
    if change == "signature":
        signature = "0" * 64
    if change == "body":
        payload["food_description"] = "changed"
    headers = {"X-Pilot-Authorization": encoded + "." + signature,
               "X-Operation-Id": operation(sequence=2) if change == "operation" else identifier}
    with pytest.raises(PilotError):
        verify(headers, payload)


def test_time_rollover_and_backward_clock_do_not_reset_limits():
    async def run():
        control = coordinator()
        start = 1789646400.0
        control.clock = lambda: start
        await control.generate(Provider(), request(), IDENTITY, operation(start, 1), "one")
        control.clock = lambda: start + 60
        await control.generate(Provider(), request(), IDENTITY, operation(start + 60, 2), "two")
        buckets = control.store.rows["ledger"][0]["buckets"]
        assert {value["count"] for key, value in buckets.items() if ":minute:" in key} == {1}
        assert {value["count"] for key, value in buckets.items() if ":day:" in key or ":month:" in key} == {2}
        control.clock = lambda: start + 59
        with pytest.raises(PilotError):
            await control.generate(Provider(), request(), IDENTITY, operation(start + 59, 3), "three")
    asyncio.run(run())


def test_policy_mismatch_and_missing_configuration_fail_closed(monkeypatch):
    from app.pilot_access import build_coordinator

    monkeypatch.setenv("APP_ENV", "test")
    monkeypatch.setenv("AI_PROVIDER", "azure_openai")
    monkeypatch.delenv("AI_PILOT_POLICY_JSON", raising=False)
    with pytest.raises(PilotError):
        build_coordinator(MemoryCAS())

    async def run():
        first = coordinator()
        second = coordinator(first.store, version="different-policy")
        with pytest.raises(PilotError):
            await second.generate(Provider(), request(), IDENTITY, operation(), "one")
    asyncio.run(run())


def test_permit_is_single_use_and_bound_to_generation_request():
    import hashlib
    from dataclasses import asdict
    from app.pilot import DispatchPermit, _permit, canonical, consume_permit

    generation = request()
    permit = DispatchPermit(hashlib.sha256(canonical(asdict(generation))).hexdigest(), time.time() + 1)
    token = _permit.set(permit)
    try:
        with pytest.raises(PilotError):
            consume_permit(replace(generation, max_output_tokens=99))
        consume_permit(generation)
        with pytest.raises(PilotError):
            consume_permit(generation)
    finally:
        _permit.reset(token)


def test_cleanup_expired_unknown_blocks_ledger_before_deleting_fingerprint():
    from app.pilot_table import AzureTableStore

    class Entity(dict):
        metadata = {"etag": "operation-etag"}

    class Client:
        def query_entities(self, *args, **kwargs):
            async def rows():
                yield Entity(RowKey="op-expired", data=json.dumps({"expires": 1, "state": "unknown"}))
            return rows()

        async def delete_entity(self, partition, key, **kwargs):
            assert storage.rows["ledger"][0]["blocked"] is True
            assert kwargs["etag"] == "operation-etag"
            assert key == "op-expired"

    async def run():
        store = AzureTableStore(Client())
        store.read, store.commit = storage.read, storage.commit
        assert await store.cleanup(time.time(), 2678400) == 1

    storage = coordinator().store
    storage.rows["ledger"][0]["active"]["op-expired"] = "synthetic-person"
    asyncio.run(run())
    assert not storage.rows["ledger"][0]["active"]


def test_cleanup_then_clock_rollback_cannot_redispatch_deleted_operation():
    from app.pilot_table import AzureTableStore

    async def run():
        control, provider = coordinator(), Provider()
        start = 1789646400.0
        control.clock = lambda: start
        identifier = operation(start)
        await control.generate(provider, request(), IDENTITY, identifier, "one")
        operation_key = next(key for key in control.store.rows if key.startswith("op-"))

        class Entity(dict):
            metadata = {"etag": control.store.rows[operation_key][1]}

        class Client:
            def query_entities(self, *args, **kwargs):
                async def rows():
                    yield Entity(RowKey=operation_key, data=json.dumps(control.store.rows[operation_key][0]))
                return rows()

            async def delete_entity(self, partition, key, **kwargs):
                del control.store.rows[key]

        table = AzureTableStore(Client())
        table.read, table.commit = control.store.read, control.store.commit
        assert await table.cleanup(start + control.policy.retention_seconds + 1,
                                   control.policy.retention_seconds) == 1
        assert operation_key not in control.store.rows
        control.clock = lambda: start + 60
        with pytest.raises(PilotError):
            await control.generate(provider, request(), IDENTITY, identifier, "one")
        assert provider.calls == 1

    asyncio.run(run())


@pytest.mark.parametrize("usage", [(100, 20, None, 5), (100, 20, 101, 5), (100, 20, 40, 21),
                                   (True, 20, 0, None), (100, -1, 0, None)])
def test_invalid_or_partial_usage_cannot_release_cost(usage):
    from app.providers.base import GenerationMetadata, TokenUsage

    class Metered(Provider):
        async def generate(self, request):
            return StructuredGenerationResult({}, GenerationMetadata(
                "azure_openai", "deployment", "gpt-4.1-mini-2025-04-14", None, 1, "success",
                TokenUsage(*usage), None, "synthetic"))

    async def run():
        control = coordinator()
        await control.generate(Metered(), request(), IDENTITY, operation(), "one")
        row = next(data for key, (data, _) in control.store.rows.items() if key.startswith("op-"))
        assert row["charged"] == row["reserved"]
        assert not row["usage_known"]
    asyncio.run(run())


def test_rounding_never_increases_approved_budget():
    from decimal import ROUND_FLOOR
    from app.pilot import units

    assert units(Decimal("0.0000000001")) == 1
    assert units(Decimal("0.0000000009"), ROUND_FLOOR) == 0


@pytest.mark.parametrize("http_status", [409, 412, 500, 503])
def test_table_conflicts_are_distinguished_from_unknown_writes(http_status, caplog):
    from azure.data.tables import TableTransactionError
    from app.pilot_table import AzureTableStore

    class Response:
        status_code = http_status
        reason = "synthetic-sensitive-table-error"
        headers = {}

    class Client:
        calls = 0

        async def submit_transaction(self, *args, **kwargs):
            self.calls += 1
            raise TableTransactionError(message="synthetic-sensitive-table-error", response=Response())

    client = Client()
    with pytest.raises(Conflict if http_status in {409, 412} else PilotError) as caught:
        asyncio.run(AzureTableStore(client).commit([("ledger", {}, "etag")]))
    assert client.calls == 1
    assert "synthetic-sensitive-table-error" not in str(caught.value)
    assert "synthetic-sensitive-table-error" not in caplog.text


def test_cancelled_dispatch_keeps_unknown_state():
    class Cancelled(Provider):
        async def generate(self, request):
            self.calls += 1
            raise asyncio.CancelledError()

    async def run():
        control, provider = coordinator(), Cancelled()
        with pytest.raises(asyncio.CancelledError):
            await control.generate(provider, request(), IDENTITY, operation(), "one")
        row = next(data for key, (data, _) in control.store.rows.items() if key.startswith("op-"))
        assert row["state"] == "unknown"
        assert row["charged"] == row["reserved"]
        assert provider.calls == 1
    asyncio.run(run())


@pytest.mark.parametrize("model,usage,version", [
    ("unexpected-model", None, "synthetic"),
    ("unexpected-model", (100, 20, 0, None), None),
    ("gpt-4.1-mini-2025-04-14", (1047577, 20, 0, None), "stale"),
    ("gpt-4.1-mini-2025-04-14", (100, 101, 0, None), None),
])
def test_reported_bound_violation_blocks_even_without_cost_metadata(model, usage, version):
    from app.providers.base import GenerationMetadata, TokenUsage

    class Unexpected(Provider):
        async def generate(self, request):
            self.calls += 1
            return StructuredGenerationResult({}, GenerationMetadata(
                "azure_openai", "deployment", model, None, 1, "success",
                TokenUsage(*usage) if usage else None, None, version))

    async def run():
        control, provider = coordinator(), Unexpected()
        await control.generate(provider, request(), IDENTITY, operation(), "one")
        assert control.store.rows["ledger"][0]["blocked"]
        row = next(data for key, (data, _) in control.store.rows.items() if key.startswith("op-"))
        assert row["charged"] == row["reserved"]
        assert not row["usage_known"]
        with pytest.raises(PilotError):
            await coordinator(control.store).generate(provider, request(), OTHER, operation(sequence=2), "two")
        assert provider.calls == 1
    asyncio.run(run())


@pytest.mark.parametrize("action", ["read", "commit"])
def test_table_sdk_never_logs_operation_keys(monkeypatch, caplog, action):
    from azure.core.credentials import AccessToken
    from azure.core.pipeline.transport import AsyncHttpTransport
    from azure.data.tables.aio import TableClient
    from app import pilot_table

    requests = []

    class Credential:
        async def get_token(self, *args, **kwargs):
            return AccessToken("synthetic-token", 2000000000)

        async def close(self):
            pass

    class NoNetwork(AsyncHttpTransport):
        calls = 0

        async def open(self):
            pass

        async def close(self):
            pass

        async def __aexit__(self, *args):
            await self.close()

        async def send(self, request, **kwargs):
            self.calls += 1
            requests.append(request)
            raise RuntimeError("Synthetic transport failure")

    transport = NoNetwork()
    monkeypatch.setattr(pilot_table, "ManagedIdentityCredential", Credential)
    monkeypatch.setattr(pilot_table, "TableClient", lambda *args, **kwargs: TableClient(
        *args, transport=transport, **kwargs))
    caplog.set_level(logging.DEBUG)

    async def run():
        store = pilot_table.AzureTableStore.connect("https://synthetic.table.core.windows.net", "Synthetic")
        try:
            with pytest.raises(PilotError):
                if action == "read":
                    await store.read("op-synthetic-private-key")
                else:
                    await store.commit([("ledger", {}, "operation-etag"),
                                        ("op-synthetic-private-key", {"fingerprint": "private-fingerprint"}, None)])
        finally:
            await store.close()

    asyncio.run(run())
    assert transport.calls == 1
    sent = requests[0]
    if action == "read":
        assert "op-synthetic-private-key" in sent.url
    else:
        from email.parser import BytesParser
        from email.policy import default

        assert sent.method == "POST" and sent.url.endswith("/$batch")
        message = BytesParser(policy=default).parsebytes(
            ("Content-Type: " + sent.headers["Content-Type"] + "\r\n\r\n").encode() + sent.body)
        changesets = list(message.iter_parts())
        assert len(changesets) == 1
        operations = list(changesets[0].iter_parts())
        assert len(operations) == 2
        update, create = [part.get_payload(decode=True).decode() for part in operations]
        update_headers = BytesParser(policy=default).parsebytes(update.partition("\r\n")[2].encode())
        assert update.startswith("PUT ") and update_headers["If-Match"] == '"operation-etag"'
        assert create.startswith("POST ") and '"RowKey": "op-synthetic-private-key"' in create
        assert all('"PartitionKey": "pilot-v1"' in body for body in (update, create))
    assert "op-synthetic-private-key" not in caplog.text
    assert "synthetic-token" not in caplog.text
    assert "private-fingerprint" not in caplog.text


@pytest.mark.parametrize("offset,accepted", [(-3601, False), (-3600, True), (30, True), (31, False)])
def test_operation_age_boundaries(offset, accepted):
    from app.pilot import operation_id

    now = 1789646400.0
    identifier = operation(now + offset)
    if accepted:
        assert operation_id(identifier, now, 3600) == identifier
    else:
        with pytest.raises(PilotError, match="UUIDv7"):
            operation_id(identifier, now, 3600)


def test_client_timestamp_never_selects_budget_period_or_authorizes_identity():
    from datetime import datetime, timezone

    async def run():
        control = coordinator()
        now = datetime(2026, 10, 1, tzinfo=timezone.utc).timestamp()
        control.clock = lambda: now
        identifier = operation(now - 60)
        await control.reserve(IDENTITY, identifier, "one", control.bound(request()))
        buckets = control.store.rows["ledger"][0]["buckets"]
        assert all(key.endswith(("202610010000", "20261001", "202610")) for key in buckets)
        with pytest.raises(PilotError, match="identity"):
            await control.reserve((OTHER[1], OTHER[1]), identifier, "one", control.bound(request()))

    asyncio.run(run())


def test_same_operation_is_scoped_to_verified_identity():
    async def run():
        control, provider, identifier = coordinator(), Provider(), operation()
        for identity in (IDENTITY, OTHER):
            await control.generate(provider, request(), identity, identifier, "same-payload")
        assert provider.calls == 2
        assert len([key for key in control.store.rows if key.startswith("op-")]) == 2

    asyncio.run(run())


def test_expired_pending_dispatch_keeps_reserve_and_cannot_be_reclaimed():
    async def run():
        control, provider = coordinator(), Provider()
        now = time.time()
        control.clock = lambda: now
        identifier = operation(now)
        key = await control.reserve(IDENTITY, identifier, "one", control.bound(request()))
        control.clock = lambda: now + 31
        with pytest.raises(PilotError):
            await control.mark_dispatched(key)
        with pytest.raises(PilotError):
            await control.generate(provider, request(), IDENTITY, identifier, "one")
        assert provider.calls == 0
        assert control.store.rows[key][0]["state"] == "pending"
        assert key in control.store.rows["ledger"][0]["active"]

    asyncio.run(run())


def test_production_guard_still_wins_with_valid_pilot_permit(monkeypatch):
    from app.errors import ServiceNotReadyError
    from tests.test_openai_api import _provider

    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.setenv("AI_PILOT_ENABLED", "true")

    async def run():
        control = coordinator()
        provider = _provider(lambda request: pytest.fail("Production dispatch"),
                             model_routes=control.routes, prices=control.prices)
        try:
            with pytest.raises(ServiceNotReadyError):
                await control.generate(provider, request(), IDENTITY, operation(), "one")
        finally:
            await provider.aclose()

    asyncio.run(run())