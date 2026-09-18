"""Offline plan by default; explicit, separately approved Azure create/stop/destroy."""

import argparse
import asyncio
import hashlib
import json
import os
from pathlib import Path
import subprocess
import tempfile
import time

from azure.identity.aio import AzureCliCredential

from app.benchmark import Approval, MANIFEST_HASH, ROOT, sha, write_result
from app.benchmark_diagnostics import BenchmarkTableClient
from app.benchmark_azure import CheckedCredential, TableRequestBudget, local_guard
from app.pilot import PilotError, canonical
from app.pilot_table import AzureTableStore, _sdk_logger


TEMPLATE = ROOT.parent / "infra/benchmark/main.json"
RETENTION = 2678400


def restore_template(approval):
    template = json.loads(TEMPLATE.read_text())["resources"][1]["properties"]["template"]
    template["resources"] = [resource for resource in template["resources"] if (
        resource["type"].startswith("Microsoft.CognitiveServices/accounts")
        or resource["type"] == "Microsoft.Authorization/roleAssignments"
        and "CognitiveServices/accounts" in resource.get("scope", ""))]
    if len(template["resources"]) != 3:
        raise PilotError()
    template["resources"][0]["properties"]["restore"] = True
    parameters = {"accountName": approval.account_name, "storageName": approval.storage_name,
                  "operatorId": str(approval.operator_id), "egressIPv4": approval.egress_ipv4,
                  "capacity": approval.capacity, "tags": {
                      "purpose": "pft-public-benchmark", "benchmarkRun": approval.run_id,
                      "manifestSha256": MANIFEST_HASH, "expiresAt": str(approval.expires_at)}}
    return template, {"parameters": {key: {"value": value} for key, value in parameters.items()}}


def restore_model(approval, directory, *, final_round=False):
    from app.benchmark_continuation import execution_evidence
    execution_evidence(directory, final_round=final_round)
    label = "final-model-restore" if final_round else "model-restore"
    approval.check_window()
    check_identity(approval)
    check_group(approval)
    template, parameters = restore_template(approval)
    write_result(directory, label + "-started.json", {"approval_hash": sha(approval.model_dump(mode="json")),
                 "template_hash": sha(template), "started_at": int(time.time()), "retry": False})
    try:
        with tempfile.TemporaryDirectory(prefix="pft-benchmark-restore-") as temporary:
            template_file, parameters_file = Path(temporary) / "template.json", Path(temporary) / "parameters.json"
            template_file.write_bytes(canonical(template))
            parameters_file.write_bytes(canonical(parameters))
            template_file.chmod(0o600)
            parameters_file.chmod(0o600)
            az("deployment", "group", "create", "--subscription", str(approval.subscription_id),
               "--resource-group", approval.resource_group, "--name", "pft-bench-" + approval.run_id,
               "--template-file", str(template_file), "--parameters", "@" + str(parameters_file))
        write_result(directory, label + "-result.json", {"status": "completed", "finished_at": int(time.time())})
    except BaseException:
        write_result(directory, label + "-result.json", {"status": "unknown", "finished_at": int(time.time())})
        raise


def delete_model(approval):
    deleted = {"deployment_deleted": False, "account_deleted": False}
    for kind in ("deployment", "account"):
        try:
            arguments = ["cognitiveservices", "account"]
            if kind == "deployment":
                arguments += ["deployment"]
            arguments += ["delete", "--subscription", str(approval.subscription_id),
                          "--resource-group", approval.resource_group, "--name", approval.account_name]
            if kind == "deployment":
                arguments += ["--deployment-name", "mini-bench"]
            az(*arguments)
            deleted[kind + "_deleted"] = True
        except Exception:
            pass
    return deleted


