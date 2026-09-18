"""Cumulative continuation proposal and explicitly gated execution."""

from dataclasses import asdict
from decimal import Decimal
import hashlib
import json
from pathlib import Path
import time

from app.benchmark import Approval, code_hash, load_cases, make_coordinator, sha
from app.pilot import PilotError, digest
from app.providers.pricing import GPT_54_MINI


PRIORITY = ("P1", "L1", "R1", "P2", "L2", "R2", "P3", "P4", "R3", "R4", "P5", "P6", "T6")


def bounded_price_evidence(directory, approval):
    directory = Path(directory)
    basis = json.loads((directory / "final-price-basis.json").read_text())
    source_bytes = (directory / "continuation-resource-review.json").read_bytes()
    source = json.loads(source_bytes)
    if (basis.get("source_file") != "continuation-resource-review.json"
            or basis.get("source_sha256") != hashlib.sha256(source_bytes).hexdigest()
            or basis.get("approval_hash") != sha(approval.model_dump(mode="json"))
            or basis.get("source_url") != "https://prices.azure.com/api/retail/prices"
            or basis.get("region") != "swedencentral" or basis.get("storage_sku") != "Standard_LRS"
            or basis.get("model_sku") != "DataZoneStandard" or basis.get("tariff_multiplier") != "1.10"
            or basis.get("max_age_seconds") != 21600 or basis.get("table_unit_limit") != 50000
            or basis.get("storage_gb_month") != "1" or basis.get("transfer_allowance_eur") != "0.50"
            or basis.get("booked_billing") != "unknown"
            or not 0 <= time.time() - source.get("verified_at", 0) <= 21600
            or basis.get("expires_at") != min(source["verified_at"] + 21600, approval.expires_at)
            or time.time() >= basis["expires_at"]):
        raise PilotError()
    model = source.get("model_prices", [])
    expected = {"fc81bb98-83fa-569b-a361-70d5904b285d": Decimal(".825"),
                "41b51273-5b41-5b0b-ba4b-3900379c9800": Decimal(".0825"),
                "3167a76c-f4a1-53f1-8784-362e76c0787e": Decimal("4.95")}
    if (len(model) != 3 or {item.get("meterId") for item in model} != set(expected)
            or any(item.get("armRegionName") != "swedencentral" or item.get("currencyCode") != "USD"
                or item.get("type") != "Consumption" or item.get("unitOfMeasure") != "1M"
                or item.get("isPrimaryMeterRegion") is not True
                or Decimal(str(item.get("retailPrice"))) != expected[item["meterId"]] for item in model)):
        raise PilotError()
    table = [item for item in source.get("table_prices", []) if item.get("skuName") in {"Standard LRS", "Account Encrypted LRS"}
             and item.get("isPrimaryMeterRegion") is True]
    if (not table or any(item.get("armRegionName") != "swedencentral" or item.get("currencyCode") != "EUR"
            or item.get("type") != "Consumption" or item.get("productName") != "Tables"
            or item.get("unitOfMeasure") not in {"10K", "1 GB/Month"}
            or not Decimal(str(item.get("retailPrice"))).is_finite()
            or Decimal(str(item.get("retailPrice"))) < 0 for item in table)):
        raise PilotError()
    transaction = [Decimal(str(item["retailPrice"])) for item in table if item["unitOfMeasure"] == "10K"]
    storage = [Decimal(str(item["retailPrice"])) for item in table if item["unitOfMeasure"] == "1 GB/Month"]
    if not transaction or not storage:
        raise PilotError()
    ancillary = ((5 * max(transaction) + max(storage)) * Decimal("1.10") + Decimal(".50")) * Decimal("1.50") * Decimal("1.20")
    if ancillary > Decimal(approval.ancillary_reserve_eur):
        raise PilotError()
    return {"mode": "last_verified_bounded", "source_sha256": basis["source_sha256"],
            "source_verified_at": source["verified_at"], "expires_at": basis["expires_at"],
            "tariff_multiplier": "1.10", "ancillary_projection_eur": str(ancillary), "model_prices": model}


