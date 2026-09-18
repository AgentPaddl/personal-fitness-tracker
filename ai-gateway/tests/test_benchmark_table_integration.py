"""Explicitly opted-in real Table transactions; never construct a model provider."""

import asyncio
from dataclasses import asdict
from decimal import Decimal
import os
from pathlib import Path
import time
from uuid import uuid4

import pytest

from app.benchmark import Approval, RunState, load_cases, make_coordinator, write_result
from app.benchmark_azure import AzureBenchmark, CheckedCredential, TableRequestBudget
from app.benchmark_diagnostics import BenchmarkDiagnostics, BenchmarkTableClient, BenchmarkTableStore
from app.benchmark_parent import PARENT_KEY, ParentStore, RESERVE
from app.pilot import Conflict, Coordinator, PilotError, digest
from app.pilot_table import _sdk_logger
from app.providers.base import GenerationMetadata, TokenUsage
from app.providers.pricing import GPT_54_MINI
from tests.test_benchmark import closed_benchmark_evidence


pytestmark = pytest.mark.skipif(os.environ.get("RUN_BENCHMARK_TABLE_TESTS") != "1",
                                reason="Requires separate approval for real Table writes, no model calls")


COUNTER_SCENARIOS = ("sequence18", "cancel_before_reserve", "lost_reserve_ack", "lost_dispatch_ack",
                     "unknown_dispatch", "lost_settle_ack")


async def exercise_counter_scenario(first, second, config, scenario, keys):
    from tests.test_pilot import operation

    clock = [time.time()]
    config = config.model_copy(update={"created_at": int(clock[0]) - 1, "expires_at": int(clock[0]) + 3600})
    _, cases = load_cases()

    def coordinator(store):
        control = make_coordinator(store, config)
        control.clock = lambda: clock[0]
        return control

    owner, competitor = coordinator(first), coordinator(second)
    metadata = GenerationMetadata("azure_openai", "mini-bench", GPT_54_MINI.price.model,
        None, 1, "success", TokenUsage(100, 20, 0, 0), price_version=GPT_54_MINI.price_version,
        profile_id=GPT_54_MINI.identifier, service_tier="default")
    if scenario == "sequence18":
        keys.add("ledger")
        await first.commit([("ledger", owner.initial_ledger(), None)])
        ledger, stale = await first.read("ledger")
        await first.commit([("ledger", ledger, stale)])
        with pytest.raises(Conflict):
            await second.commit([("ledger", ledger, stale)])
        request = cases[0][1]
        fingerprint = digest(owner.secret, "request", asdict(request))
        for sequence in range(18):
            identifier = operation(clock[0], sequence + 1)
            key = "op-" + digest(owner.secret, "operation", [config.identity, identifier])
            keys.add(key)
            arguments = (config.identity, identifier, fingerprint, owner.bound(request), owner.admission(request))
            if sequence == 5:
                outcomes = await asyncio.gather(owner.reserve(*arguments), competitor.reserve(*arguments), return_exceptions=True)
                assert sum(isinstance(outcome, str) for outcome in outcomes) == 1
                assert sum(isinstance(outcome, PilotError) for outcome in outcomes) == 1
            else:
                assert await owner.reserve(*arguments) == key
            await competitor.mark_dispatched(key)
            assert await owner.settle(key, "succeeded", metadata) is False
            ledger, _ = await second.read("ledger")
            assert ledger["benchmark"]["attempts"] == sequence + 1 and not ledger["active"]
            assert ledger["benchmark"]["reserved"] == (sequence + 1) * RESERVE
            owner, competitor = coordinator(second), coordinator(first)
            clock[0] += 61
        with pytest.raises(PilotError):
            await owner.reserve(config.identity, operation(clock[0], 19), fingerprint,
                                owner.bound(request), owner.admission(request))
        return {"operations": 18, "settled": 18, "reserved": 18 * RESERVE, "restart_each_operation": True}

    keys.update({"ledger", "benchmark", *("case-" + case["id"] for case, _ in cases)})
    state = RunState(first, owner, config, cases)
    await state.initialize()
    _, request, identifier = await state.claim()
    key = "op-" + digest(owner.secret, "operation", [config.identity, identifier])
    keys.add(key)
    arguments = (config.identity, identifier, digest(owner.secret, "request", asdict(request)),
                 owner.bound(request), owner.admission(request))
    commit = first.commit

    async def interrupted(changes):
        if scenario != "cancel_before_reserve":
            await commit(changes)
        raise asyncio.CancelledError()

    if scenario in {"cancel_before_reserve", "lost_reserve_ack"}:
        first.commit = interrupted
        try:
            with pytest.raises(asyncio.CancelledError):
                await owner.reserve(*arguments)
        finally:
            first.commit = commit
    else:
        await owner.reserve(*arguments)
        if scenario == "lost_dispatch_ack":
            first.commit = interrupted
            try:
                with pytest.raises(asyncio.CancelledError):
                    await owner.mark_dispatched(key)
            finally:
                first.commit = commit
        else:
            await owner.mark_dispatched(key)
            if scenario == "lost_settle_ack":
                first.commit = interrupted
                try:
                    with pytest.raises(asyncio.CancelledError):
                        await owner.settle(key, "succeeded", metadata)
                finally:
                    first.commit = commit
            else:
                await owner.settle(key, "unknown", None)
    restarted = RunState(second, coordinator(second), config, cases)
    with pytest.raises(PilotError):
        await restarted.claim()
    ledger, _ = await second.read("ledger")
    record, _ = await second.read(key)
    attempts = 0 if scenario == "cancel_before_reserve" else 1
    assert ledger["benchmark"]["attempts"] == attempts
    assert ledger["benchmark"]["reserved"] == attempts * RESERVE
    if attempts:
        with pytest.raises(PilotError):
            await restarted.control.reserve(*arguments)
        assert record["state"] == {"lost_reserve_ack": "pending", "lost_dispatch_ack": "unknown",
                                    "unknown_dispatch": "unknown", "lost_settle_ack": "succeeded"}[scenario]
        if scenario != "lost_settle_ack":
            assert key in ledger["active"] and record["reserved"] == RESERVE
        if scenario == "unknown_dispatch":
            assert record["charged"] == RESERVE and record["usage_known"] is False
    else:
        assert record is None and not ledger["active"]
    return {"operations": attempts, "reserved": attempts * RESERVE, "restart_blocked": True,
            "operation_state": record["state"] if record else None}


