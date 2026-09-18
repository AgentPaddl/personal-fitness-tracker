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
                    price_version=GPT_54_MINI.price_version, capacity=10,
                    billing_delay_risk_accepted=True)


def test_operational_budget_requires_risk_acceptance():
    config = approval()
    config.check_window()
    with pytest.raises(PilotError):
        config.model_copy(update={"billing_delay_risk_accepted": False}).check_window()
    with pytest.raises(PilotError):
        config.model_copy(update={"total_budget_eur": "9.00"}).check_window()


def test_table_request_budget_is_durable_and_bound(monkeypatch, tmp_path):
    from types import SimpleNamespace
    from app.benchmark_azure import TableRequestBudget
    monkeypatch.setenv("BENCHMARK_CONTROL_DIR", str(tmp_path / "control"))
    config = approval()
    request = SimpleNamespace(http_request=SimpleNamespace(method="POST", url="https://example.invalid/$batch"))
    first = TableRequestBudget(config)
    first.initialize()
    first(request)
    second = TableRequestBudget(config)
    second.max_units = 100
    with pytest.raises(PilotError):
        second(request)
    with pytest.raises(PilotError):
        TableRequestBudget(config.model_copy(update={"expires_at": config.expires_at + 1}))(request)
    cleanup = TableRequestBudget(config, cleanup=True)
    cleanup(request)
    assert cleanup.filename.read_text().splitlines()[1:] == ["100", "100"]


def test_table_sdk_calls_budget_before_transport(monkeypatch, tmp_path):
    from azure.core.credentials import AzureNamedKeyCredential
    from azure.data.tables.aio import TableClient
    from app.benchmark_azure import TableRequestBudget
    monkeypatch.setenv("BENCHMARK_CONTROL_DIR", str(tmp_path / "control"))
    budget = TableRequestBudget(approval())
    budget.initialize()
    budget.max_units = 0

    async def run():
        async with TableClient("https://offline.table.core.windows.net", "MiniBenchmark",
                               credential=AzureNamedKeyCredential("offline", "c3ludGhldGlj"),
                               retry_total=0, raw_request_hook=budget) as client:
            with pytest.raises(PilotError):
                await client.get_entity("offline", "offline")
    asyncio.run(run())


def test_benchmark_table_preserves_safe_auth_diagnostic(caplog):
    from azure.core.exceptions import HttpResponseError
    from app.benchmark_azure import BenchmarkTableStore
    from app.benchmark_diagnostics import BenchmarkDiagnostics

    class Client:
        async def get_entity(self, *args, **kwargs):
            error = HttpResponseError(message="private-token-and-resource")
            error.status_code = 403
            raise error

    async def run():
        diagnostics = BenchmarkDiagnostics()
        store = BenchmarkTableStore(Client(), diagnostics=diagnostics)
        with pytest.raises(PilotError) as failed:
            await store.read("ledger")
        assert failed.value.code == "pilot_unavailable"
        assert diagnostics.snapshot()["failures"] == [{
            "stage": "preflight", "action": "table_read", "target": "ledger",
            "category": "http_auth", "http_status": 403}]
        assert "private-token-and-resource" not in json.dumps(diagnostics.snapshot())
    asyncio.run(run())
    assert "private-token-and-resource" not in caplog.text


@pytest.mark.parametrize("outcome", ["matched", "mismatch", "missing", "failed", "cancelled"])
def test_ledger_probe_is_once_even_after_failure(tmp_path, outcome):
    from app.benchmark import sha
    from app.benchmark_diagnostics import BenchmarkDiagnosticError, BenchmarkDiagnostics
    from app.benchmark_probe import read_once

    class Store:
        calls = 0
        diagnostics = BenchmarkDiagnostics()

        async def read(self, key):
            self.calls += 1
            assert key == "ledger"
            if outcome == "failed":
                error = BenchmarkDiagnosticError("credential_acquisition")
                self.diagnostics.record("credential", "storage", error)
                raise error
            if outcome == "cancelled":
                raise asyncio.CancelledError()
            return (None if outcome == "missing" else {"closed": outcome == "matched"}), "etag"

    async def run():
        store = Store()
        directory = tmp_path / "probe"
        if outcome == "cancelled":
            with pytest.raises(asyncio.CancelledError):
                await read_once(store, directory, sha({"closed": True}), "binding")
            assert not (directory / "ledger-probe-result.json").exists()
        else:
            result = await read_once(store, directory, sha({"closed": True}), "binding")
            assert result["outcome"] == outcome
            assert result["ledger_hash_matches"] is (outcome == "matched")
            assert json.loads((directory / "ledger-probe-result.json").read_text()) == result
        with pytest.raises(FileExistsError):
            await read_once(store, directory, sha({"closed": True}), "binding")
        assert store.calls == 1
    asyncio.run(run())


def test_ledger_probe_uses_existing_counter_and_storage_only(closed_benchmark_evidence, monkeypatch):
    from app import benchmark_probe

    directory = closed_benchmark_evidence
    control_dir = directory / "control"
    control_dir.chmod(0o700)
    counter_file = control_dir / "offline-table-requests.log"
    counter_file.chmod(0o600)
    original_counter = counter_file.read_bytes()
    monkeypatch.setenv("APP_ENV", "development")
    monkeypatch.setenv("AI_PILOT_ENABLED", "true")
    monkeypatch.setenv("AZURE_CONFIG_DIR", "/unused-offline")
    monkeypatch.setenv("BENCHMARK_CONTROL_DIR", str(control_dir))
    observed = {}

    class Credential:
        def __init__(self, **kwargs):
            observed["credential"] = kwargs

        async def close(self):
            observed["closed"] = True

    class Client:
        def __init__(self, endpoint, table, **kwargs):
            observed.update(endpoint=endpoint, table=table, options=kwargs)

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            pass

    async def read(store, key):
        observed.setdefault("reads", []).append(key)
        observed["partition"] = store.partition
        records = json.loads((directory / "closed-ledger-snapshot.json").read_text())["records"]
        return next(record["data"] for record in records if record["key"] == key), "etag"

    monkeypatch.setattr(benchmark_probe, "AzureCliCredential", Credential)
    monkeypatch.setattr(benchmark_probe, "BenchmarkTableClient", Client)
    monkeypatch.setattr(benchmark_probe.BenchmarkTableStore, "read", read)
    result = asyncio.run(benchmark_probe.execute(directory))
    assert result["outcome"] == "matched"
    assert observed["reads"] == ["ledger"] and observed["closed"] is True
    assert observed["partition"] == "benchmark-offline"
    assert observed["endpoint"] == "https://pftbenchoffline.table.core.windows.net"
    assert observed["table"] == "MiniBenchmark"
    assert observed["credential"] == {"subscription": str(approval().subscription_id)}
    options = observed["options"]
    assert options["credential"].ledger_cleanup is True
    assert options["retry_total"] == options["redirect_max"] == 0
    assert options["retry_to_secondary"] is options["logging_enable"] is options["tracing_enable"] is False
    counter = options["raw_request_hook"]
    assert counter.filename == counter_file and (counter.max_requests, counter.max_units) == (2500, 40000)
    assert counter_file.read_bytes() == original_counter
    with pytest.raises(PilotError):
        asyncio.run(benchmark_probe.execute(directory))
    assert observed["reads"] == ["ledger"]


