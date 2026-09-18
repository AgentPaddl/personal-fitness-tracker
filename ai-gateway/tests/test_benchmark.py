import asyncio
import json
import logging
from pathlib import Path
import time

import pytest

from app.benchmark import Approval, MANIFEST_HASH, RunState, load_cases, make_coordinator, run_one
from app.pilot import Conflict, PilotError
from app.providers.pricing import GPT_54_MINI
from tests.test_pilot import MemoryCAS


@pytest.mark.parametrize("environment", ["production", "development"])
def test_local_guard_needs_more_than_environment_name(monkeypatch, environment):
    from app.benchmark_azure import local_guard
    monkeypatch.setenv("APP_ENV", environment)
    monkeypatch.setenv("AI_PILOT_ENABLED", "true")
    monkeypatch.setenv("AZURE_CONFIG_DIR", "/unused-offline")
    monkeypatch.setenv("IDENTITY_ENDPOINT", "http://managed-identity.invalid")
    with pytest.raises(PilotError):
        local_guard()


def resources(config):
    tags = {"purpose": "pft-public-benchmark", "benchmarkRun": config.run_id,
            "manifestSha256": MANIFEST_HASH, "expiresAt": str(config.expires_at)}
    network = {"defaultAction": "Deny", "bypass": "None", "ipRules": [{"value": config.egress_ipv4}]}
    group = {"id": config.group_id, "location": "swedencentral", "tags": tags}
    account = {**group, "id": config.account_id, "kind": "OpenAI", "sku": {"name": "S0"},
               "properties": {"provisioningState": "Succeeded", "publicNetworkAccess": "Enabled",
                              "networkAcls": network, "disableLocalAuth": True,
                              "customSubDomainName": config.account_name,
                              "endpoint": f"https://{config.account_name}.openai.azure.com/"}}
    storage = {**group, "id": config.storage_id, "kind": "StorageV2", "sku": {"name": "Standard_LRS"},
               "properties": {"provisioningState": "Succeeded", "publicNetworkAccess": "Enabled",
                              "networkAcls": network, "allowSharedKeyAccess": False, "allowBlobPublicAccess": False,
                              "supportsHttpsTrafficOnly": True, "minimumTlsVersion": "TLS1_2",
                              "primaryEndpoints": {"table": f"https://{config.storage_name}.table.core.windows.net/"}}}
    deployment = {"id": config.account_id + "/deployments/mini-bench",
                  "sku": {"name": "DataZoneStandard", "capacity": 10},
                  "properties": {"provisioningState": "Succeeded", "versionUpgradeOption": "NoAutoUpgrade",
                                 "model": {"format": "OpenAI", "name": "gpt-5.4-mini", "version": "2026-03-17"}}}
    inventory = {"value": [{"id": config.account_id}, {"id": config.storage_id}]}
    return group, account, deployment, storage, inventory


@pytest.mark.parametrize("mutation", ["none", "production_group", "tag", "model", "sku", "upgrade", "keys", "network", "extra_resource"])
def test_attestation_rejects_wrong_resource_even_when_environment_renamed(mutation, monkeypatch):
    from app.benchmark_azure import validate_resources
    monkeypatch.setenv("APP_ENV", "development")
    config = approval()
    group, account, deployment, storage, inventory = resources(config)
    if mutation == "production_group":
        group["id"] = group["id"].replace("rg-pft-mini-bench-offline", "production")
    elif mutation == "tag":
        account["tags"]["purpose"] = "production"
    elif mutation == "model":
        deployment["properties"]["model"]["version"] = "latest"
    elif mutation == "sku":
        deployment["sku"]["name"] = "GlobalStandard"
    elif mutation == "upgrade":
        deployment["properties"]["versionUpgradeOption"] = "OnceNewDefaultVersionAvailable"
    elif mutation == "keys":
        storage["properties"]["allowSharedKeyAccess"] = True
    elif mutation == "network":
        account["properties"]["networkAcls"]["defaultAction"] = "Allow"
    elif mutation == "extra_resource":
        inventory["value"].append({"id": config.group_id + "/production-app"})
    if mutation == "none":
        validate_resources(config, group, account, deployment, storage, inventory)
    else:
        with pytest.raises(PilotError):
            validate_resources(config, group, account, deployment, storage, inventory)