def test_real_counter_lifecycle(monkeypatch):
    from azure.core import MatchConditions
    from azure.identity.aio import AzureCliCredential
    from app.benchmark import code_hash, sha
    from app.providers.openai_api import AzureOpenAIProvider
    import hashlib
    import json
    import logging

    def forbidden(*args, **kwargs):
        pytest.fail("No model provider or model attestation is permitted")

    monkeypatch.setattr(AzureBenchmark, "provider", forbidden)
    monkeypatch.setattr(AzureBenchmark, "attest", forbidden)
    monkeypatch.setattr(AzureOpenAIProvider, "__init__", forbidden)
    for name in ("azure.identity", "azure.identity.aio._internal.decorators", "azure.identity.aio._credentials.azure_cli"):
        logging.getLogger(name).disabled = True

    async def run():
        config = Approval.model_validate_json(Path(os.environ["BENCHMARK_APPROVAL_FILE"]).read_text())
        evidence = Path(os.environ["BENCHMARK_APPROVAL_FILE"]).parent
        review = json.loads((evidence / "counter-lock-cost-review.json").read_text())
        budget = TableRequestBudget(config)
        before = budget.filename.read_bytes()
        lines = before.decode().splitlines()
        assert review["parent_approval_hash"] == sha(config.model_dump(mode="json"))
        assert review["counter_sha256"] == hashlib.sha256(before).hexdigest()
        assert review["code_hash"] == code_hash()
        assert review["test_sha256"] == hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
        assert 0 <= time.time() - review["verified_at"] < 3600
        assert review["model_calls_permitted"] is False
        assert Decimal(review["projection_eur"]) <= Decimal(config.total_budget_eur)
        budget.max_requests = min(budget.max_requests, len(lines) - 1 + 480)
        budget.max_units = min(budget.max_units, sum(map(int, lines[1:])) + 11980)
        partitions = {scenario: "test-lock-" + uuid4().hex for scenario in COUNTER_SCENARIOS}
        write_result(evidence, "counter-lock-tests-started.json", {"partitions": partitions,
            "max_additional_requests": 480, "max_additional_units": 11980, "model_calls": 0})
        raw = AzureCliCredential(subscription=str(config.subscription_id))
        diagnostics = BenchmarkDiagnostics()
        credential = CheckedCredential(raw, config, ledger_cleanup=True, diagnostics=diagnostics)
        options = dict(credential=credential, retry_total=0, redirect_max=0, retry_to_secondary=False,
            logging_enable=False, tracing_enable=False, logger=_sdk_logger, raw_request_hook=budget,
            connection_timeout=2, read_timeout=3)
        results, cleaned = {}, []
        try:
            async with BenchmarkTableClient(f"https://{config.storage_name}.table.core.windows.net", "MiniBenchmark", **options) as client:
                async with BenchmarkTableClient(f"https://{config.storage_name}.table.core.windows.net", "MiniBenchmark", **options) as another:
                    for scenario, partition in partitions.items():
                        keys = set()
                        first = BenchmarkTableStore(client, partition=partition, diagnostics=diagnostics)
                        second = BenchmarkTableStore(another, partition=partition, diagnostics=diagnostics)
                        try:
                            results[scenario] = await exercise_counter_scenario(first, second, config, scenario, keys)
                        finally:
                            assert len(keys) <= 40
                            deletes = []
                            for key in sorted(keys):
                                data, etag = await second.read(key)
                                if data is not None:
                                    deletes.append(("delete", {"PartitionKey": partition, "RowKey": key},
                                        {"etag": etag, "match_condition": MatchConditions.IfNotModified}))
                            if deletes:
                                await another.submit_transaction(deletes)
                            for key in ("ledger", "benchmark"):
                                assert (await second.read(key))[0] is None
                            cleaned.append(scenario)
        finally:
            await raw.close()
            after = budget.filename.read_bytes()
            assert after.startswith(before)
            weights = list(map(int, after[len(before):].decode().splitlines()))
            receipt = {"results": results, "cleaned": cleaned, "model_calls": 0,
                "requests": len(weights), "units": sum(weights), "diagnostics": diagnostics.snapshot(),
                "passed": len(results) == len(cleaned) == len(COUNTER_SCENARIOS)}
            write_result(evidence, "counter-lock-tests-result.json", receipt)
            print(json.dumps(receipt))
    asyncio.run(run())


