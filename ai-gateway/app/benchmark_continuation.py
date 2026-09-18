"""Offline continuation proposal. No credentials, resource creation or dispatch."""

from dataclasses import asdict
from decimal import Decimal
import hashlib
import json
from pathlib import Path

from app.benchmark import Approval, code_hash, load_cases, make_coordinator, sha
from app.pilot import PilotError, digest
from app.providers.pricing import GPT_54_MINI


PRIORITY = ("P1", "L1", "R1", "P2", "L2", "R2", "P3", "P4", "R3", "R4", "P5", "P6", "T6")


def continuation_plan(directory):
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
    if request_count >= 2500 or units >= 40000:
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