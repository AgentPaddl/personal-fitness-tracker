"""One explicitly authorized storage-only ledger read. Never retry a started probe."""

import argparse
import asyncio
import hashlib
import json
import logging
from pathlib import Path
import time

from azure.identity.aio import AzureCliCredential

from app.benchmark import Approval, code_hash, sha, write_result
from app.benchmark_azure import CheckedCredential, TableRequestBudget, local_guard
from app.benchmark_continuation import continuation_plan
from app.benchmark_diagnostics import BenchmarkDiagnostics, BenchmarkTableClient, BenchmarkTableStore
from app.pilot import PilotError
from app.pilot_table import _sdk_logger


async def read_once(store, directory, expected_hash, binding):
    directory = Path(directory)
    write_result(directory, "ledger-probe-started.json", {
        "version": 1, "binding": binding, "started_at": int(time.time()),
        "expected_ledger_hash": expected_hash, "max_reads": 1, "retry": False})
    started = time.perf_counter()
    outcome, matches = "failed", False
    try:
        ledger, _ = await store.read("ledger")
        matches = ledger is not None and sha(ledger) == expected_hash
        outcome = "matched" if matches else "missing" if ledger is None else "mismatch"
    except Exception:
        pass
    result = {"version": 1, "binding": binding, "finished_at": int(time.time()),
              "outcome": outcome, "ledger_hash_matches": matches,
              "duration_ms": round((time.perf_counter() - started) * 1000, 3),
              "diagnostics": store.diagnostics.snapshot()}
    write_result(directory, "ledger-probe-result.json", result)
    return result


async def execute(directory):
    local_guard()
    directory = Path(directory)
    if (directory / "ledger-probe-started.json").exists() or (directory / "ledger-probe-result.json").exists():
        raise PilotError()
    proposal = continuation_plan(directory)
    approval = Approval.model_validate_json((directory / "approval.json").read_text())
    records = json.loads((directory / "closed-ledger-snapshot.json").read_text())["records"]
    expected = next(record["data"] for record in records if record["key"] == "ledger")
    counter = TableRequestBudget(approval)
    if hashlib.sha256(counter.filename.read_bytes()).hexdigest() != proposal["table_counter"]["sha256"]:
        raise PilotError()
    for name in ("azure.identity", "azure.identity.aio._internal.decorators", "azure.identity.aio._credentials.azure_cli"):
        logging.getLogger(name).disabled = True
    diagnostics = BenchmarkDiagnostics()
    raw = AzureCliCredential(subscription=str(approval.subscription_id))
    credential = CheckedCredential(raw, approval, ledger_cleanup=True, diagnostics=diagnostics)
    try:
        async with BenchmarkTableClient(
            f"https://{approval.storage_name}.table.core.windows.net", "MiniBenchmark",
            credential=credential, retry_total=0, retry_to_secondary=False, redirect_max=0,
            raw_request_hook=counter, logger=_sdk_logger, logging_enable=False, tracing_enable=False,
            connection_timeout=2, read_timeout=3,
        ) as client:
            store = BenchmarkTableStore(client, partition="benchmark-" + approval.run_id, diagnostics=diagnostics)
            return await read_once(store, directory, sha(expected), sha([proposal, code_hash()]))
    finally:
        await raw.close()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--evidence", required=True)
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    try:
        if not args.apply:
            raise PilotError()
        result = asyncio.run(execute(args.evidence))
        print(json.dumps(result))
        if result["outcome"] != "matched":
            parser.exit(1, "Ledger probe failed; no repeat or continuation permitted.\n")
    except Exception:
        parser.exit(1, "Ledger probe stopped; inspect the private receipt and never repeat a started probe.\n")


if __name__ == "__main__":
    main()