async def exercise_final_handoff(first, second, directory, keys=None):
    import json
    from app.benchmark_parent import FinalParentStore

    records = json.loads((directory / "continuation-closed-snapshot.json").read_text())["records"]
    owner, competitor = FinalParentStore(first, directory), FinalParentStore(second, directory)
    keys = set() if keys is None else keys
    keys.update({record["key"] for record in records} | {owner.parent_key, owner.key("ledger"), owner.key("benchmark"),
        *(owner.key("case-" + case["id"]) for case, _ in owner.cases)})
    await first.commit([(record["key"], record["data"], None) for record in records])
    owner.control.clock = competitor.control.clock = lambda: time.time()
    await owner.adopt()
    with pytest.raises(Conflict):
        await competitor.adopt()
    outcomes = await asyncio.gather(owner.state.claim(), competitor.state.claim(), return_exceptions=True)
    claimed = [outcome for outcome in outcomes if isinstance(outcome, tuple)]
    assert len(claimed) == 1 and sum(isinstance(outcome, (Conflict, PilotError)) for outcome in outcomes) == 1
    _, request, identifier = claimed[0]
    keys.add(owner.key("op-" + digest(owner.control.secret, "operation", [owner.approval.identity, identifier])))
    arguments = (owner.approval.identity, identifier, digest(owner.control.secret, "request", asdict(request)),
                 owner.control.bound(request), owner.control.admission(request))
    key = await owner.control.reserve(*arguments)
    await competitor.control.mark_dispatched(key)
    await owner.control.settle(key, "unknown", None)
    restarted = FinalParentStore(second, directory)
    with pytest.raises(PilotError):
        await restarted.state.claim()
    with pytest.raises(PilotError):
        await restarted.control.reserve(*arguments)
    parent, _ = await owner.parent()
    assert parent["slots"] == 12 and parent["technical_reserved"] == 12 * RESERVE
    assert parent["unknown_reserve"] == 3 * RESERVE
    assert parent["r2_reserve"] == parent["t5_reserve"] == RESERVE
    for record in records:
        assert (await second.read(record["key"]))[0] == record["data"]
    await owner.close()
    with pytest.raises(PilotError):
        await restarted.parent()
    return keys


