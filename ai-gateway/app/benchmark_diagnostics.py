"""Bounded benchmark-only failure evidence, without exception text or identifiers."""

import asyncio
from contextlib import contextmanager
from contextvars import ContextVar

from azure.core.exceptions import (
    ClientAuthenticationError, HttpResponseError, ResourceNotFoundError,
    ServiceRequestError, ServiceResponseError,
)
from azure.core.pipeline.policies import AsyncBearerTokenCredentialPolicy
from azure.data.tables.aio import TableClient

from app.pilot import Conflict, Coordinator, PilotError
from app.pilot_table import AzureTableStore


class BenchmarkDiagnosticError(PilotError):
    def __init__(self, category):
        super().__init__()
        allowed = {"credential_acquisition", "credential_claims", "credential_scope", "local_guard",
                   "approval_window", "attestation_stale", "counter_integrity", "counter_io", "counter_limit",
                   "counter_locked", "cas_exhausted", "control_rejected", "table_local_error"}
        self.category = category if category in allowed else "other"


class _FixedBearerTokenPolicy(AsyncBearerTokenCredentialPolicy):
    async def on_challenge(self, request, response):
        return False


class BenchmarkTableClient(TableClient):
    def _configure_policies(self, **kwargs):
        policies = super()._configure_policies(**kwargs)
        positions = [index for index, policy in enumerate(policies)
                     if isinstance(policy, AsyncBearerTokenCredentialPolicy)]
        if len(positions) != 1:
            raise BenchmarkDiagnosticError("credential_scope")
        policies[positions[0]] = _FixedBearerTokenPolicy(self.credential, "https://storage.azure.com/.default")
        return policies


class BenchmarkDiagnostics:
    def __init__(self):
        self._stage = ContextVar("benchmark_diagnostic_stage", default="preflight")
        self.failures = []
        self.failure_count = 0

    @contextmanager
    def phase(self, stage):
        if stage not in {"preflight", "claim", "bound", "admission", "reserve", "mark_dispatched",
                         "provider", "settle", "accounting_read", "finish"}:
            raise ValueError("Unknown benchmark phase")
        token = self._stage.set(stage)
        try:
            yield
        finally:
            self._stage.reset(token)

    def record(self, action, target, error):
        status = None
        if isinstance(error, BenchmarkDiagnosticError):
            category = error.category
        elif isinstance(error, Conflict):
            category = "cas_conflict"
        elif isinstance(error, ClientAuthenticationError):
            category = "credential_acquisition"
        elif isinstance(error, HttpResponseError):
            status = error.status_code
            if type(status) is not int or not 100 <= status <= 599:
                status = None
            category = ("http_auth" if status in {401, 403} else
                        "cas_conflict" if status in {409, 412} else
                        "http_throttled" if status == 429 else
                        "http_service" if status is not None and status >= 500 else "http_other")
        elif isinstance(error, TimeoutError):
            category = "timeout"
        elif isinstance(error, asyncio.CancelledError):
            category = "cancelled_or_deadline"
        elif isinstance(error, (ServiceRequestError, ServiceResponseError, OSError)):
            category = "transport"
        else:
            category = "other"
        action = action if action in {"table_read", "table_commit", "credential", "control"} else "other"
        target = target if target in {"ledger", "operation", "case", "run", "transaction", "storage", "model", "arm"} else "other"
        self.failure_count += 1
        self.failures.append({"stage": self._stage.get(), "action": action, "target": target,
                              "category": category, "http_status": status})
        self.failures = self.failures[-8:]

    def snapshot(self):
        return {"version": 1, "failure_count": self.failure_count,
                "failures": [dict(failure) for failure in self.failures]}


def _target(key):
    return ("ledger" if key == "ledger" else "run" if key == "benchmark" else
            "operation" if key.startswith("op-") else "case" if key.startswith("case-") else "other")


class _ObservedTableClient:
    def __init__(self, client, diagnostics):
        self.client, self.diagnostics = client, diagnostics

    def __getattr__(self, name):
        return getattr(self.client, name)

    async def get_entity(self, partition, key, **kwargs):
        try:
            return await self.client.get_entity(partition, key, **kwargs)
        except ResourceNotFoundError:
            raise
        except (Exception, asyncio.CancelledError) as exc:
            self.diagnostics.record("table_read", _target(key), exc)
            raise

    async def submit_transaction(self, operations, **kwargs):
        targets = {_target(operation[1]["RowKey"]) for operation in operations}
        target = next(iter(targets)) if len(targets) == 1 else "transaction"
        try:
            return await self.client.submit_transaction(operations, **kwargs)
        except (Exception, asyncio.CancelledError) as exc:
            self.diagnostics.record("table_commit", target, exc)
            raise


class BenchmarkTableStore(AzureTableStore):
    def __init__(self, client, partition="pilot-v1", *, diagnostics=None):
        self.diagnostics = diagnostics if diagnostics is not None else BenchmarkDiagnostics()
        super().__init__(_ObservedTableClient(client, self.diagnostics), partition)

    async def read(self, key):
        before = self.diagnostics.failure_count
        try:
            return await super().read(key)
        except PilotError:
            if self.diagnostics.failure_count == before:
                self.diagnostics.record("table_read", _target(key), BenchmarkDiagnosticError("table_local_error"))
            raise

    async def commit(self, changes):
        before = self.diagnostics.failure_count
        try:
            return await super().commit(changes)
        except PilotError:
            if self.diagnostics.failure_count == before:
                self.diagnostics.record("table_commit", "transaction", BenchmarkDiagnosticError("table_local_error"))
            raise


class BenchmarkCoordinator(Coordinator):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.diagnostics = getattr(self.store, "diagnostics", None) or BenchmarkDiagnostics()

    async def _observe(self, stage, method, *args, **kwargs):
        before = self.diagnostics.failure_count
        with self.diagnostics.phase(stage):
            try:
                return await method(*args, **kwargs)
            except Exception:
                added = self.diagnostics.failure_count - before
                recent = self.diagnostics.failures[-added:] if added else []
                if added == 3 and all(item["category"] == "cas_conflict" for item in recent):
                    self.diagnostics.record("control", "ledger", BenchmarkDiagnosticError("cas_exhausted"))
                elif not added:
                    self.diagnostics.record("control", "other", BenchmarkDiagnosticError("control_rejected"))
                raise

    def bound(self, request):
        with self.diagnostics.phase("bound"):
            try:
                return super().bound(request)
            except Exception:
                self.diagnostics.record("control", "other", BenchmarkDiagnosticError("control_rejected"))
                raise

    async def reserve(self, *args, **kwargs):
        return await self._observe("reserve", super().reserve, *args, **kwargs)

    async def mark_dispatched(self, key):
        return await self._observe("mark_dispatched", super().mark_dispatched, key)

    async def settle(self, *args, **kwargs):
        return await self._observe("settle", super().settle, *args, **kwargs)