def plan(approval):
    parameters = {
        "runId": approval.run_id, "accountName": approval.account_name, "storageName": approval.storage_name,
        "operatorId": str(approval.operator_id), "egressIPv4": approval.egress_ipv4,
        "expiresAt": str(approval.expires_at), "manifestSha256": MANIFEST_HASH, "capacity": approval.capacity,
    }
    return {"approval_hash": sha(approval.model_dump(mode="json")),
            "template_hash": hashlib.sha256(TEMPLATE.read_bytes()).hexdigest(),
            "resource_group": approval.resource_group, "region": "swedencentral",
            "model_reserve_usd": "4.2174", "operational_budget_eur": approval.total_budget_eur,
            "ancillary_reserve_eur": approval.ancillary_reserve_eur,
            "usd_to_eur_reserve": approval.usd_to_eur_reserve,
            "tax_multiplier_reserve": approval.tax_multiplier_reserve,
            "billing_delay_risk_accepted": approval.billing_delay_risk_accepted,
            "parameters": {key: {"value": value} for key, value in parameters.items()}}


def az(*arguments):
    environment = {**os.environ, "AZURE_CORE_COLLECT_TELEMETRY": "no", "AZURE_EXTENSION_USE_DYNAMIC_INSTALL": "no"}
    result = subprocess.run(["az", *arguments, "--only-show-errors", "--output", "json"],
                            env=environment, capture_output=True, text=True, timeout=600, check=False)
    if result.returncode:
        raise PilotError()
    return json.loads(result.stdout) if result.stdout.strip() else None


def check_identity(approval):
    local_guard()
    account = az("account", "show", "--subscription", str(approval.subscription_id))
    principal = az("ad", "signed-in-user", "show", "--query", "id")
    if (account.get("tenantId") != str(approval.tenant_id) or account.get("id") != str(approval.subscription_id)
            or account.get("user", {}).get("type") != "user" or principal != str(approval.operator_id)):
        raise PilotError()


def check_group(approval):
    group = az("group", "show", "--subscription", str(approval.subscription_id), "--name", approval.resource_group)
    expected = {"purpose": "pft-public-benchmark", "benchmarkRun": approval.run_id,
                "manifestSha256": MANIFEST_HASH, "expiresAt": str(approval.expires_at)}
    if (group.get("id", "").lower() != approval.group_id.lower() or group.get("location") != "swedencentral"
            or any(group.get("tags", {}).get(key) != value for key, value in expected.items())):
        raise PilotError()
    resources = az("resource", "list", "--subscription", str(approval.subscription_id), "--resource-group", approval.resource_group)
    prefixes = (approval.account_id.lower(), approval.storage_id.lower())
    deployment_id = (approval.group_id + "/providers/Microsoft.Resources/deployments/pft-bench-" + approval.run_id).lower()
    if any(resource["id"].lower() != deployment_id and not any(
        resource["id"].lower() == prefix or resource["id"].lower().startswith(prefix + "/") for prefix in prefixes
    ) for resource in resources):
        raise PilotError()


async def close_or_archive(approval, archive=None):
    raw = AzureCliCredential(subscription=str(approval.subscription_id))
    credential = CheckedCredential(raw, approval, ledger_cleanup=True)
    client = BenchmarkTableClient(f"https://{approval.storage_name}.table.core.windows.net", "MiniBenchmark",
                         credential=credential, retry_total=0, logging_enable=False, logger=_sdk_logger,
                         raw_request_hook=TableRequestBudget(approval, cleanup=True), retry_to_secondary=False,
                         redirect_max=0,
                         tracing_enable=False, connection_timeout=2, read_timeout=3)
    store = AzureTableStore(client, partition="benchmark-" + approval.run_id)
    try:
        run, run_etag = await store.read("benchmark")
        ledger, ledger_etag = await store.read("ledger")
        if run is None and ledger is None and archive is None:
            run = {"run_id": approval.run_id, "approval_hash": sha(approval.model_dump(mode="json")),
                   "state": "uninitialized", "initialized": False}
        if (not run or run.get("run_id") != approval.run_id
                or run.get("approval_hash") != sha(approval.model_dump(mode="json"))):
            raise PilotError()
        if archive is None:
            run.update(state="closed", closed_at=run.get("closed_at", int(time.time())),
                       purge_after=run.get("purge_after", int(time.time()) + RETENTION))
            changes = [("benchmark", run, run_etag)]
            if ledger:
                ledger["blocked"] = True
                changes.append(("ledger", ledger, ledger_etag))
            await store.commit(changes)
            return
        if run.get("state") != "closed" or time.time() < run.get("purge_after", float("inf")):
            raise PilotError()
        records = []
        async for entity in client.query_entities("PartitionKey eq @partition", parameters={"partition": store.partition}):
            records.append({"key": entity["RowKey"], "data": json.loads(entity["data"])})
        validate_archive(run, ledger, records)
        archive = Path(archive)
        write_result(archive.parent, archive.name, {"approval_hash": run["approval_hash"], "closed_run": approval.run_id,
                                                  "archived_at": int(time.time()), "records": records})
    finally:
        await store.close()
        await raw.close()