def approval():
    return Approval(subscription_id="00000000-0000-4000-8000-000000000003",
                    tenant_id="00000000-0000-4000-8000-000000000001",
                    operator_id="00000000-0000-4000-8000-000000000002",
                    run_id="offline", account_name="pftbenchoffline", storage_name="pftbenchoffline",
                    egress_ipv4="8.8.8.8", created_at=int(time.time()) - 1,
                    expires_at=int(time.time()) + 600, manifest_sha256=MANIFEST_HASH,
                    price_version=GPT_54_MINI.price_version, capacity=10)


def test_frozen_public_requests_are_complete():
    manifest, cases = load_cases()
    assert len(cases) == manifest["max_attempts"] == 18
    assert sum(bool(request.attachments) for case, request in cases) == 8
    assert all(request.max_output_tokens == 2000 for case, request in cases)


def test_claim_race_restart_and_reinitialization_fail_closed():
    async def run():
        store = MemoryCAS()
        config = approval()
        _, cases = load_cases()
        first = RunState(store, make_coordinator(store, config), config, cases)
        second = RunState(store, make_coordinator(store, config), config, cases)
        await first.initialize()
        before, _ = await store.read("case-T1")
        results = await asyncio.gather(first.claim(), second.claim(), return_exceptions=True)
        assert sum(isinstance(result, tuple) for result in results) == 1
        assert sum(isinstance(result, (Conflict, PilotError)) for result in results) == 1
        restarted = RunState(store, make_coordinator(store, config), config, cases)
        with pytest.raises(PilotError):
            await restarted.claim()
        with pytest.raises(Conflict):
            await restarted.initialize()
        after, _ = await store.read("case-T1")
        assert before["operation"] == after["operation"]
    asyncio.run(run())


def test_uncertain_claim_ack_never_reopens_case():
    class LostAcknowledgement(MemoryCAS):
        async def commit(self, changes):
            await super().commit(changes)
            if any(data.get("state") == "busy" for _, data, _ in changes):
                raise PilotError()

    async def run():
        store = LostAcknowledgement()
        config = approval()
        _, cases = load_cases()
        state = RunState(store, make_coordinator(store, config), config, cases)
        await state.initialize()
        with pytest.raises(PilotError):
            await state.claim()
        with pytest.raises(PilotError):
            await RunState(store, state.control, config, cases).claim()
    asyncio.run(run())


@pytest.mark.parametrize("outcome", ["success", "timeout", "usage_missing", "refused", "model_drift"])
def test_full_runner_single_dispatch_and_results(monkeypatch, tmp_path, outcome, caplog):
    import httpx2
    from app.providers.openai_api import AzureOpenAIProvider
    from tests.test_openai_api import _food_data, _profile_completion

    monkeypatch.setenv("APP_ENV", "development")
    monkeypatch.setenv("AI_PILOT_ENABLED", "true")
    caplog.set_level(logging.DEBUG)
    calls, token_calls = [], []

    async def token():
        token_calls.append(1)
        return "synthetic-token-not-a-secret"

    def handler(request):
        calls.append(request)
        if outcome == "timeout":
            raise httpx2.ReadTimeout("synthetic-private-provider-diagnostic")
        response = _profile_completion(_food_data())
        if outcome == "usage_missing":
            response["usage"] = None
        if outcome == "refused":
            response["choices"][0]["message"]["refusal"] = "synthetic-refusal"
        if outcome == "model_drift":
            response["model"] = "different-model"
        return httpx2.Response(200, json=response)

    async def run():
        store = MemoryCAS()
        config = approval()
        _, cases = load_cases()
        control = make_coordinator(store, config)
        state = RunState(store, control, config, cases)
        await state.initialize()
        provider = AzureOpenAIProvider(endpoint="https://pftbenchoffline.openai.azure.com",
                                       token_provider=token, dispatch_guard=lambda: None,
                                       model_routes=control.routes, prices=control.prices,
                                       profile_bindings=control.profile_bindings,
                                       transport=httpx2.MockTransport(handler))
        try:
            record = await run_one(state, provider, {"offline": True}, tmp_path / "results")
            assert record["status"] == ("succeeded" if outcome == "success" else "halted")
            assert record["usage_known"] is (outcome in {"success", "refused"})
            if outcome in {"timeout", "usage_missing", "model_drift"}:
                assert record["charged_usd"] is None
                assert record["retained_reserve_usd"] == "0.2343"
            assert record["provider_ms"] is not None
            assert json.loads((tmp_path / "results/T1.json").read_text()) == record
            assert (tmp_path / "results/T1.json").stat().st_mode & 0o777 == 0o600
            with pytest.raises(PilotError):
                await run_one(RunState(store, control, config, cases), provider, {}, tmp_path / "results")
            ledger, _ = await store.read("ledger")
            assert ledger["benchmark"]["attempts"] == 1
        finally:
            await provider.aclose()
    asyncio.run(run())
    assert len(calls) == len(token_calls) == 1
    assert calls[0].headers["Authorization"] == "Bearer synthetic-token-not-a-secret"
    assert "synthetic-private-provider-diagnostic" not in caplog.text
    assert "synthetic-token-not-a-secret" not in caplog.text
    assert "Referenz je 100 g" not in caplog.text