def final_continuation_plan(directory, *, cleanup=False):
    directory = Path(directory)
    proposal = continuation_plan(directory, cleanup=cleanup)
    approval = Approval.model_validate_json((directory / "approval.json").read_text())
    frozen_code = json.loads((directory / "continuation-cost-review.json").read_text())["code_hash"]
    content = (directory / "continuation-closed-snapshot.json").read_bytes()
    records = json.loads(content)["records"]
    snapshot = {record["key"]: record["data"] for record in records}
    original = json.loads((directory / "closed-ledger-snapshot.json").read_text())["records"]
    if len(snapshot) != len(records) or any(snapshot.get(record["key"]) != record["data"] for record in original):
        raise PilotError()
    binding = sha(["continuation-v1", proposal["parent_binding"], proposal["parent_result_hashes"],
                   proposal["snapshot_sha256"], frozen_code, proposal["queue"]])
    child_binding = sha([approval.model_dump(mode="json"), frozen_code,
                        [(item["case_id"], item["request_hash"]) for item in proposal["queue"]]])
    parent, run, ledger = (snapshot[key] for key in (
        "continuation-parent-v1", "continuation-v1-benchmark", "continuation-v1-ledger"))
    reserve = GPT_54_MINI.reserve_usd(2000)
    amount = int(reserve * 1_000_000_000)
    control = make_coordinator(None, approval)
    if (parent.get("state") != "closed" or parent.get("binding") != binding or parent.get("slots") != 10
            or parent.get("technical_reserved") != 10 * amount or parent.get("cursor") != 5
            or parent.get("inflight") is not None or parent.get("t5_reserve") != amount
            or parent.get("unknown_reserve") != amount or run.get("state") != "closed"
            or run.get("cursor") != 5 or run.get("binding") != child_binding
            or ledger.get("blocked") is not True or ledger.get("active") or ledger.get("policy") != control.policy_id
            or ledger.get("benchmark") != {"run_id": approval.run_id, "attempts": 10, "reserved": 10 * amount}):
        raise PilotError()
    known = Decimal(proposal["aggregate"]["known_model_cost_usd"])
    result_hashes, operations = {}, set()
    for index, item in enumerate(proposal["queue"]):
        case_id = item["case_id"]
        saved = snapshot["continuation-v1-case-" + case_id]
        if (saved.get("request_hash") != item["request_hash"]
                or saved.get("state") != ("finished" if index < 5 else "ready")):
            raise PilotError()
        if index >= 5:
            continue
        result = json.loads((directory / "continuation-results" / (case_id + ".json")).read_text())
        result_hashes[case_id] = sha(result)
        key = "continuation-v1-op-" + digest(control.secret, "operation", [approval.identity, saved["operation"]])
        operations.add(key)
        operation = snapshot[key]
        if (saved.get("result_hash") != sha(result) or result.get("binding") != child_binding
                or result.get("case_id") != case_id or result.get("operation_id") != saved["operation"]
                or result.get("request_hash") != item["request_hash"] or result.get("run_id") != approval.run_id
                or result.get("status") != "succeeded" or result.get("usage_known") is not True
                or operation.get("state") != "succeeded" or operation.get("settled") is not True
                or operation.get("usage_known") is not True or operation.get("reserved") != amount
                or type(operation.get("charged")) is not int or not 0 <= operation["charged"] <= amount
                or Decimal(result["charged_usd"]) != Decimal(operation["charged"]) / 1_000_000_000):
            raise PilotError()
        known += Decimal(result["charged_usd"])
    if (operations != {key for key in snapshot if key.startswith("continuation-v1-op-")}
            or parent.get("known_cost") != int(known * 1_000_000_000)):
        raise PilotError()
    projection = Decimal(approval.ancillary_reserve_eur) + (known + 9 * reserve) * Decimal("1.10") * (
        Decimal(approval.usd_to_eur_reserve) * Decimal(approval.tax_multiplier_reserve))
    if projection > Decimal(approval.total_budget_eur):
        raise PilotError()
    proposal.update(version=2, queue=proposal["queue"][6:], both_prior_runs_must_remain_closed=True,
                    predecessor_snapshot_sha256=hashlib.sha256(content).hexdigest(),
                    predecessor_binding=binding, predecessor_result_hashes=result_hashes)
    proposal["aggregate"].update(consumed_case_slots=11, confirmed_dispatches=9, uncertain_case_slots=2,
        max_additional_cases=7, known_model_cost_usd=str(known), r2_held_reserve_usd=str(reserve),
        technical_reserve_usd=str(11 * reserve),
        current_projection_eur=str(projection - 7 * reserve * Decimal("1.10") * Decimal("1.20") * Decimal("1.50")),
        full_projection_eur=str(projection))
    return proposal