def validate_archive(run, ledger, records):
    operations = [record["data"] for record in records if record["key"].startswith("op-")]
    cases = [record["data"] for record in records if record["key"].startswith("case-")]
    attempts = ledger["benchmark"]["attempts"] if ledger else 0
    if (run.get("state") != "closed" or len(operations) != attempts or ledger and ledger.get("active")
            or run.get("initialized") is True and (
                ledger is None or len(cases) != 18
                or sum(record.get("state") == "finished" for record in cases) != attempts)
            or any(record.get("state") not in {"ready", "finished"} for record in cases)
            or any(record.get("state") not in {"succeeded", "failed"} or not record.get("settled")
                   or record.get("usage_known") is not True for record in operations)):
        raise PilotError()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("plan", "prepare-control", "provision", "restore", "stop", "destroy"))
    parser.add_argument("--approval", required=True)
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--confirm")
    parser.add_argument("--archive")
    parser.add_argument("--evidence")
    parser.add_argument("--final-round", action="store_true")
    args = parser.parse_args()
    try:
        approval = Approval.model_validate_json(Path(args.approval).read_text())
        proposed = plan(approval)
        confirmation = sha(proposed)
        if args.command == "plan":
            print(json.dumps({**proposed, "confirmation": confirmation}, indent=2))
            return
        if not args.apply or args.confirm != confirmation:
            raise PilotError()
        if args.command == "prepare-control":
            approval.check_window()
            TableRequestBudget(approval).initialize()
            print("Local Table counter initialized once; no cloud requests made.")
            return
        if args.command == "restore":
            if not args.evidence or Path(args.approval).resolve() != (Path(args.evidence) / "approval.json").resolve():
                raise PilotError()
            restore_model(approval, args.evidence, final_round=args.final_round)
            print("Isolated model restore completed; storage and ledger were not provisioned.")
            return
        check_identity(approval)
        if args.command == "provision":
            approval.check_window()
            if az("group", "exists", "--subscription", str(approval.subscription_id), "--name", approval.resource_group):
                raise PilotError()
            with tempfile.TemporaryDirectory(prefix="pft-benchmark-parameters-") as temporary:
                parameters = Path(temporary) / "parameters.json"
                parameters.write_bytes(canonical({"parameters": proposed["parameters"]}))
                parameters.chmod(0o600)
                az("deployment", "sub", "create", "--subscription", str(approval.subscription_id),
                   "--name", "pft-bench-" + approval.run_id, "--location", "swedencentral",
                   "--template-file", str(TEMPLATE), "--parameters", "@" + str(parameters))
        elif args.command == "stop":
            check_group(approval)
            asyncio.run(close_or_archive(approval))
            az("cognitiveservices", "account", "delete", "--subscription", str(approval.subscription_id),
               "--resource-group", approval.resource_group, "--name", approval.account_name)
        else:
            if not args.archive:
                raise PilotError()
            check_group(approval)
            asyncio.run(close_or_archive(approval, args.archive))
            az("group", "delete", "--subscription", str(approval.subscription_id), "--name", approval.resource_group, "--yes")
        print("Approved benchmark infrastructure operation completed.")
    except (Exception, KeyboardInterrupt):
        parser.exit(1, "Infrastructure operation stopped; inspect Azure state before any manual continuation.\n")


if __name__ == "__main__":
    main()