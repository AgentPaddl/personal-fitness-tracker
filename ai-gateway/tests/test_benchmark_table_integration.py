"""Explicitly opted-in real Table transactions; never construct a model provider."""

import asyncio
from dataclasses import asdict
from decimal import Decimal
import os
from pathlib import Path
import time
from uuid import uuid4

import pytest

from app.benchmark import Approval, RunState, load_cases, make_coordinator
from app.benchmark_azure import AzureBenchmark
from app.pilot import Conflict, Coordinator, PilotError, digest
from app.providers.base import GenerationMetadata, TokenUsage
from app.providers.pricing import GPT_54_MINI


pytestmark = pytest.mark.skipif(os.environ.get("RUN_BENCHMARK_TABLE_TESTS") != "1",
                                reason="Requires separate approval for real Table writes, no model calls")


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