def execution_evidence(directory, *, final_round=False):
    directory = Path(directory)
    proposal = final_continuation_plan(directory) if final_round else continuation_plan(directory)
    probe = json.loads((directory / "ledger-probe-result.json").read_text())
    if probe.get("outcome") != "matched" or probe.get("ledger_hash_matches") is not True:
        raise PilotError()
    for scenario in ("adopt_claim_race", "lost_reserve_ack", "unknown_settlement"):
        receipt = json.loads((directory / ("parent-table-" + scenario + "-result.json")).read_text())
        if receipt.get("passed") is not True or receipt.get("cleaned") is not True:
            raise PilotError()
    if final_round:
        receipt = json.loads((directory / "final-table-result.json").read_text())
        if receipt.get("passed") is not True or receipt.get("cleaned") is not True or receipt.get("code_hash") != code_hash():
            raise PilotError()
        approval = Approval.model_validate_json((directory / "approval.json").read_text())
        prices = bounded_price_evidence(directory, approval)
    review = json.loads((directory / ("final-cost-review.json" if final_round else "continuation-cost-review.json")).read_text())
    if final_round and (review.get("price_basis_hash") != sha(prices)
                       or review.get("ancillary_projection_eur") != prices["ancillary_projection_eur"]):
        raise PilotError()
    if (review.get("code_hash") != code_hash() or not 0 <= time.time() - review.get("verified_at", 0) < 3600
            or review.get("parent_approval_hash") != proposal["parent_approval_hash"]
            or review.get("billing_delay_risk_accepted") is not True or review.get("booked_billing") != "unknown"
            or review.get("storage_verified") is not True or review.get("model_absent") is not True
            or review.get("network_verified") is not True or not final_round and review.get("prices_verified") is not True
            or Decimal(review["ancillary_projection_eur"]) > Decimal("2.00")
            or Decimal(review["ancillary_projection_eur"]) < 0
            or Decimal(review["full_projection_eur"]) != Decimal(proposal["aggregate"]["full_projection_eur"])
            or Decimal(review["full_projection_eur"]) > Decimal("10.00")):
        raise PilotError()
    return proposal


async def execute_continuation(args):
    from app.benchmark import run_one, write_result
    from app.benchmark_azure import AzureBenchmark
    from app.benchmark_parent import FinalParentStore, ParentStore
    directory = Path(args.evidence)
    final_round = getattr(args, "final_round", False)
    label = "final" if final_round else "continuation"
    if not args.apply:
        raise PilotError()
    if args.command == "continuation-stop":
        await stop_continuation(directory, final_round=final_round)
        return
    execution_evidence(directory, final_round=final_round)
    approval = Approval.model_validate_json((directory / "approval.json").read_text())
    async with AzureBenchmark(approval, price_evidence=directory if final_round else None) as azure:
        await azure.attest()
        base = azure.store()
        try:
            parent = (FinalParentStore if final_round else ParentStore)(base, directory)
            if args.command == "continuation-adopt":
                write_result(directory, label + "-adopt-started.json", {"binding": parent.binding, "retry": False})
                await parent.adopt()
                write_result(directory, label + "-adopt-result.json", {"binding": parent.binding, "status": "completed"})
            else:
                provider = azure.provider(parent.control)
                try:
                    result = await run_one(parent.state, provider, azure.attest, directory / (label + "-results"))
                    print(json.dumps({key: result[key] for key in ("case_id", "status", "provider_ms", "total_ms", "usage_known", "charged_usd")}))
                    if result["status"] != "succeeded":
                        raise PilotError()
                finally:
                    await provider.aclose()
        finally:
            await base.close()