def test_changed_case_binding_cannot_resume():
    from dataclasses import replace

    async def run():
        config, store = approval(), MemoryCAS()
        _, cases = load_cases()
        control = make_coordinator(store, config)
        await RunState(store, control, config, cases).initialize()
        cases[0] = (cases[0][0], replace(cases[0][1], max_output_tokens=1999))
        with pytest.raises(PilotError):
            await RunState(store, control, config, cases).claim()
    asyncio.run(run())


def test_infrastructure_is_isolated_keyless_and_pinned():
    template = json.loads((Path(__file__).resolve().parents[2] / "infra/benchmark/main.json").read_text())
    assert template["parameters"]["manifestSha256"]["allowedValues"] == [MANIFEST_HASH]
    resources = template["resources"][1]["properties"]["template"]["resources"]
    indexed = {resource["type"]: resource for resource in resources}
    assert set(indexed) == {"Microsoft.CognitiveServices/accounts", "Microsoft.CognitiveServices/accounts/deployments",
                            "Microsoft.Storage/storageAccounts", "Microsoft.Storage/storageAccounts/tableServices",
                            "Microsoft.Storage/storageAccounts/tableServices/tables", "Microsoft.Authorization/roleAssignments"}
    model = indexed["Microsoft.CognitiveServices/accounts/deployments"]
    assert model["sku"]["name"] == GPT_54_MINI.sku
    assert model["properties"]["model"]["version"] == GPT_54_MINI.version
    assert model["properties"]["versionUpgradeOption"] == "NoAutoUpgrade"
    for resource_type in ("Microsoft.CognitiveServices/accounts", "Microsoft.Storage/storageAccounts"):
        properties = indexed[resource_type]["properties"]
        assert properties["networkAcls"]["defaultAction"] == "Deny"
        assert properties["networkAcls"]["bypass"] == "None"
    assert indexed["Microsoft.CognitiveServices/accounts"]["properties"]["disableLocalAuth"] is True
    assert indexed["Microsoft.Storage/storageAccounts"]["properties"]["allowSharedKeyAccess"] is False


@pytest.mark.parametrize("unknown", [True, False])
def test_archive_requires_every_consumed_operation_reconciled(unknown):
    from app.benchmark_infra import validate_archive
    run = {"state": "closed"}
    ledger = {"benchmark": {"attempts": 1}, "active": {}}
    records = [{"key": "op-one", "data": {"state": "unknown" if unknown else "succeeded",
                                          "settled": True, "usage_known": not unknown}}]
    if unknown:
        with pytest.raises(PilotError):
            validate_archive(run, ledger, records)
    else:
        validate_archive(run, ledger, records)
    with pytest.raises(PilotError):
        validate_archive(run, ledger, [])
    with pytest.raises(PilotError):
        validate_archive({"state": "closed", "initialized": True}, None, [])
    with pytest.raises(PilotError):
        validate_archive(run, None, [{"key": "case-T1", "data": {"state": "started"}}])


def test_infrastructure_plan_is_offline_and_requires_confirmation(monkeypatch, tmp_path, capsys):
    import sys
    from app import benchmark_infra
    config_file = tmp_path / "approval.json"
    config_file.write_text(approval().model_dump_json())
    monkeypatch.setattr(benchmark_infra, "az", lambda *args: pytest.fail("No Azure command permitted"))
    monkeypatch.setattr(sys, "argv", ["benchmark_infra", "plan", "--approval", str(config_file)])
    benchmark_infra.main()
    plan = json.loads(capsys.readouterr().out)
    assert len(plan["confirmation"]) == 64
    monkeypatch.setattr(sys, "argv", ["benchmark_infra", "provision", "--approval", str(config_file)])
    with pytest.raises(SystemExit) as stopped:
        benchmark_infra.main()
    assert stopped.value.code == 1