def test_real_final_handoff(monkeypatch):
    import hashlib
    import json
    import logging
    from azure.core import MatchConditions
    from azure.identity.aio import AzureCliCredential
    from app.benchmark import code_hash, sha
    from app.providers.openai_api import AzureOpenAIProvider

    def forbidden(*args, **kwargs):
        pytest.fail("No model allowed during final handoff test")

    monkeypatch.setattr(AzureBenchmark, "attest", forbidden)
    monkeypatch.setattr(AzureOpenAIProvider, "__init__", forbidden)

    async def run():
        config = Approval.model_validate_json(Path(os.environ["BENCHMARK_APPROVAL_FILE"]).read_text())
        directory = Path(os.environ["BENCHMARK_APPROVAL_FILE"]).parent
        review = json.loads((directory / "final-resource-review.json").read_text())
        assert review["code_hash"] == code_hash() and review["parent_approval_hash"] == sha(config.model_dump(mode="json"))
        assert review["test_sha256"] == hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
        assert review["storage_verified"] is True and review["model_absent"] is True
        assert 0 <= time.time() - review["verified_at"] < 3600
        budget = TableRequestBudget(config)
        before = budget.filename.read_bytes()
        weights = list(map(int, before.decode().splitlines()[1:]))
        assert hashlib.sha256(before).hexdigest() == review["counter_sha256"]
        assert sum(weights) + 1400 + 4200 <= budget.max_units
        budget.max_units = sum(weights) + 1400
        budget.max_requests = min(budget.max_requests, len(weights) + 250)
        partition = "test-final-" + uuid4().hex
        write_result(directory, "final-table-started.json", {"partition": partition, "max_units": 1400, "max_requests": 250})
        for name in ("azure.identity", "azure.identity.aio._internal.decorators", "azure.identity.aio._credentials.azure_cli"):
            logging.getLogger(name).disabled = True
        raw = AzureCliCredential(subscription=str(config.subscription_id))
        diagnostics = BenchmarkDiagnostics()
        options = dict(credential=CheckedCredential(raw, config, ledger_cleanup=True, diagnostics=diagnostics),
            retry_total=0, redirect_max=0, retry_to_secondary=False, logging_enable=False, tracing_enable=False,
            logger=_sdk_logger, raw_request_hook=budget, connection_timeout=2, read_timeout=3)
        passed = cleaned = False
        keys = set()
        try:
            async with BenchmarkTableClient(f"https://{config.storage_name}.table.core.windows.net", "MiniBenchmark", **options) as client:
                async with BenchmarkTableClient(f"https://{config.storage_name}.table.core.windows.net", "MiniBenchmark", **options) as another:
                    first = BenchmarkTableStore(client, partition=partition, diagnostics=diagnostics)
                    second = BenchmarkTableStore(another, partition=partition, diagnostics=diagnostics)
                    try:
                        await exercise_final_handoff(first, second, directory, keys)
                        passed = True
                    finally:
                        deletes = []
                        assert len(keys) < 80
                        for key in sorted(keys):
                            data, etag = await second.read(key)
                            if data is not None:
                                deletes.append(("delete", {"PartitionKey": partition, "RowKey": key},
                                    {"etag": etag, "match_condition": MatchConditions.IfNotModified}))
                        if deletes:
                            await another.submit_transaction(deletes)
                        assert (await second.read("final-parent-v1"))[0] is None
                        cleaned = True
        finally:
            await raw.close()
            after = budget.filename.read_bytes()
            assert after.startswith(before)
            added = list(map(int, after[len(before):].decode().splitlines()))
            receipt = {"passed": passed, "cleaned": cleaned, "code_hash": code_hash(), "requests": len(added),
                       "units": sum(added), "model_calls": 0, "diagnostics": diagnostics.snapshot()}
            write_result(directory, "final-table-result.json", receipt)
            print(json.dumps(receipt))
    asyncio.run(run())