@pytest.mark.parametrize("failure,category,attempts", [
    ("read403", "http_auth", 0), ("read429", "http_throttled", 0),
    ("read_timeout", "timeout", 0), ("read_payload", "table_local_error", 0),
    ("write503", "http_service", 0), ("cas409", "cas_exhausted", 0),
    ("cas412", "cas_exhausted", 0), ("lost_ack", "transport", 1),
])
def test_benchmark_admission_diagnostics_and_reserves(tmp_path, failure, category, attempts, caplog):
    from azure.core.exceptions import HttpResponseError, ResourceNotFoundError, ServiceResponseError
    from app.benchmark_diagnostics import BenchmarkTableStore

    class Entity(dict):
        pass

    class Client:
        def __init__(self):
            self.memory = MemoryCAS()
            self.injected = False
            self.reserve_writes = 0

        def http_failure(self, status):
            error = HttpResponseError(message="private-resource-and-token")
            error.status_code = status
            return error

        async def get_entity(self, partition, key, **kwargs):
            if key == "ledger" and failure.startswith("read") and not self.injected:
                self.injected = True
                if failure == "read_timeout":
                    raise TimeoutError("private-resource-and-token")
                if failure == "read_payload":
                    return Entity(data="not-json-private-resource-and-token")
                raise self.http_failure(int(failure[-3:]))
            data, etag = await self.memory.read(key)
            if data is None:
                raise ResourceNotFoundError()
            entity = Entity(data=json.dumps(data))
            entity.metadata = {"etag": etag}
            return entity

        async def submit_transaction(self, operations, **kwargs):
            changes = [(item[1]["RowKey"], json.loads(item[1]["data"]),
                        item[2]["etag"] if len(item) > 2 else None) for item in operations]
            reserving = any(data.get("state") == "pending" for _, data, _ in changes)
            if reserving:
                self.reserve_writes += 1
                if failure.startswith("cas") or failure == "write503":
                    raise self.http_failure(int(failure[-3:]))
            await self.memory.commit(changes)
            if reserving and failure == "lost_ack":
                raise ServiceResponseError("private-resource-and-token")

    class Provider:
        calls = 0

        async def generate(self, request):
            self.calls += 1
            raise AssertionError("No provider invocation permitted")

    async def run():
        client, provider, config = Client(), Provider(), approval()
        store = BenchmarkTableStore(client)
        _, cases = load_cases()
        state = RunState(store, make_coordinator(store, config), config, cases)
        await state.initialize()
        result = await run_one(state, provider, {}, tmp_path / "results")
        assert provider.calls == 0
        assert result["status"] == "halted" and result["error"] == "pilot_unavailable"
        assert result["provider_invoked"] is False
        assert result["reserve_exposure_usd"] == "0.2343"
        assert result["diagnostics"]["failures"][-1]["category"] == category
        assert result["diagnostics"]["failures"][-1]["stage"] == "reserve"
        assert client.reserve_writes == (3 if failure.startswith("cas") else 0 if failure.startswith("read") else 1)
        ledger, _ = await client.memory.read("ledger")
        assert ledger["benchmark"]["attempts"] == attempts
        if failure == "lost_ack":
            assert ledger["active"] and result["retained_reserve_usd"] == "0.2343"
        with pytest.raises(PilotError):
            await state.claim()
        assert "private-resource-and-token" not in json.dumps(result)
    asyncio.run(run())
    assert "private-resource-and-token" not in caplog.text


def test_credential_failure_diagnostic_is_bounded_and_private(monkeypatch):
    from app.benchmark_azure import CheckedCredential
    from app.benchmark_diagnostics import BenchmarkDiagnostics
    monkeypatch.setenv("APP_ENV", "development")
    monkeypatch.setenv("AI_PILOT_ENABLED", "true")
    monkeypatch.setenv("AZURE_CONFIG_DIR", "/offline-unused")

    class Credential:
        async def get_token(self, *args, **kwargs):
            raise RuntimeError("private-tenant-token")

    diagnostics = BenchmarkDiagnostics()
    credential = CheckedCredential(Credential(), approval(), diagnostics=diagnostics)

    async def run():
        for _ in range(12):
            with pytest.raises(PilotError):
                await credential.get_token("https://storage.azure.com/.default")
    asyncio.run(run())
    record = diagnostics.snapshot()
    assert record["failure_count"] == 12 and len(record["failures"]) == 8
    assert all(item["category"] == "credential_acquisition" and item["target"] == "storage"
               for item in record["failures"])
    assert "private-tenant-token" not in json.dumps(record)


def test_table_deadline_diagnostic_does_not_hide_cancellation(monkeypatch):
    from app.benchmark_diagnostics import BenchmarkTableStore
    from app import pilot_table

    class Client:
        async def get_entity(self, *args, **kwargs):
            await asyncio.Future()

    timeout = asyncio.timeout
    monkeypatch.setattr(pilot_table.asyncio, "timeout", lambda seconds: timeout(.001))

    async def run():
        store = BenchmarkTableStore(Client())
        with pytest.raises(PilotError):
            await store.read("ledger")
        assert store.diagnostics.snapshot()["failures"][-1]["category"] == "cancelled_or_deadline"
    asyncio.run(run())


def test_benchmark_table_disables_implicit_auth_challenge(monkeypatch, tmp_path):
    from app.benchmark_azure import AzureBenchmark
    monkeypatch.setenv("APP_ENV", "development")
    monkeypatch.setenv("AI_PILOT_ENABLED", "true")
    monkeypatch.setenv("AZURE_CONFIG_DIR", "/offline-unused")
    monkeypatch.setenv("BENCHMARK_CONTROL_DIR", str(tmp_path / "control"))

    async def run():
        async with AzureBenchmark(approval()) as azure:
            azure.attested_at = time.monotonic()
            store = azure.store()
            try:
                policies = [getattr(item, "_policy", item)
                            for item in store.client._client._client._pipeline._impl_policies]
                auth = next(policy for policy in policies if type(policy).__name__ == "_FixedBearerTokenPolicy")
                assert not any(type(policy).__name__ == "AsyncBearerTokenChallengePolicy" for policy in policies)
                assert await auth.on_challenge(None, None) is False
            finally:
                await store.close()
    asyncio.run(run())