def test_18_cases_across_restarts_and_missing_results(monkeypatch, tmp_path):
    import httpx2
    from app import benchmark
    from app.providers.openai_api import AzureOpenAIProvider
    from tests.test_openai_api import _food_data, _profile_completion

    clock = [time.time()]
    config = approval().model_copy(update={"expires_at": int(clock[0]) + 86400})
    monkeypatch.setattr(benchmark.time, "time", lambda: clock[0])
    monkeypatch.setenv("APP_ENV", "development")
    monkeypatch.setenv("AI_PILOT_ENABLED", "true")
    calls = []

    def handler(request):
        calls.append(request)
        return httpx2.Response(200, json=_profile_completion(_food_data()))

    async def token():
        return "synthetic"

    async def run():
        store = MemoryCAS()
        _, cases = load_cases()
        control = make_coordinator(store, config)
        control.clock = lambda: clock[0]
        await RunState(store, control, config, cases).initialize()
        identifiers = [(await store.read("case-" + case["id"]))[0]["operation"] for case, _ in cases]
        assert len(set(identifiers)) == 18
        provider = AzureOpenAIProvider(endpoint="https://pftbenchoffline.openai.azure.com", token_provider=token,
                                       dispatch_guard=lambda: None, model_routes=control.routes, prices=control.prices,
                                       profile_bindings=control.profile_bindings, transport=httpx2.MockTransport(handler))
        try:
            for index in range(18):
                state = RunState(store, control, config, cases)
                if index:
                    with pytest.raises(PilotError):
                        await run_one(state, provider, {}, tmp_path / "lost-results")
                result = await run_one(state, provider, {}, tmp_path / "results")
                assert result["operation_id"] == identifiers[index]
                assert result["status"] == "succeeded"
                clock[0] += 61
            with pytest.raises(PilotError):
                await run_one(RunState(store, control, config, cases), provider, {}, tmp_path / "results")
            ledger, _ = await store.read("ledger")
            assert ledger["benchmark"]["attempts"] == 18
            assert ledger["benchmark"]["reserved"] == 4217400000
        finally:
            await provider.aclose()
    asyncio.run(run())
    assert len(calls) == 18


@pytest.mark.parametrize("failure", ["operator", "tenant", "audience", "expiry", "app", "none"])
def test_token_binding(failure):
    import base64
    from azure.core.credentials import AccessToken
    from app.benchmark_azure import token_identity

    config = approval()
    claims = {"oid": str(config.operator_id), "tid": str(config.tenant_id),
              "aud": "https://ai.azure.com", "exp": int(time.time()) + 600,
              "appid": "04b07795-8ddb-461a-bbee-02f9e1bf7b46"}
    fields = {"operator": "oid", "tenant": "tid", "audience": "aud", "app": "appid"}
    if failure in fields:
        claims[fields[failure]] = "other"
    if failure == "expiry":
        claims["exp"] = int(time.time()) - 1
    token = AccessToken("header." + base64.urlsafe_b64encode(json.dumps(claims).encode()).decode() + ".signature",
                        int(time.time()) + 600)
    if failure == "none":
        token_identity(token, config, "https://ai.azure.com/.default")
    else:
        with pytest.raises(PilotError):
            token_identity(token, config, "https://ai.azure.com/.default")


@pytest.mark.parametrize("failure", ["disk", "table"])
def test_result_write_failure_leaves_run_busy(monkeypatch, tmp_path, failure):
    from app import benchmark
    from app.providers.base import GenerationMetadata, StructuredGenerationResult, TokenUsage
    from tests.test_openai_api import _food_data

    class Provider:
        calls = 0

        async def generate(self, request):
            self.calls += 1
            return StructuredGenerationResult(_food_data(), GenerationMetadata(
                "azure_openai", "mini-bench", GPT_54_MINI.price.model, None, 1, "success", TokenUsage(100, 20, 0, 0),
                price_version=GPT_54_MINI.price_version, profile_id=GPT_54_MINI.identifier, service_tier="default"))

    def disk_failure(*args):
        raise OSError("synthetic full disk")

    async def run():
        store, config = MemoryCAS(), approval()
        _, cases = load_cases()
        state = RunState(store, make_coordinator(store, config), config, cases)
        await state.initialize()
        provider = Provider()
        read = store.read

        async def unavailable(key):
            if provider.calls:
                raise PilotError()
            return await read(key)

        if failure == "disk":
            monkeypatch.setattr(benchmark, "write_result", disk_failure)
        else:
            monkeypatch.setattr(store, "read", unavailable)
        with pytest.raises(OSError if failure == "disk" else PilotError):
            await run_one(state, provider, {}, tmp_path / "results")
        if failure == "table":
            record = json.loads((tmp_path / "results/T1.json").read_text())
            assert record["error"] == "ledger_read_failed"
            assert record["charged_usd"] is None
            assert record["reserve_exposure_usd"] == "0.2343"
            assert record["usage"]["input_tokens"] == 100
            monkeypatch.setattr(store, "read", read)
        with pytest.raises(PilotError):
            await RunState(store, state.control, config, cases).claim()
        assert provider.calls == 1
    asyncio.run(run())