@pytest.mark.parametrize("scenario", ["claim_race", "lost_ack", "lifetime_cleanup"])
def test_real_benchmark_table(scenario, monkeypatch):
    def forbidden(*args, **kwargs):
        pytest.fail("Table integration must never construct a model provider")

    monkeypatch.setattr(AzureBenchmark, "provider", forbidden)

    async def run():
        config = Approval.model_validate_json(Path(os.environ["BENCHMARK_APPROVAL_FILE"]).read_text())
        _, cases = load_cases()
        partition = "test-" + uuid4().hex
        async with AzureBenchmark(config) as azure:
            await azure.attest()
            first, second = azure.store(test_partition=partition), azure.store(test_partition=partition)
            try:
                control = make_coordinator(first, config)
                state = RunState(first, control, config, cases)
                await state.initialize()
                another = RunState(second, make_coordinator(second, config), config, cases)
                if scenario == "claim_race":
                    results = await asyncio.gather(state.claim(), another.claim(), return_exceptions=True)
                    assert sum(isinstance(result, tuple) for result in results) == 1
                    assert sum(isinstance(result, (Conflict, PilotError)) for result in results) == 1
                    with pytest.raises(PilotError):
                        await another.claim()
                    with pytest.raises(Conflict):
                        await another.initialize()
                elif scenario == "lost_ack":
                    commit = first.commit

                    async def lost_ack(changes):
                        await commit(changes)
                        raise PilotError()

                    first.commit = lost_ack
                    with pytest.raises(PilotError):
                        await state.claim()
                    with pytest.raises(PilotError):
                        await another.claim()
                    record, _ = await second.read("case-T1")
                    assert record["state"] == "started"
                else:
                    clock = [time.time()]
                    expiry = int(clock[0]) + 86400 * 80
                    policy = control.policy.model_copy(update={
                        "deployment_verified_until": expiry,
                        "benchmark": control.policy.benchmark.model_copy(update={"expires_at": expiry}),
                    })
                    first_control = Coordinator(first, policy, control.secret, control.allowlist, control.prices,
                                                control.routes, clock=lambda: clock[0],
                                                profile_bindings=control.profile_bindings, max_output_tokens=2000)
                    second_control = Coordinator(second, policy, control.secret, control.allowlist, control.prices,
                                                 control.routes, clock=lambda: clock[0],
                                                 profile_bindings=control.profile_bindings, max_output_tokens=2000)
                    ledger, etag = await first.read("ledger")
                    assert ledger["benchmark"]["attempts"] == 0
                    await first.commit([("ledger", first_control.initial_ledger(), etag)])
                    request = cases[0][1]
                    from tests.test_pilot import operation

                    for sequence in range(18):
                        identifier = operation(clock[0], sequence + 1)
                        fingerprint = digest(control.secret, "request", asdict(request))
                        outcomes = await asyncio.gather(
                            first_control.reserve(config.identity, identifier, fingerprint, first_control.bound(request), first_control.admission(request)),
                            second_control.reserve(config.identity, identifier, fingerprint, second_control.bound(request), second_control.admission(request)),
                            return_exceptions=True,
                        )
                        keys = [outcome for outcome in outcomes if isinstance(outcome, str)]
                        assert len(keys) == 1
                        await first_control.mark_dispatched(keys[0])
                        if sequence == 17:
                            await second_control.settle(keys[0], "unknown", None)
                        else:
                            metadata = GenerationMetadata("azure_openai", "mini-bench", GPT_54_MINI.price.model,
                                                          None, 1, "success", TokenUsage(100, 20, 0, 0),
                                                          Decimal("0.0001815"), GPT_54_MINI.price_version,
                                                          GPT_54_MINI.identifier, "default")
                            await second_control.settle(keys[0], "succeeded", metadata)
                        clock[0] += 61 if sequence != 8 else 86400 * 40
                    with pytest.raises(PilotError):
                        await second_control.reserve(config.identity, operation(clock[0], 19), "another",
                                                     second_control.bound(request), second_control.admission(request))
                    await second.cleanup(clock[0] + policy.retention_seconds + 1, policy.retention_seconds)
                    ledger, _ = await first.read("ledger")
                    assert ledger["benchmark"] == {"run_id": config.run_id, "attempts": 18, "reserved": 4217400000}
                    assert ledger["blocked"] is True
            finally:
                async for entity in second.client.query_entities("PartitionKey eq @partition", parameters={"partition": partition}):
                    await second.client.delete_entity(partition, entity["RowKey"])
                await first.close()
                await second.close()
    asyncio.run(run())