@pytest.mark.parametrize("status", [401, 403, 503])
def test_benchmark_sdk_sends_once_and_records_status(tmp_path, monkeypatch, status, caplog):
    from azure.core.credentials import AccessToken
    from azure.core.pipeline.transport import AsyncHttpResponse, AsyncHttpTransport
    from app.benchmark_azure import TableRequestBudget
    from app.benchmark_diagnostics import BenchmarkTableClient, BenchmarkTableStore
    from app.pilot_table import _sdk_logger

    class Credential:
        calls = 0

        async def get_token(self, *args, **kwargs):
            self.calls += 1
            return AccessToken("synthetic-private-token", 2000000000)

    class Response(AsyncHttpResponse):
        def __init__(self, request):
            super().__init__(request, None)
            self.status_code = status
            self.reason = "synthetic-private-diagnostic"
            self.headers = {"Content-Type": "application/json", "WWW-Authenticate":
                            'Bearer authorization_uri="https://login.microsoftonline.com/private-tenant", resource_id="https://storage.azure.com"'}
            self.content_type = "application/json"

        def body(self):
            return b'{"odata.error":{"code":"Synthetic","message":{"value":"synthetic-private-body"}}}'

        async def load_body(self):
            pass

    class Transport(AsyncHttpTransport):
        calls = 0

        async def open(self):
            pass

        async def close(self):
            pass

        async def __aexit__(self, *args):
            await self.close()

        async def send(self, request, **kwargs):
            self.calls += 1
            return Response(request)

    monkeypatch.setenv("BENCHMARK_CONTROL_DIR", str(tmp_path / "control"))
    budget = TableRequestBudget(approval())
    budget.initialize()
    credential, transport = Credential(), Transport()
    caplog.set_level(logging.DEBUG)

    async def run():
        async with BenchmarkTableClient("https://offline.table.core.windows.net", "MiniBenchmark", credential=credential,
                                        transport=transport, retry_total=0, redirect_max=0, raw_request_hook=budget,
                                        logger=_sdk_logger, logging_enable=False, tracing_enable=False) as client:
            store = BenchmarkTableStore(client)
            with pytest.raises(PilotError):
                await store.read("ledger")
            diagnostic = store.diagnostics.snapshot()
            assert diagnostic["failures"][-1]["http_status"] == status
            assert "private" not in json.dumps(diagnostic)
    asyncio.run(run())
    assert credential.calls == transport.calls == 1
    assert budget.filename.read_text().splitlines()[1:] == ["1"]
    assert "synthetic-private" not in caplog.text and "private-tenant" not in caplog.text


@pytest.mark.parametrize("failure", ["missing", "truncated", "permissions", "hardlink", "symlink", "limit", "locked"])
def test_table_budget_never_resets_or_dispatches_invalid_counter(monkeypatch, tmp_path, failure):
    import fcntl
    import os
    from types import SimpleNamespace
    from app.benchmark_azure import TableRequestBudget
    monkeypatch.setenv("BENCHMARK_CONTROL_DIR", str(tmp_path / "control"))
    budget = TableRequestBudget(approval(), cleanup=True)
    budget.initialize()
    with pytest.raises(FileExistsError):
        budget.initialize()
    request = SimpleNamespace(http_request=SimpleNamespace(method="POST", url="https://example.invalid/$batch"))
    lock = None
    if failure == "missing":
        budget.filename.unlink()
    elif failure == "truncated":
        budget.filename.write_text(budget.binding + "\n10")
    elif failure == "permissions":
        budget.filename.chmod(0o644)
    elif failure == "hardlink":
        os.link(budget.filename, tmp_path / "linked")
    elif failure == "symlink":
        original = tmp_path / "original"
        budget.filename.rename(original)
        budget.filename.symlink_to(original)
    elif failure == "limit":
        budget(request)
        budget.max_requests = 1
    elif failure == "locked":
        lock = budget.filename.open("rb")
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    before = budget.filename.read_bytes() if budget.filename.exists() else None
    try:
        with pytest.raises((PilotError, BlockingIOError)):
            budget(request)
        assert (budget.filename.read_bytes() if budget.filename.exists() else None) == before
    finally:
        if lock:
            lock.close()


@pytest.mark.parametrize("failure,category,entries", [
    ("flock", "counter_locked", 0), ("file_sync", "counter_io", 1), ("directory_sync", "counter_io", 1),
])
def test_table_budget_distinguishes_lock_from_sync_failure(monkeypatch, tmp_path, failure, category, entries):
    import errno
    import fcntl
    import os
    import stat
    from types import SimpleNamespace
    from app.benchmark_azure import TableRequestBudget
    from app.benchmark_diagnostics import BenchmarkDiagnosticError

    monkeypatch.setenv("BENCHMARK_CONTROL_DIR", str(tmp_path / "control"))
    budget = TableRequestBudget(approval())
    budget.initialize()
    request = SimpleNamespace(http_request=SimpleNamespace(method="POST", url="https://offline.invalid/$batch"))
    fsync = os.fsync
    flock = fcntl.flock

    def sync(descriptor):
        directory = stat.S_ISDIR(os.fstat(descriptor).st_mode)
        if failure == ("directory_sync" if directory else "file_sync"):
            raise BlockingIOError(errno.EAGAIN, "private-synchronization-error")
        return fsync(descriptor)

    def lock(descriptor, flags):
        if failure == "flock" and flags & fcntl.LOCK_EX:
            raise BlockingIOError(errno.EAGAIN, "private-lock-error")
        return flock(descriptor, flags)

    with monkeypatch.context() as injected:
        injected.setattr(os, "fsync", sync)
        injected.setattr(fcntl, "flock", lock)
        with pytest.raises(BenchmarkDiagnosticError) as caught:
            budget(request)
    assert budget.filename.read_text().splitlines()[1:] == ["100"] * entries
    with budget.filename.open("rb") as unlocked:
        flock(unlocked, fcntl.LOCK_EX | fcntl.LOCK_NB)
    assert caught.value.category == category
    assert "private" not in str(caught.value)


@pytest.mark.parametrize("outcome", ["success", "io_error", "cancelled"])
def test_table_budget_releases_lock_with_duplicate_descriptor(monkeypatch, tmp_path, outcome):
    import fcntl
    import os
    from types import SimpleNamespace
    from app.benchmark_azure import TableRequestBudget

    monkeypatch.setenv("BENCHMARK_CONTROL_DIR", str(tmp_path / "control"))
    budget = TableRequestBudget(approval())
    budget.initialize()
    request = SimpleNamespace(http_request=SimpleNamespace(method="POST", url="https://offline.invalid/$batch"))
    descriptors = []
    fsync = os.fsync

    def duplicated(descriptor):
        if not descriptors:
            descriptors.append(os.dup(descriptor))
            if outcome == "io_error":
                raise OSError("private-sync-error")
            if outcome == "cancelled":
                raise asyncio.CancelledError()
        return fsync(descriptor)

    try:
        with monkeypatch.context() as injected:
            injected.setattr(os, "fsync", duplicated)
            if outcome == "success":
                budget(request)
            else:
                with pytest.raises(asyncio.CancelledError if outcome == "cancelled" else PilotError):
                    budget(request)
        assert budget.filename.read_text().splitlines()[1:] == ["100"]
        with budget.filename.open("rb") as observer:
            fcntl.flock(observer, fcntl.LOCK_EX | fcntl.LOCK_NB)
    finally:
        for descriptor in descriptors:
            os.close(descriptor)


def test_table_budget_partial_append_stops_and_cannot_flush_after_unlock(monkeypatch, tmp_path):
    import fcntl
    import os
    from types import SimpleNamespace
    from app.benchmark_azure import TableRequestBudget
    from app.benchmark_diagnostics import BenchmarkDiagnosticError

    monkeypatch.setenv("BENCHMARK_CONTROL_DIR", str(tmp_path / "control"))
    budget = TableRequestBudget(approval())
    budget.initialize()
    request = SimpleNamespace(http_request=SimpleNamespace(method="POST", url="https://offline.invalid/$batch"))
    fdopen = os.fdopen
    buffers = []

    class Partial:
        def __init__(self, output):
            self.output = output

        def __getattr__(self, name):
            return getattr(self.output, name)

        def __enter__(self):
            return self

        def __exit__(self, *args):
            self.output.close()

        def write(self, data):
            return self.output.write(data[:-1])

    def partial(descriptor, mode, **kwargs):
        buffers.append(kwargs.get("buffering", -1))
        return Partial(fdopen(descriptor, mode, **kwargs))

    with monkeypatch.context() as injected:
        injected.setattr(os, "fdopen", partial)
        with pytest.raises(BenchmarkDiagnosticError):
            budget(request)
    assert buffers == [0]
    assert budget.filename.read_bytes().endswith(b"\n100")
    with pytest.raises(BenchmarkDiagnosticError) as caught:
        budget(request)
    assert caught.value.category == "counter_integrity"
    with budget.filename.open("rb") as observer:
        fcntl.flock(observer, fcntl.LOCK_EX | fcntl.LOCK_NB)