async def stop_continuation(directory, *, final_round=False):
    from azure.identity.aio import AzureCliCredential
    from app.benchmark import write_result
    from app.benchmark_azure import CheckedCredential, TableRequestBudget, local_guard
    from app.benchmark_diagnostics import BenchmarkDiagnostics, BenchmarkTableClient, BenchmarkTableStore
    from app.benchmark_infra import check_group, check_identity, delete_model
    from app.benchmark_parent import FinalParentStore, ParentStore
    from app.pilot_table import _sdk_logger
    import asyncio
    import logging

    directory = Path(directory)
    label = "final" if final_round else "continuation"
    approval = Approval.model_validate_json((directory / "approval.json").read_text())
    local_guard()
    check_identity(approval)
    check_group(approval)
    write_result(directory, label + "-stop-started.json", {"started_at": int(time.time()), "retry": False})
    for name in ("azure.identity", "azure.identity.aio._internal.decorators", "azure.identity.aio._credentials.azure_cli"):
        logging.getLogger(name).disabled = True
    raw = AzureCliCredential(subscription=str(approval.subscription_id))
    diagnostics = BenchmarkDiagnostics()
    credential = CheckedCredential(raw, approval, ledger_cleanup=True, diagnostics=diagnostics)
    closed, snapshot_saved, deleted = False, False, {"deployment_deleted": False, "account_deleted": False}
    try:
        async with BenchmarkTableClient(f"https://{approval.storage_name}.table.core.windows.net", "MiniBenchmark",
                credential=credential, retry_total=0, redirect_max=0, retry_to_secondary=False,
                logging_enable=False, tracing_enable=False, logger=_sdk_logger,
                raw_request_hook=TableRequestBudget(approval, cleanup=True), connection_timeout=2, read_timeout=3) as client:
            base = BenchmarkTableStore(client, partition="benchmark-" + approval.run_id, diagnostics=diagnostics)
            parent = (FinalParentStore if final_round else ParentStore)(base, directory, cleanup=True)
            summary = await parent.close()
            closed = True
            records = []
            async with asyncio.timeout(15):
                async for entity in client.query_entities("PartitionKey eq @partition",
                        parameters={"partition": base.partition}, results_per_page=100):
                    records.append({"key": entity["RowKey"], "data": json.loads(entity["data"])})
                    if len(records) > 80:
                        raise PilotError()
            old = json.loads((directory / ("continuation-closed-snapshot.json" if final_round else "closed-ledger-snapshot.json")).read_text())["records"]
            actual = {record["key"]: record["data"] for record in records}
            if any(actual.get(record["key"]) != record["data"] for record in old):
                raise PilotError()
            write_result(directory, label + "-closed-snapshot.json", {"summary": summary, "records": records})
            snapshot_saved = True
    except Exception:
        pass
    finally:
        await raw.close()
        deleted = delete_model(approval)
        receipt = {"closed": closed, "snapshot_saved": snapshot_saved, **deleted,
                   "finished_at": int(time.time()), "diagnostics": diagnostics.snapshot()}
        write_result(directory, label + "-stop-result.json", receipt)
        print(json.dumps(receipt))
    if not closed or not snapshot_saved or not all(deleted.values()):
        raise PilotError()