def test_stale_preflight_cannot_claim_a_later_case():
    async def run():
        config, store = approval(), MemoryCAS()
        _, cases = load_cases()
        state = RunState(store, make_coordinator(store, config), config, cases)
        await state.initialize()
        run, etag = await store.read("benchmark")
        run["cursor"] = 1
        await store.commit([("benchmark", run, etag)])
        with pytest.raises(PilotError):
            await state.claim(expected_cursor=0)
        record, _ = await store.read("case-T2")
        assert record["state"] == "ready"
    asyncio.run(run())


@pytest.mark.parametrize("outcome", ["success", "price_drift", "missing_meter", "arm_denied"])
def test_full_attestation_http_path_without_azure(monkeypatch, outcome):
    import base64
    import httpx2
    from azure.core.credentials import AccessToken
    from app import benchmark_azure

    config = approval()
    monkeypatch.setenv("APP_ENV", "development")
    monkeypatch.setenv("AI_PILOT_ENABLED", "true")
    monkeypatch.setenv("AZURE_CONFIG_DIR", "/unused-offline")
    calls = []

    class Credential:
        async def get_token(self, scope, **kwargs):
            claims = {"oid": str(config.operator_id), "tid": str(config.tenant_id),
                      "aud": scope.removesuffix("/.default"), "exp": int(time.time()) + 600,
                      "appid": "04b07795-8ddb-461a-bbee-02f9e1bf7b46"}
            return AccessToken("header." + base64.urlsafe_b64encode(json.dumps(claims).encode()).decode() + ".signature",
                               int(time.time()) + 600)

        async def close(self):
            pass

    monkeypatch.setattr(benchmark_azure, "AzureCliCredential", lambda **kwargs: Credential())
    group, account, deployment, storage, inventory = resources(config)
    documents = {config.group_id: group, config.account_id: account,
                 config.account_id + "/deployments/mini-bench": deployment,
                 config.storage_id: storage, config.group_id + "/resources": inventory}
    meters = {"fc81bb98-83fa-569b-a361-70d5904b285d": .825,
              "41b51273-5b41-5b0b-ba4b-3900379c9800": .0825,
              "3167a76c-f4a1-53f1-8784-362e76c0787e": 4.95}

    def handler(request):
        calls.append(request)
        if request.url.host == "management.azure.com":
            return httpx2.Response(403 if outcome == "arm_denied" else 200, json=documents[request.url.path])
        items = [{"meterId": meter, "retailPrice": price, "currencyCode": "USD", "armRegionName": "swedencentral",
                  "unitOfMeasure": "1M", "type": "Consumption", "isPrimaryMeterRegion": True} for meter, price in meters.items()]
        if outcome == "price_drift":
            items[0]["retailPrice"] = .83
        if outcome == "missing_meter":
            items.pop()
        return httpx2.Response(200, json={"Items": items, "NextPageLink": None})

    async def run():
        async with benchmark_azure.AzureBenchmark(config) as azure:
            await azure.http.aclose()
            azure.http = httpx2.AsyncClient(transport=httpx2.MockTransport(handler))
            with pytest.raises(PilotError):
                azure.guard()
            if outcome == "success":
                proof = await azure.attest()
                assert proof["model"] == GPT_54_MINI.price.model
                azure.guard()
                azure.attested_at -= 31
                with pytest.raises(PilotError):
                    azure.guard()
            else:
                with pytest.raises(PilotError):
                    await azure.attest()
                with pytest.raises(PilotError):
                    azure.guard()
    asyncio.run(run())
    assert len(calls) == (1 if outcome == "arm_denied" else 6)
    assert all(request.method == "GET" for request in calls)
    assert not any("chat/completions" in str(request.url) for request in calls)
    if outcome != "arm_denied":
        assert "$filter" in calls[-1].url.params
        assert calls[-1].headers.get("Authorization") is None