@pytest.mark.parametrize("scenario", ["adopt_claim_race", "lost_reserve_ack", "unknown_settlement"])
def test_real_parent_cas(scenario, closed_benchmark_evidence, monkeypatch):
    from azure.core import MatchConditions
    from azure.identity.aio import AzureCliCredential
    import json
    import logging

    def forbidden(*args, **kwargs):
        pytest.fail("Parent integration must never construct a model provider")

    monkeypatch.setattr(AzureBenchmark, "provider", forbidden)
    for name in ("azure.identity", "azure.identity.aio._internal.decorators", "azure.identity.aio._credentials.azure_cli"):
        logging.getLogger(name).disabled = True

    async def run():
        config = Approval.model_validate_json(Path(os.environ["BENCHMARK_APPROVAL_FILE"]).read_text())
        evidence = Path(os.environ["BENCHMARK_APPROVAL_FILE"]).parent
        partition = "test-parent-" + uuid4().hex
        write_result(evidence, "parent-table-" + scenario + "-started.json", {"partition": partition, "scenario": scenario})
        raw = AzureCliCredential(subscription=str(config.subscription_id))
        diagnostics = BenchmarkDiagnostics()
        credential = CheckedCredential(raw, config, ledger_cleanup=True, diagnostics=diagnostics)
        options = dict(credential=credential, retry_total=0, redirect_max=0, retry_to_secondary=False,
                       logging_enable=False, tracing_enable=False, logger=_sdk_logger,
                       raw_request_hook=TableRequestBudget(config), connection_timeout=2, read_timeout=3)
        passed, cleaned = False, False
        try:
            async with BenchmarkTableClient(f"https://{config.storage_name}.table.core.windows.net", "MiniBenchmark", **options) as client:
                async with BenchmarkTableClient(f"https://{config.storage_name}.table.core.windows.net", "MiniBenchmark", **options) as another_client:
                    first = BenchmarkTableStore(client, partition=partition, diagnostics=diagnostics)
                    second = BenchmarkTableStore(another_client, partition=partition, diagnostics=diagnostics)
                    records = json.loads((closed_benchmark_evidence / "closed-ledger-snapshot.json").read_text())["records"]
                    try:
                        await first.commit([(record["key"], record["data"], None) for record in records])
                        owner, competitor = ParentStore(first, closed_benchmark_evidence), ParentStore(second, closed_benchmark_evidence)
                        if scenario == "adopt_claim_race":
                            outcomes = await asyncio.gather(owner.adopt(), competitor.adopt(), return_exceptions=True)
                            assert sum(outcome is None for outcome in outcomes) == 1
                            assert sum(isinstance(outcome, Conflict) for outcome in outcomes) == 1
                        else:
                            await owner.adopt()
                        instant = time.time() + 61
                        monkeypatch.setattr(time, "time", lambda: instant)
                        owner.control.clock = competitor.control.clock = lambda: instant
                        if scenario == "adopt_claim_race":
                            outcomes = await asyncio.gather(owner.state.claim(), competitor.state.claim(), return_exceptions=True)
                            assert sum(isinstance(outcome, tuple) for outcome in outcomes) == 1
                            assert sum(isinstance(outcome, (Conflict, PilotError)) for outcome in outcomes) == 1
                        else:
                            _, request, operation = await owner.state.claim()
                            if scenario == "lost_reserve_ack":
                                commit = first.commit

                                async def lost_ack(changes):
                                    await commit(changes)
                                    raise PilotError()

                                monkeypatch.setattr(first, "commit", lost_ack)
                                with pytest.raises(PilotError):
                                    await owner.control.reserve(owner.approval.identity, operation,
                                        digest(owner.control.secret, "request", asdict(request)), owner.control.bound(request),
                                        owner.control.admission(request))
                                monkeypatch.setattr(first, "commit", commit)
                            else:
                                key = await owner.control.reserve(owner.approval.identity, operation,
                                    digest(owner.control.secret, "request", asdict(request)), owner.control.bound(request),
                                    owner.control.admission(request))
                                await owner.control.mark_dispatched(key)
                                await owner.control.settle(key, "unknown", None)
                        with pytest.raises(PilotError):
                            await ParentStore(second, closed_benchmark_evidence).state.claim()
                        parent, _ = await second.read(PARENT_KEY)
                        assert parent["slots"] == 6 and parent["technical_reserved"] == 6 * RESERVE
                        assert parent["unknown_reserve"] == 2 * RESERVE
                        for record in records:
                            assert (await second.read(record["key"]))[0] == record["data"]
                        passed = True
                    finally:
                        entities = []
                        async with asyncio.timeout(15):
                            async for entity in another_client.query_entities(
                                    "PartitionKey eq @partition", parameters={"partition": partition}, results_per_page=100):
                                entities.append(entity)
                                if len(entities) > 60:
                                    raise PilotError()
                            if entities:
                                await another_client.submit_transaction([
                                    ("delete", {"PartitionKey": partition, "RowKey": entity["RowKey"]},
                                     {"etag": entity.metadata["etag"], "match_condition": MatchConditions.IfNotModified})
                                    for entity in entities])
                            cleaned = True
        finally:
            await raw.close()
            write_result(evidence, "parent-table-" + scenario + "-result.json", {
                "partition": partition, "scenario": scenario, "passed": passed, "cleaned": cleaned,
                "diagnostics": diagnostics.snapshot()})
    asyncio.run(run())