def continuation_plan(directory, *, cleanup=False):
    directory = Path(directory)
    approval = Approval.model_validate_json((directory / "approval.json").read_text())
    if not approval.billing_delay_risk_accepted:
        raise PilotError()
    baseline = json.loads((directory / "analysis-baseline.json").read_text())
    counter_name = f"control/{approval.run_id}-table-requests.log"
    required = {"approval.json", "closed-ledger-snapshot.json", counter_name,
                *(f"results/{approval.run_id}/T{index}.json" for index in range(1, 6))}
    if not required <= baseline["artifact_sha256"].keys():
        raise PilotError()
    for name, expected in baseline["artifact_sha256"].items():
        relative = Path(name)
        if relative.is_absolute() or ".." in relative.parts or (directory / relative).stat().st_size > 1_000_000:
            raise PilotError()
        content = (directory / relative).read_bytes()
        if name == counter_name:
            prefix, matched = hashlib.sha256(), False
            for line in content.splitlines(keepends=True):
                prefix.update(line)
                matched = matched or prefix.hexdigest() == expected
            if not matched:
                raise PilotError()
        elif hashlib.sha256(content).hexdigest() != expected:
            raise PilotError()
    records = json.loads((directory / "closed-ledger-snapshot.json").read_text())["records"]
    snapshot = {record["key"]: record["data"] for record in records}
    if len(snapshot) != len(records):
        raise PilotError()
    run, ledger = snapshot["benchmark"], snapshot["ledger"]
    control = make_coordinator(None, approval)
    _, cases = load_cases()
    requests = {case["id"]: sha(asdict(request)) for case, request in cases}
    binding = sha([approval.model_dump(mode="json"), baseline["code_hash"], list(requests.items())])
    if (run.get("state") != "closed" or run.get("cursor") != 5 or run.get("initialized") is not True
            or run.get("binding") != binding or baseline.get("binding") != binding
            or run.get("approval_hash") != sha(approval.model_dump(mode="json"))
            or ledger.get("blocked") is not True or ledger.get("active") or ledger.get("policy") != control.policy_id
            or ledger["benchmark"]["attempts"] != 4 or run.get("run_id") != approval.run_id):
        raise PilotError()
    result_hashes, known_cost, operation_keys = {}, Decimal(0), set()
    for index, (case, request) in enumerate(cases):
        case_id = case["id"]
        saved = snapshot["case-" + case_id]
        if saved.get("request_hash") != requests[case_id] or saved.get("state") != ("finished" if index < 5 else "ready"):
            raise PilotError()
        if index >= 5:
            continue
        result = json.loads((directory / "results" / approval.run_id / f"{case_id}.json").read_text())
        result_hashes[case_id] = sha(result)
        if (result_hashes[case_id] != saved.get("result_hash") or result["binding"] != binding
                or result["request_hash"] != requests[case_id] or result["case_id"] != case_id
                or result["operation_id"] != saved["operation"] or result["run_id"] != approval.run_id):
            raise PilotError()
        if index < 4:
            key = "op-" + digest(control.secret, "operation", [approval.identity, result["operation_id"]])
            operation_keys.add(key)
            operation = snapshot[key]
            if (result.get("usage_known") is not True or result.get("status") != "succeeded"
                    or operation.get("state") != "succeeded" or operation.get("settled") is not True
                    or operation.get("usage_known") is not True or type(operation.get("charged")) is not int
                    or not 0 <= operation["charged"] <= operation["reserved"]
                    or Decimal(result["charged_usd"]) != Decimal(operation["charged"]) / 1_000_000_000):
                raise PilotError()
            known_cost += Decimal(result["charged_usd"])
        elif result.get("status") != "halted" or result.get("error") != "pilot_unavailable":
            raise PilotError()
        if case_id == "T2" and result.get("quality", {}).get("arithmetic", {}).get("protein_grams") is not False:
            raise PilotError()
    if operation_keys != {key for key in snapshot if key.startswith("op-")}:
        raise PilotError()
    if sum(snapshot[key]["reserved"] for key in operation_keys) != ledger["benchmark"]["reserved"]:
        raise PilotError()
    counter = (directory / counter_name).read_bytes()
    lines = counter.decode().splitlines()
    if (not counter.endswith(b"\n") or lines[0] != sha(approval.model_dump(mode="json"))
            or any(line not in {"1", "100", "1000"} for line in lines[1:])):
        raise PilotError()
    request_count, units = len(lines) - 1, sum(map(int, lines[1:]))
    if request_count >= (3000 if cleanup else 2500) or units >= (50000 if cleanup else 40000):
        raise PilotError()
    reserve = GPT_54_MINI.reserve_usd(2000)
    unknown = reserve
    current = (known_cost + unknown) * Decimal(approval.usd_to_eur_reserve) * Decimal(approval.tax_multiplier_reserve)
    current += Decimal(approval.ancillary_reserve_eur)
    projected = current + 13 * reserve * Decimal(approval.usd_to_eur_reserve) * Decimal(approval.tax_multiplier_reserve)
    if projected > Decimal(approval.total_budget_eur) or 18 * reserve > Decimal("4.2174"):
        raise PilotError()
    return {
        "version": 1, "status": "prepared_execution_blocked", "execution_authorized": False,
        "parent_run_id": approval.run_id, "parent_approval_hash": sha(approval.model_dump(mode="json")),
        "parent_binding": binding, "parent_result_hashes": result_hashes,
        "snapshot_sha256": baseline["artifact_sha256"]["closed-ledger-snapshot.json"],
        "prepared_code_hash": code_hash(), "original_run_must_remain_closed": True,
        "aggregate": {"total_budget_eur": approval.total_budget_eur, "max_case_slots": 18,
                      "consumed_case_slots": 5, "confirmed_dispatches": 4, "uncertain_case_slots": 1,
                      "max_additional_cases": 13, "known_model_cost_usd": str(known_cost),
                      "t5_held_reserve_usd": str(unknown), "technical_reserve_usd": str(5 * reserve),
                      "max_technical_reserve_usd": "4.2174", "ancillary_reserve_eur": approval.ancillary_reserve_eur,
                      "current_projection_eur": str(current), "full_projection_eur": str(projected),
                      "booked_billing": "unknown"},
        "table_counter": {"relative_file": counter_name, "sha256": hashlib.sha256(counter).hexdigest(),
                          "requests": request_count, "units": units, "normal_requests_remaining": 2500 - request_count,
                          "normal_units_remaining": 40000 - units, "total_request_limit": 3000, "total_unit_limit": 50000},
        "remaining_resources": ["existing isolated StorageV2 account", "closed MiniBenchmark Table", "existing scoped review roles"],
        "queue": [{"case_id": case_id, "request_hash": requests[case_id]} for case_id in PRIORITY],
        "required_gates": ["separate execution approval under the same parent authorization",
                           "one approved storage-only read probe with original append-only counter",
                           "fresh billing/resource/price/FX/tax and retention reconciliation",
                           "reviewed parent-CAS continuation runner and isolated model provisioning",
                           "one atomic parent reservation per case before any provider permit",
                           "no retry, replay, reset, new allowance or analysis-behavior change"],
    }