@pytest.mark.parametrize("ending", ["success", "error", "abort"])
def test_table_counter_lock_lifetime_across_processes(monkeypatch, tmp_path, ending):
    import select
    import subprocess
    import sys
    from types import SimpleNamespace
    from app.benchmark_azure import TableRequestBudget
    from app.benchmark_diagnostics import BenchmarkDiagnosticError

    monkeypatch.setenv("BENCHMARK_CONTROL_DIR", str(tmp_path / "control"))
    budget = TableRequestBudget(approval())
    budget.initialize()
    child = subprocess.Popen([sys.executable, "-B", "-c", """
import fcntl, os, sys
descriptor = os.open(sys.argv[1], os.O_RDWR)
fcntl.flock(descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)
print('locked', flush=True)
ending = input()
if ending == 'abort':
    os._exit(2)
if ending == 'error':
    raise RuntimeError('synthetic child failure')
os.close(descriptor)
""", str(budget.filename)], stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    try:
        assert select.select([child.stdout], [], [], 5)[0]
        assert child.stdout.readline().strip() == "locked"
        request = SimpleNamespace(http_request=SimpleNamespace(method="POST", url="https://offline.invalid/$batch"))
        before = budget.filename.read_bytes()
        with pytest.raises(BenchmarkDiagnosticError) as caught:
            budget(request)
        assert caught.value.category == "counter_locked" and budget.filename.read_bytes() == before
        child.communicate(ending + "\n", timeout=5)
        assert child.returncode == {"success": 0, "error": 1, "abort": 2}[ending]
        budget(request)
        assert budget.filename.read_text().splitlines()[1:] == ["100"]
    finally:
        if child.poll() is None:
            child.kill()
        child.communicate(timeout=5)


@pytest.mark.parametrize("scenario", ["sequence18", "cancel_before_reserve", "lost_reserve_ack", "lost_dispatch_ack",
                                      "unknown_dispatch", "lost_settle_ack"])
def test_counter_lifecycle_scenarios_offline(scenario):
    from tests.test_benchmark_table_integration import exercise_counter_scenario

    async def run():
        store = MemoryCAS()
        keys = set()
        result = await exercise_counter_scenario(store, store, approval(), scenario, keys)
        assert len(keys) <= 40
        assert result["operations"] == (18 if scenario == "sequence18" else 0 if scenario == "cancel_before_reserve" else 1)
    asyncio.run(run())


def test_frozen_public_requests_are_complete():
    manifest, cases = load_cases()
    assert len(cases) == manifest["max_attempts"] == 18
    assert sum(bool(request.attachments) for case, request in cases) == 8
    assert all(request.max_output_tokens == 2000 for case, request in cases)


@pytest.fixture
def closed_benchmark_evidence(monkeypatch, tmp_path):
    import hashlib
    from app import benchmark
    from app.providers.base import GenerationMetadata, StructuredGenerationResult, TokenUsage
    from tests.test_openai_api import _food_data

    clock = [time.time()]
    monkeypatch.setattr(benchmark.time, "time", lambda: clock[0])
    config = approval().model_copy(update={"expires_at": int(clock[0]) + 86399})
    directory = tmp_path / "evidence"
    directory.mkdir(mode=0o700)
    (directory / "approval.json").write_text(config.model_dump_json())

    class Provider:
        async def generate(self, request):
            data = {**_food_data(), "protein_grams": 20.2}
            return StructuredGenerationResult(data, GenerationMetadata(
                "azure_openai", "mini-bench", GPT_54_MINI.price.model, None, 1, "success", TokenUsage(100, 20, 0, 0),
                price_version=GPT_54_MINI.price_version, profile_id=GPT_54_MINI.identifier, service_tier="default"))

    async def run():
        store = MemoryCAS()
        _, cases = load_cases()
        control = make_coordinator(store, config)
        control.clock = lambda: clock[0]
        state = RunState(store, control, config, cases)
        await state.initialize()
        for _ in range(4):
            await run_one(state, Provider(), {}, directory / "results" / config.run_id)
            clock[0] += 61

        async def denied(*args, **kwargs):
            raise PilotError()

        monkeypatch.setattr(control, "reserve", denied)
        await run_one(state, Provider(), {}, directory / "results" / config.run_id)
        run, run_etag = await store.read("benchmark")
        ledger, ledger_etag = await store.read("ledger")
        run.update(state="closed", closed_at=int(clock[0]), purge_after=int(clock[0]) + 2678400)
        ledger["blocked"] = True
        await store.commit([("benchmark", run, run_etag), ("ledger", ledger, ledger_etag)])
        records = [{"key": key, "data": data} for key, (data, _) in sorted(store.rows.items())]
        (directory / "closed-ledger-snapshot.json").write_text(json.dumps({"records": records}))
        return state.binding

    binding = asyncio.run(run())
    (directory / "control").mkdir()
    (directory / "control/offline-table-requests.log").write_text(benchmark.sha(config.model_dump(mode="json")) + "\n100\n1\n")
    hashes = {str(filename.relative_to(directory)): hashlib.sha256(filename.read_bytes()).hexdigest()
              for filename in directory.rglob("*") if filename.is_file()}
    (directory / "analysis-baseline.json").write_text(json.dumps({
        "artifact_sha256": hashes, "binding": binding, "code_hash": benchmark.code_hash()}))
    return directory


@pytest.mark.parametrize("scenario", ["success", "claim_race", "adopt_race", "lost_claim_ack", "unknown",
                                      "lost_reserved_ack", "lost_dispatched_ack", "lost_settled_ack", "exhausted"])
def test_parent_cas_preserves_closed_run_and_allowance(closed_benchmark_evidence, scenario, monkeypatch):
    from copy import deepcopy
    from app.benchmark_parent import PARENT_KEY, ParentStore, RESERVE
    from app.providers.base import GenerationMetadata, StructuredGenerationResult, TokenUsage
    from tests.test_openai_api import _food_data

    directory = closed_benchmark_evidence

    class Provider:
        calls = 0

        async def generate(self, request):
            self.calls += 1
            if scenario == "unknown":
                raise TimeoutError()
            return StructuredGenerationResult(_food_data(), GenerationMetadata(
                "azure_openai", "mini-bench", GPT_54_MINI.price.model, None, 1, "success", TokenUsage(100, 20, 0, 0),
                price_version=GPT_54_MINI.price_version, profile_id=GPT_54_MINI.identifier, service_tier="default"))

    async def run():
        base = MemoryCAS()
        records = json.loads((directory / "closed-ledger-snapshot.json").read_text())["records"]
        await base.commit([(record["key"], record["data"], None) for record in records])
        originals = {record["key"]: deepcopy(record["data"]) for record in records}
        first, second = ParentStore(base, directory), ParentStore(base, directory)
        if scenario == "adopt_race":
            outcomes = await asyncio.gather(first.adopt(), second.adopt(), return_exceptions=True)
            assert sum(outcome is None for outcome in outcomes) == 1
            assert sum(isinstance(outcome, Conflict) for outcome in outcomes) == 1
        else:
            await first.adopt()
        with pytest.raises(Conflict):
            await second.adopt()
        clock = [time.time() + 61]
        monkeypatch.setattr(time, "time", lambda: clock[0])
        first.control.clock = second.control.clock = lambda: clock[0]
        provider = Provider()
        if scenario in {"lost_reserved_ack", "lost_dispatched_ack", "lost_settled_ack"}:
            commit = base.commit
            failed_state = scenario.removeprefix("lost_").removesuffix("_ack")

            async def lost_operation_ack(changes):
                await commit(changes)
                if any(key == PARENT_KEY and data["state"] == failed_state for key, data, _ in changes):
                    raise PilotError()

            monkeypatch.setattr(base, "commit", lost_operation_ack)
        if scenario == "claim_race":
            outcomes = await asyncio.gather(first.state.claim(), second.state.claim(), return_exceptions=True)
            assert sum(isinstance(outcome, tuple) for outcome in outcomes) == 1
        elif scenario == "lost_claim_ack":
            commit = base.commit

            async def lost_ack(changes):
                await commit(changes)
                raise PilotError()

            monkeypatch.setattr(base, "commit", lost_ack)
            with pytest.raises(PilotError):
                await first.state.claim()
            monkeypatch.setattr(base, "commit", commit)
        elif scenario != "adopt_race":
            for _ in range(13 if scenario == "exhausted" else 1):
                first = ParentStore(base, directory)
                first.control.clock = lambda: clock[0]
                result = await run_one(first.state, provider, {}, directory / "continuation-results")
                assert result["status"] == ("succeeded" if scenario in {"success", "exhausted"} else "halted")
                clock[0] += 61
            assert provider.calls == (0 if scenario in {"lost_reserved_ack", "lost_dispatched_ack"}
                                      else 13 if scenario == "exhausted" else 1)
        parent, _ = await base.read(PARENT_KEY)
        assert parent["slots"] == (5 if scenario == "adopt_race" else 18 if scenario == "exhausted" else 6)
        assert parent["technical_reserved"] == parent["slots"] * RESERVE
        assert parent["unknown_reserve"] == (RESERVE if scenario in {"success", "adopt_race", "exhausted", "lost_settled_ack"}
                                             else 2 * RESERVE)
        if scenario not in {"success", "adopt_race"}:
            with pytest.raises(PilotError):
                await ParentStore(base, directory).state.claim()
        if scenario == "exhausted":
            clock[0] += 40 * 86400
            assert (await second.parent())[0]["technical_reserved"] == 4217400000
            with pytest.raises(PilotError):
                await second.state.claim()
        for key, original in originals.items():
            assert (await base.read(key))[0] == original
        closed = await first.close()
        assert closed["state"] == "closed" and closed["slots"] == parent["slots"]
        with pytest.raises(PilotError):
            await second.parent()
    asyncio.run(run())


@pytest.fixture
def closed_continuation_evidence(closed_benchmark_evidence, monkeypatch):
    from app.benchmark import code_hash
    from app.benchmark_parent import ParentStore
    from app.providers.base import GenerationMetadata, StructuredGenerationResult, TokenUsage
    from tests.test_openai_api import _food_data

    directory = closed_benchmark_evidence
    clock = [time.time() + 61]
    monkeypatch.setattr(time, "time", lambda: clock[0])

    class Provider:
        async def generate(self, request):
            return StructuredGenerationResult(_food_data(), GenerationMetadata(
                "azure_openai", "mini-bench", GPT_54_MINI.price.model, None, 1, "success", TokenUsage(100, 20, 0, 0),
                price_version=GPT_54_MINI.price_version, profile_id=GPT_54_MINI.identifier, service_tier="default"))

    async def run():
        base = MemoryCAS()
        records = json.loads((directory / "closed-ledger-snapshot.json").read_text())["records"]
        await base.commit([(record["key"], record["data"], None) for record in records])
        parent = ParentStore(base, directory)
        await parent.adopt()
        parent.control.clock = lambda: clock[0]
        for _ in range(5):
            clock[0] += 61
            await run_one(parent.state, Provider(), {}, directory / "continuation-results")
        await parent.close()
        return [{"key": key, "data": data} for key, (data, _) in sorted(base.rows.items())]

    (directory / "continuation-closed-snapshot.json").write_text(json.dumps({"records": asyncio.run(run())}))
    (directory / "continuation-cost-review.json").write_text(json.dumps({"code_hash": code_hash()}))
    return directory


@pytest.mark.parametrize("mutation", ["none", "r2_started", "hold", "open_run", "cost", "result", "code"])
def test_final_plan_preserves_two_closed_runs_and_holds(closed_continuation_evidence, mutation):
    from decimal import Decimal
    from app.benchmark_continuation import final_continuation_plan

    directory = closed_continuation_evidence
    filename = directory / "continuation-closed-snapshot.json"
    archive = json.loads(filename.read_text())
    rows = {record["key"]: record["data"] for record in archive["records"]}
    if mutation == "r2_started":
        rows["continuation-v1-case-R2"]["state"] = "started"
    elif mutation == "hold":
        rows["continuation-parent-v1"]["unknown_reserve"] = 0
    elif mutation == "open_run":
        rows["continuation-v1-benchmark"]["state"] = "idle"
    elif mutation == "cost":
        rows["continuation-parent-v1"]["known_cost"] = 0
    elif mutation == "result":
        (directory / "continuation-results/L2.json").write_text("{}")
    elif mutation == "code":
        (directory / "continuation-cost-review.json").write_text(json.dumps({"code_hash": "changed"}))
    filename.write_text(json.dumps(archive))
    if mutation != "none":
        with pytest.raises(PilotError):
            final_continuation_plan(directory)
        return
    plan = final_continuation_plan(directory)
    assert [item["case_id"] for item in plan["queue"]] == ["P3", "P4", "R3", "R4", "P5", "P6", "T6"]
    assert plan["aggregate"]["consumed_case_slots"] == 11
    assert plan["aggregate"]["max_additional_cases"] == 7
    assert plan["aggregate"]["technical_reserve_usd"] == "2.5773"
    assert plan["aggregate"]["t5_held_reserve_usd"] == plan["aggregate"]["r2_held_reserve_usd"] == "0.2343"
    assert Decimal(plan["aggregate"]["full_projection_eur"]) < Decimal("10")
    assert plan["both_prior_runs_must_remain_closed"] is True and plan["execution_authorized"] is False


@pytest.mark.parametrize("scenario", ["seven", "adopt_race", "claim_race", "unknown", "lost_adopt_ack", "old_changed"])
def test_final_parent_cumulative_cas(closed_continuation_evidence, monkeypatch, scenario):
    from copy import deepcopy
    from app.benchmark_parent import FinalParentStore, ParentStore, RESERVE
    from app.providers.base import GenerationMetadata, StructuredGenerationResult, TokenUsage
    from tests.test_openai_api import _food_data

    directory = closed_continuation_evidence
    clock = [time.time() + 61]
    monkeypatch.setattr(time, "time", lambda: clock[0])

    class Provider:
        calls = 0

        async def generate(self, request):
            self.calls += 1
            if scenario == "unknown":
                raise TimeoutError()
            return StructuredGenerationResult(_food_data(), GenerationMetadata(
                "azure_openai", "mini-bench", GPT_54_MINI.price.model, None, 1, "success", TokenUsage(100, 20, 0, 0),
                price_version=GPT_54_MINI.price_version, profile_id=GPT_54_MINI.identifier, service_tier="default"))

    async def run():
        base = MemoryCAS()
        records = json.loads((directory / "continuation-closed-snapshot.json").read_text())["records"]
        await base.commit([(record["key"], record["data"], None) for record in records])
        original = deepcopy(base.rows)
        first, second = FinalParentStore(base, directory), FinalParentStore(base, directory)
        if scenario == "old_changed":
            ledger, etag = await base.read("ledger")
            ledger["last_time"] += 1
            await base.commit([("ledger", ledger, etag)])
            with pytest.raises(PilotError):
                await first.adopt()
            assert (await base.read(first.parent_key))[0] is None
            return
        if scenario == "adopt_race":
            outcomes = await asyncio.gather(first.adopt(), second.adopt(), return_exceptions=True)
            assert sum(outcome is None for outcome in outcomes) == 1
            assert sum(isinstance(outcome, Conflict) for outcome in outcomes) == 1
        elif scenario == "lost_adopt_ack":
            commit = base.commit

            async def lost_ack(changes):
                await commit(changes)
                raise PilotError()

            with monkeypatch.context() as injected:
                injected.setattr(base, "commit", lost_ack)
                with pytest.raises(PilotError):
                    await first.adopt()
        else:
            await first.adopt()
        with pytest.raises(Conflict):
            await second.adopt()
        with pytest.raises(PilotError):
            await ParentStore(base, directory).parent()
        if scenario == "claim_race":
            outcomes = await asyncio.gather(first.state.claim(), second.state.claim(), return_exceptions=True)
            assert sum(isinstance(outcome, tuple) for outcome in outcomes) == 1
            with pytest.raises(PilotError):
                await FinalParentStore(base, directory).state.claim()
        elif scenario in {"seven", "unknown"}:
            provider = Provider()
            for _ in range(7 if scenario == "seven" else 1):
                first = FinalParentStore(base, directory)
                first.control.clock = lambda: clock[0]
                result = await run_one(first.state, provider, {}, directory / "final-results")
                assert result["status"] == ("succeeded" if scenario == "seven" else "halted")
                clock[0] += 61
            assert provider.calls == (7 if scenario == "seven" else 1)
            with pytest.raises(PilotError):
                await second.state.claim()
        parent, _ = await first.parent()
        assert parent["slots"] == (18 if scenario == "seven" else 12 if scenario in {"unknown", "claim_race"} else 11)
        assert parent["technical_reserved"] == parent["slots"] * RESERVE
        assert parent["t5_reserve"] == parent["r2_reserve"] == RESERVE
        assert parent["unknown_reserve"] == (3 if scenario in {"unknown", "claim_race"} else 2) * RESERVE
        for key, (data, _) in original.items():
            assert (await base.read(key))[0] == data
        await first.close()
        with pytest.raises(PilotError):
            await second.parent()
    asyncio.run(run())


def test_final_handoff_scenario_offline(closed_continuation_evidence, monkeypatch):
    from tests.test_benchmark_table_integration import exercise_final_handoff

    instant = time.time() + 61
    monkeypatch.setattr(time, "time", lambda: instant)

    async def run():
        base = MemoryCAS()
        keys = await exercise_final_handoff(base, base, closed_continuation_evidence)
        assert keys == set(base.rows) and len(keys) < 80
    asyncio.run(run())


@pytest.mark.parametrize("mutation", ["none", "stale", "future", "hash", "region", "sku", "buffer", "limit", "billing",
                                      "unit", "missing_storage", "expensive", "model_region", "expired"])
def test_bounded_price_basis(monkeypatch, tmp_path, mutation):
    import hashlib
    from app.benchmark import sha
    from app.benchmark_continuation import bounded_price_evidence

    config = approval()
    instant = time.time()
    monkeypatch.setattr(time, "time", lambda: instant)
    source = {"verified_at": int(instant) - 3600, "model_prices": [
        {"meterId": meter, "armRegionName": "swedencentral", "currencyCode": "USD", "type": "Consumption",
         "unitOfMeasure": "1M", "isPrimaryMeterRegion": True, "retailPrice": price}
        for meter, price in [("fc81bb98-83fa-569b-a361-70d5904b285d", .825),
                            ("41b51273-5b41-5b0b-ba4b-3900379c9800", .0825),
                            ("3167a76c-f4a1-53f1-8784-362e76c0787e", 4.95)]], "table_prices": [
        {"skuName": "Account Encrypted LRS", "armRegionName": "swedencentral", "currencyCode": "EUR",
         "type": "Consumption", "unitOfMeasure": unit, "isPrimaryMeterRegion": True,
         "productName": "Tables", "retailPrice": price} for unit, price in [("10K", .1005), ("1 GB/Month", .0502)]]}
    if mutation in {"stale", "future"}:
        source["verified_at"] = int(instant) + (60 if mutation == "future" else -21601)
    if mutation == "model_region":
        source["model_prices"][0]["armRegionName"] = "different"
    if mutation == "unit":
        source["table_prices"][0]["unitOfMeasure"] = "1M"
    if mutation == "missing_storage":
        source["table_prices"].pop()
    if mutation == "expensive":
        source["table_prices"][0]["retailPrice"] = 1
    source_bytes = json.dumps(source).encode()
    (tmp_path / "continuation-resource-review.json").write_bytes(source_bytes)
    basis = {"source_file": "continuation-resource-review.json", "source_sha256": hashlib.sha256(source_bytes).hexdigest(),
             "source_url": "https://prices.azure.com/api/retail/prices", "approval_hash": sha(config.model_dump(mode="json")),
             "region": "swedencentral", "storage_sku": "Standard_LRS", "model_sku": "DataZoneStandard",
             "tariff_multiplier": "1.10", "max_age_seconds": 21600, "table_unit_limit": 50000,
             "storage_gb_month": "1", "transfer_allowance_eur": "0.50", "booked_billing": "unknown",
             "expires_at": min(source["verified_at"] + 21600, config.expires_at)}
    changes = {"hash": ("source_sha256", "wrong"), "region": ("region", "other"), "sku": ("storage_sku", "Standard_GRS"),
               "buffer": ("tariff_multiplier", "1.00"), "limit": ("table_unit_limit", 60000),
               "billing": ("booked_billing", "0"), "expired": ("expires_at", instant - 1)}
    if mutation in changes:
        key, value = changes[mutation]
        basis[key] = value
    (tmp_path / "final-price-basis.json").write_text(json.dumps(basis))
    if mutation == "none":
        result = bounded_price_evidence(tmp_path, config)
        assert result["ancillary_projection_eur"] == "1.9943460000"
        assert result["mode"] == "last_verified_bounded"
    else:
        with pytest.raises(PilotError):
            bounded_price_evidence(tmp_path, config)


def test_parent_claim_counter_lock_stops_before_provider(closed_benchmark_evidence, monkeypatch):
    from app.benchmark_diagnostics import BenchmarkDiagnosticError
    from app.benchmark_parent import PARENT_KEY, ParentStore, RESERVE

    class Provider:
        calls = 0

        async def generate(self, request):
            self.calls += 1
            raise AssertionError("No provider allowed after rejected claim")

    async def run():
        directory = closed_benchmark_evidence
        base = MemoryCAS()
        records = json.loads((directory / "closed-ledger-snapshot.json").read_text())["records"]
        await base.commit([(record["key"], record["data"], None) for record in records])
        parent = ParentStore(base, directory)
        await parent.adopt()
        instant = time.time() + 61
        monkeypatch.setattr(time, "time", lambda: instant)
        parent.control.clock = lambda: instant
        writes = []

        async def locked(changes):
            writes.append(changes)
            raise BenchmarkDiagnosticError("counter_locked")

        monkeypatch.setattr(base, "commit", locked)
        provider = Provider()
        with pytest.raises(PilotError):
            await run_one(parent.state, provider, {}, directory / "continuation-results")
        assert len(writes) == 1 and provider.calls == 0
        assert not (directory / "continuation-results/P1.json").exists()
        assert (await parent.read("case-P1"))[0]["state"] == "ready"
        summary, _ = await base.read(PARENT_KEY)
        assert summary["slots"] == 5 and summary["unknown_reserve"] == RESERVE
        assert summary["inflight"] is None
    asyncio.run(run())


@pytest.mark.parametrize("mutation", ["adoption_toctou", "request", "new_operation", "new_binding", "reinitialize"])
def test_parent_cas_rejects_changed_authority(closed_benchmark_evidence, mutation, monkeypatch):
    from dataclasses import asdict
    from app.benchmark_parent import PARENT_KEY, ParentStore
    from app.pilot import digest
    from tests.test_pilot import operation

    directory = closed_benchmark_evidence

    async def run():
        base = MemoryCAS()
        records = json.loads((directory / "closed-ledger-snapshot.json").read_text())["records"]
        await base.commit([(record["key"], record["data"], None) for record in records])
        store = ParentStore(base, directory)
        if mutation == "adoption_toctou":
            commit = base.commit

            async def concurrent_write(changes):
                ledger, etag = await base.read("ledger")
                ledger["last_time"] += 1
                await commit([("ledger", ledger, etag)])
                await commit(changes)

            monkeypatch.setattr(base, "commit", concurrent_write)
            with pytest.raises(Conflict):
                await store.adopt()
            assert (await base.read(PARENT_KEY))[0] is None
            return
        await store.adopt()
        instant = time.time() + 61
        monkeypatch.setattr(time, "time", lambda: instant)
        store.control.clock = lambda: instant
        if mutation == "reinitialize":
            with pytest.raises(PilotError):
                await store.state.initialize()
        elif mutation == "new_binding":
            store.binding = "different-child-does-not-mint-credit"
            with pytest.raises(PilotError):
                await store.state.claim()
        else:
            _, request, identifier = await store.state.claim()
            fingerprint = digest(store.control.secret, "request", asdict(request))
            with pytest.raises(PilotError):
                await store.control.reserve(store.approval.identity,
                    operation(instant, 99) if mutation == "new_operation" else identifier,
                    "altered" if mutation == "request" else fingerprint,
                    store.control.bound(request), store.control.admission(request))
            assert (await store.read("ledger"))[0]["benchmark"]["attempts"] == 5
        parent, _ = await base.read(PARENT_KEY)
        assert parent["slots"] == (6 if mutation in {"request", "new_operation"} else 5)
    asyncio.run(run())


@pytest.mark.parametrize("fail_deployment", [False, True])
def test_model_cleanup_attempts_account_even_after_deployment_failure(monkeypatch, fail_deployment):
    from app import benchmark_infra
    calls = []

    def az(*arguments):
        calls.append(arguments)
        if fail_deployment and "deployment" in arguments:
            raise PilotError()

    monkeypatch.setattr(benchmark_infra, "az", az)
    result = benchmark_infra.delete_model(approval())
    assert result == {"deployment_deleted": not fail_deployment, "account_deleted": True}
    assert len(calls) == 2 and "deployment" in calls[0] and "deployment" not in calls[1]
    assert all("delete" in call and approval().account_name in call for call in calls)


def test_cleanup_can_use_reserved_table_headroom(closed_benchmark_evidence):
    from app.benchmark_continuation import continuation_plan
    directory = closed_benchmark_evidence
    with (directory / "control/offline-table-requests.log").open("a") as output:
        output.write("1000\n" * 40)
    with pytest.raises(PilotError):
        continuation_plan(directory)
    assert continuation_plan(directory, cleanup=True)["table_counter"]["units"] == 40101


def test_restore_template_contains_only_isolated_model_resources():
    from app.benchmark_infra import restore_template
    template, parameters = restore_template(approval())
    resources = template["resources"]
    assert [resource["type"] for resource in resources] == ["Microsoft.CognitiveServices/accounts",
        "Microsoft.CognitiveServices/accounts/deployments", "Microsoft.Authorization/roleAssignments"]
    assert resources[0]["properties"]["restore"] is True
    assert resources[0]["properties"]["disableLocalAuth"] is True
    assert resources[0]["properties"]["networkAcls"]["defaultAction"] == "Deny"
    assert resources[1]["sku"]["name"] == "DataZoneStandard"
    assert resources[1]["properties"]["model"]["version"] == "2026-03-17"
    assert "CognitiveServices/accounts" in resources[2]["scope"]
    assert parameters["parameters"]["egressIPv4"]["value"] == approval().egress_ipv4


@pytest.mark.parametrize("mutation", ["none", "code", "budget", "ancillary", "network", "probe", "test", "stale"])
def test_continuation_execution_requires_verified_evidence(closed_benchmark_evidence, mutation):
    from app.benchmark import code_hash
    from app.benchmark_continuation import continuation_plan, execution_evidence
    directory = closed_benchmark_evidence
    proposal = continuation_plan(directory)
    (directory / "ledger-probe-result.json").write_text(json.dumps({"outcome": "failed" if mutation == "probe" else "matched",
                                                                  "ledger_hash_matches": True}))
    for scenario in ("adopt_claim_race", "lost_reserve_ack", "unknown_settlement"):
        (directory / ("parent-table-" + scenario + "-result.json")).write_text(json.dumps({"passed": mutation != "test", "cleaned": True}))
    review = {"code_hash": "changed" if mutation == "code" else code_hash(),
              "verified_at": time.time() - (3601 if mutation == "stale" else 0),
              "parent_approval_hash": proposal["parent_approval_hash"], "billing_delay_risk_accepted": True,
              "booked_billing": "unknown", "storage_verified": True, "model_absent": True,
              "network_verified": mutation != "network", "prices_verified": True,
              "ancillary_projection_eur": "2.01" if mutation == "ancillary" else "1.89486",
              "full_projection_eur": "10.01" if mutation == "budget" else proposal["aggregate"]["full_projection_eur"]}
    (directory / "continuation-cost-review.json").write_text(json.dumps(review))
    if mutation == "none":
        assert execution_evidence(directory)["aggregate"]["max_additional_cases"] == 13
    else:
        with pytest.raises(PilotError):
            execution_evidence(directory)


@pytest.mark.parametrize("mutation", ["none", "result", "counter_truncated", "counter_exhausted", "attempt_reset", "t2_reclassified"])
def test_continuation_plan_carries_parent_limits(closed_benchmark_evidence, mutation):
    import hashlib
    from app.benchmark_continuation import PRIORITY, continuation_plan
    directory = closed_benchmark_evidence
    counter = directory / "control/offline-table-requests.log"
    if mutation == "result":
        (directory / "results/offline/T5.json").write_text("{}")
    elif mutation == "counter_truncated":
        counter.write_text(counter.read_text().splitlines()[0] + "\n")
    elif mutation == "counter_exhausted":
        with counter.open("a") as output:
            output.write("1000\n" * 40)
    elif mutation in {"attempt_reset", "t2_reclassified"}:
        name = "closed-ledger-snapshot.json" if mutation == "attempt_reset" else "results/offline/T2.json"
        filename = directory / name
        data = json.loads(filename.read_text())
        if mutation == "attempt_reset":
            next(record["data"] for record in data["records"] if record["key"] == "ledger")["benchmark"]["attempts"] = 0
        else:
            data["quality"]["arithmetic"]["protein_grams"] = True
        filename.write_text(json.dumps(data))
        baseline_file = directory / "analysis-baseline.json"
        baseline = json.loads(baseline_file.read_text())
        baseline["artifact_sha256"][name] = hashlib.sha256(filename.read_bytes()).hexdigest()
        baseline_file.write_text(json.dumps(baseline))
    if mutation != "none":
        with pytest.raises(PilotError):
            continuation_plan(directory)
        return
    with counter.open("a") as output:
        output.write("1\n")
    plan = continuation_plan(directory)
    assert plan["execution_authorized"] is False and plan["original_run_must_remain_closed"] is True
    assert plan["aggregate"]["consumed_case_slots"] == 5
    assert plan["aggregate"]["max_additional_cases"] == 13
    assert plan["aggregate"]["t5_held_reserve_usd"] == "0.2343"
    assert plan["aggregate"]["total_budget_eur"] == "10.00"
    assert plan["aggregate"]["technical_reserve_usd"] == "1.1715"
    assert [item["case_id"] for item in plan["queue"]] == list(PRIORITY)
    assert len({item["case_id"] for item in plan["queue"]}) == 13
    assert plan["table_counter"]["requests"] == 3


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


@pytest.mark.parametrize("failure", ["admission", "provider"])
def test_result_distinguishes_admission_failure_from_provider_entry(monkeypatch, tmp_path, failure):
    from app import benchmark
    from app.errors import ProviderTimeoutError

    class Provider:
        calls = 0

        async def generate(self, request):
            self.calls += 1
            raise ProviderTimeoutError()

    async def run():
        store, config = MemoryCAS(), approval()
        _, cases = load_cases()
        control = make_coordinator(store, config)
        state = RunState(store, control, config, cases)
        await state.initialize()

        async def denied(*args):
            raise PilotError()

        if failure == "admission":
            monkeypatch.setattr(control, "reserve", denied)
        provider = Provider()
        ticks = iter([10.0, 10.1, 10.2, 10.3])
        monkeypatch.setattr(benchmark.time, "perf_counter", lambda: next(ticks))
        result = await run_one(state, provider, {}, tmp_path / "results")
        assert result["provider_invoked"] is (failure == "provider")
        assert result["failure_stage"] == failure
        assert result["admission_ms"] <= result["total_ms"]
        assert result["status"] == "halted"
        assert result["reserve_exposure_usd"] == "0.2343"
        assert provider.calls == (1 if failure == "provider" else 0)
        ledger, _ = await store.read("ledger")
        assert ledger["benchmark"]["attempts"] == provider.calls
        with pytest.raises(PilotError):
            await state.claim()
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


@pytest.mark.parametrize("finished_without_operation", [False, True])
def test_archive_does_not_infer_no_dispatch_from_missing_operation(finished_without_operation):
    from app.benchmark_infra import validate_archive
    run = {"state": "closed", "initialized": True}
    ledger = {"benchmark": {"attempts": 0}, "active": {}}
    records = [{"key": f"case-{index}", "data": {"state": "ready"}} for index in range(18)]
    if finished_without_operation:
        records[0]["data"]["state"] = "finished"
        with pytest.raises(PilotError):
            validate_archive(run, ledger, records)
    else:
        validate_archive(run, ledger, records)


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
    monkeypatch.setenv("BENCHMARK_CONTROL_DIR", str(tmp_path / "control"))
    monkeypatch.setattr(sys, "argv", ["benchmark_infra", "prepare-control", "--approval", str(config_file),
                                     "--apply", "--confirm", plan["confirmation"]])
    benchmark_infra.main()
    assert (tmp_path / "control/offline-table-requests.log").read_text() == plan["approval_hash"] + "\n"
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


@pytest.mark.parametrize("outcome", ["success", "price_drift", "missing_meter", "arm_denied",
                                     "cached_success", "cached_resource_invalid", "cached_expired", "cached_arm_denied"])
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

    def credential_factory(**kwargs):
        assert kwargs == {"subscription": str(config.subscription_id)}
        return Credential()

    monkeypatch.setattr(benchmark_azure, "AzureCliCredential", credential_factory)
    group, account, deployment, storage, inventory = resources(config)
    cached = outcome.startswith("cached_")
    if outcome == "cached_resource_invalid":
        storage["properties"]["allowSharedKeyAccess"] = True
    if cached:
        from app import benchmark_continuation

        def bounded_prices(directory, checked):
            assert directory == "offline-evidence" and checked == config
            if outcome == "cached_expired":
                raise PilotError()
            return {"mode": "last_verified_bounded", "model_prices": []}

        monkeypatch.setattr(benchmark_continuation, "bounded_price_evidence", bounded_prices)
    documents = {config.group_id: group, config.account_id: account,
                 config.account_id + "/deployments/mini-bench": deployment,
                 config.storage_id: storage, config.group_id + "/resources": inventory}
    meters = {"fc81bb98-83fa-569b-a361-70d5904b285d": .825,
              "41b51273-5b41-5b0b-ba4b-3900379c9800": .0825,
              "3167a76c-f4a1-53f1-8784-362e76c0787e": 4.95}

    def handler(request):
        calls.append(request)
        if request.url.host == "management.azure.com":
            return httpx2.Response(403 if outcome in {"arm_denied", "cached_arm_denied"} else 200, json=documents[request.url.path])
        if cached:
            return httpx2.Response(400, json={"Error": "Invalid OData parameters supplied"})
        items = [{"meterId": meter, "retailPrice": price, "currencyCode": "USD", "armRegionName": "swedencentral",
                  "unitOfMeasure": "1M", "type": "Consumption", "isPrimaryMeterRegion": True} for meter, price in meters.items()]
        if outcome == "price_drift":
            items[0]["retailPrice"] = .83
        if outcome == "missing_meter":
            items.pop()
        return httpx2.Response(200, json={"Items": items, "NextPageLink": None})

    async def run():
        async with benchmark_azure.AzureBenchmark(config, price_evidence="offline-evidence" if cached else None) as azure:
            await azure.http.aclose()
            azure.http = httpx2.AsyncClient(transport=httpx2.MockTransport(handler))
            with pytest.raises(PilotError):
                azure.guard()
            if outcome in {"success", "cached_success"}:
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
    assert len(calls) == (1 if outcome in {"arm_denied", "cached_arm_denied"} else 5 if cached else 6)
    assert all(request.method == "GET" for request in calls)
    assert not any("chat/completions" in str(request.url) for request in calls)
    if cached:
        assert all(request.url.host == "management.azure.com" for request in calls)
    elif outcome != "arm_denied":
        assert "$filter" in calls[-1].url.params
        assert calls[-1].headers.get("Authorization") is None