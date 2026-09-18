"""Opt-in REAL Azure Table test. Requires separately approved existing test table/identity."""

import asyncio
import os
import time
from uuid import uuid4

import pytest

from app.pilot import Coordinator, PilotError
from app.pilot_table import AzureTableStore
from tests.test_pilot import IDENTITY, OTHER, SECRET, coordinator, operation, request

pytestmark = pytest.mark.skipif(os.environ.get("RUN_AZURE_TABLE_INTEGRATION_TESTS") != "1",
                                reason="Real Azure Table integration requires explicit separate authorization")


def test_real_table_two_clients_atomic_reservation_and_duplicate():
    async def run():
        endpoint, table = os.environ["PILOT_TEST_TABLE_ENDPOINT"], os.environ["PILOT_TEST_TABLE_NAME"]
        first_store, second_store = AzureTableStore.connect(endpoint, table), AzureTableStore.connect(endpoint, table)
        partition = "test-" + uuid4().hex
        first_store.partition = second_store.partition = partition
        template = coordinator()
        limits = template.policy.total.model_copy(update={"concurrent": 1})
        policy = template.policy.model_copy(update={"total": limits, "deployment_verified_until": int(time.time()) + 600})
        first = Coordinator(first_store, policy, SECRET, {IDENTITY, OTHER}, template.prices, template.routes)
        second = Coordinator(second_store, policy, SECRET, {IDENTITY, OTHER}, template.prices, template.routes)
        try:
            await first_store.commit([("ledger", first.initial_ledger(), None)])
            identifier = operation()
            results = await asyncio.gather(first.reserve(IDENTITY, identifier, "synthetic-fingerprint", first.bound(request())),
                                           second.reserve(IDENTITY, identifier, "synthetic-fingerprint", second.bound(request())),
                                           return_exceptions=True)
            assert sum(isinstance(result, str) for result in results) == 1
            assert sum(isinstance(result, PilotError) for result in results) == 1
            ledger, _ = await second_store.read("ledger")
            assert len(ledger["active"]) == 1
            assert {entry["count"] for entry in ledger["buckets"].values()} == {1}
            with pytest.raises(PilotError):
                await second.reserve(OTHER, operation(sequence=2), "another", second.bound(request()))
        finally:
            async for entity in first_store.client.query_entities("PartitionKey eq @partition", parameters={"partition": partition}):
                await first_store.client.delete_entity(partition, entity["RowKey"])
            await first_store.close()
            await second_store.close()
    asyncio.run(run())