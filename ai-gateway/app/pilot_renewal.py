"""Bounded owner-grant renewal; no admission, ledger writes or gateway updates."""

import asyncio
from copy import deepcopy
from datetime import datetime, timezone
from decimal import Decimal
import hashlib
import json
import logging
import os
import re
import time

import httpx2

from app.pilot import canonical
from app.pilot_release import CHECKS, OWNER_LEDGER_CHECKS, RENEWABLE, configuration_digest, prepare_approval, verify_approval


class RenewalBlocked(Exception):
    pass


def require(condition, reason):
    if not condition:
        raise RenewalBlocked(reason)


def sha(value):
    return hashlib.sha256(canonical(value)).hexdigest()


def resource_projection(kind, resource):
    properties = resource.get("properties", {})
    if kind == "gateway":
        template = deepcopy(properties["template"])
        template.pop("revisionSuffix", None)
        for container in template["containers"]:
            for entry in container["env"]:
                if "secretRef" in entry:
                    entry.pop("value", None)
            container["env"].sort(key=lambda entry: entry["name"])
        configuration = deepcopy(properties["configuration"])
        configuration["secrets"] = sorted([
            {key: entry.get(key) for key in ("name", "keyVaultUrl", "identity")}
            for entry in configuration["secrets"]], key=lambda entry: entry["name"])
        return {"id": resource["id"].lower(), "identity": resource["identity"], "template": template,
                "configuration": configuration, "environment": properties["managedEnvironmentId"]}
    if kind == "roles":
        return sorted((entry["properties"]["scope"].lower(), entry["properties"]["principalId"],
                       entry["properties"]["roleDefinitionId"].lower(), entry["properties"].get("condition") or "")
                      for entry in resource["value"])
    if kind == "model":
        return {"sku": resource["sku"], "model": properties["model"],
                "upgrade": properties["versionUpgradeOption"]}
    if kind == "storage":
        return {key: properties.get(key) for key in ("allowSharedKeyAccess", "allowBlobPublicAccess",
            "minimumTlsVersion", "publicNetworkAccess", "networkAcls", "primaryEndpoints")}
    if kind == "backend":
        return {"identity": resource["identity"], **{key: properties.get(key) for key in
            ("httpsOnly", "functionAppConfig", "lastModifiedTimeUtc", "serverFarmId", "enabledHostNames")}}
    require(kind == "auth", "unknown_resource_kind")
    return properties


def check_gateway(resource, plan):
    containers = resource["properties"]["template"]["containers"]
    require(len(containers) == 1, "container_drift")
    values = {entry["name"]: entry.get("value") for entry in containers[0]["env"]}
    require(values.get("AI_API_ONLY_ENABLED") == "true", "owner_disabled")
    require(values.get("AI_PILOT_ENABLED") == "true", "pilot_disabled")
    require(sha(resource_projection("gateway", resource)) == plan["gateway_sha256"], "configuration_drift")


async def review_ledger(control, plan):
    ledger, etag = await control._read_ledger()
    require(not ledger["active"], "operation_active")
    require(ledger["acceptance"] == {"attempts": 16, "reserved": 3748800000}, "acceptance_drift")
    owner = ledger["owner_usage"]
    require(0 <= owner["attempts"] <= 12 and owner["reserved"] == owner["attempts"] * 234300000
            and 953404650 <= owner["period_cost"] <= 3765004650, "owner_accounting")
    audit, _ = await control.store.read("owner-transition-v1")
    require(sha(audit) == plan["audit_sha256"], "audit_drift")
    records = {}
    for key in plan["acceptance_keys"]:
        require(re.fullmatch(r"op-[a-f0-9]{64}", key) is not None, "operation_key")
        records[key], _ = await control.store.read(key)
    require(len(records) == 16 and sha(records) == plan["operations_sha256"], "history_drift")
    require(sum(record["usage_known"] is False for record in records.values()) == 4, "hold_drift")
    return ledger, etag


def check_cost(result, ledger, plan, now):
    properties = result["properties"]
    require(not properties.get("nextLink"), "cost_incomplete")
    columns = [entry["name"] for entry in properties["columns"]]
    rows = properties["rows"]
    require(bool(rows) and all(row[columns.index("Currency")] == "EUR" for row in rows), "cost_currency")
    posted = sum((Decimal(str(row[columns.index("PreTaxCost")])) for row in rows), Decimal(0))
    require(posted.is_finite() and 0 <= posted < Decimal("12"), "cost_stop")
    remaining_days = max(Decimal(0), Decimal(str(plan["end"] - now)) / Decimal(86400))
    remaining_attempts = 12 - ledger["owner_usage"]["attempts"]
    require(0 <= remaining_attempts <= 12, "owner_counter")
    projected = (posted * Decimal("1.5") + remaining_days * Decimal("6.45") / 30
                 + Decimal(remaining_attempts) * Decimal("0.2343") * Decimal("1.5")
                 + Decimal("0.95340465") * Decimal("1.5") + Decimal("4.30") + Decimal("1.50"))
    require(projected <= Decimal("18"), "cost_forecast")
    return {"posted_net_eur": str(posted), "conservative_all_in_eur": str(projected)}


async def renew_owner(plan, settings, cloud, control, *, clock=time.time):
    now = int(clock())
    policy = control.policy
    require(policy.owner_usage is not None and len(control.allowlist) == 1, "owner_scope")
    require(plan["end"] == policy.owner_usage.expires_at == policy.acceptance.expires_at
            == policy.deployment_verified_until, "period_drift")
    require(policy.owner_usage.daily_attempts == 3 and policy.owner_usage.max_attempts == 12, "limit_drift")
    require(configuration_digest(settings) == plan["configuration_sha256"], "configuration_drift")
    if now >= plan["end"]:
        cloud.retire()
        return {"status": "period_ended", "end": plan["end"]}
    check_gateway(cloud.gateway(), plan)
    require({entry["kind"] for entry in plan["resources"]} == {"auth", "backend", "roles", "storage", "model"}, "missing_evidence")
    for entry in plan["resources"]:
        require(sha(resource_projection(entry["kind"], cloud.resource(entry["url"]))) == entry["sha256"], "evidence_drift")
    previous = cloud.bundle()
    approval = verify_approval(settings, previous)
    require(all(approval["evidence"][name] == plan["fixed_evidence"][name] for name in ("budget", "privacy")), "scope_drift")
    ledger, etag = await review_ledger(control, plan)
    cost = check_cost(cloud.cost(now), ledger, plan, now)
    if ledger["owner_usage"]["attempts"] == 12:
        return {"status": "quota_exhausted", "end": plan["end"]}
    evidence = {name: {"configuration_sha256": plan["configuration_sha256"], "checked_at": now,
        "checks": {check: True for check in (OWNER_LEDGER_CHECKS if name == "ledger" else CHECKS[name])}}
        for name in RENEWABLE}
    signed = prepare_approval(settings, evidence, previous=previous)
    require(signed["approval"]["expires_at"] <= min(plan["end"], now + 86400), "expiry_drift")
    check_gateway(cloud.gateway(), plan)
    require(cloud.bundle() == previous, "grant_changed")
    after, after_etag = await control._read_ledger()
    require(after == ledger and after_etag == etag, "ledger_changed")
    cloud.publish(signed)
    require(cloud.bundle() == signed, "publication_unconfirmed")
    return {"status": "renewed", "issued_at": signed["approval"]["issued_at"],
        "expires_at": signed["approval"]["expires_at"], "end": plan["end"], "cost": cost,
        "owner_attempts": ledger["owner_usage"]["attempts"], "holds": 4, "model_requests": 0}


class AzureRenewal:
    def __init__(self, plan, credential, client):
        self.plan, self.credential, self.client = plan, credential, client
        self.arm = "https://management.azure.com" + plan["resource_group_id"]
        require(re.fullmatch(r"/subscriptions/[a-f0-9-]{36}/resourceGroups/pft-pilot-[a-z0-9-]+", plan["resource_group_id"]) is not None, "target_scope")
        require(plan["job_url"].startswith(self.arm + "/providers/Microsoft.App/jobs/"), "job_scope")
        require(re.fullmatch(r"https://[a-z0-9-]+\.vault\.azure\.net/secrets/owner-release-bundle", plan["bundle_url"]) is not None, "bundle_scope")

    def request(self, method, url, *, vault=False, body=None):
        scope = "https://vault.azure.net/.default" if vault else "https://management.azure.com/.default"
        token = self.credential.get_token(scope).token
        response = self.client.request(method, url, json=body,
            headers={"Authorization": "Bearer " + token, "ClientType": "pft-owner-auto-renewal"})
        require(200 <= response.status_code < 300, "dependency_" + str(response.status_code))
        return response.json() if response.content else None

    def resource(self, url):
        require(url.startswith(self.arm + "/"), "resource_scope")
        return self.request("GET", url)

    def gateway(self):
        return self.resource(self.plan["gateway_url"])

    def bundle(self):
        record = self.request("GET", self.plan["bundle_url"] + "?api-version=7.4", vault=True)
        require(record.get("attributes", {}).get("enabled") is True, "grant_disabled")
        return json.loads(record["value"])

    def load_secrets(self):
        gateway = self.gateway()
        check_gateway(gateway, self.plan)
        references = {entry["name"]: entry["keyVaultUrl"] for entry in gateway["properties"]["configuration"]["secrets"]}
        expected = {"GATEWAY_SERVICE_TOKEN", "AI_PILOT_SIGNING_KEY", "AI_PILOT_FINGERPRINT_KEY", "AI_PILOT_RELEASE_KEY"}
        bindings = {entry["name"]: references[entry["secretRef"]] for entry in
                    gateway["properties"]["template"]["containers"][0]["env"] if entry["name"] in expected}
        require(set(bindings) == expected, "missing_secret")
        for name, url in bindings.items():
            require(url.startswith(self.plan["bundle_url"].rsplit("/", 1)[0] + "/"), "secret_scope")
            record = self.request("GET", url + "?api-version=7.4", vault=True)
            require(record.get("attributes", {}).get("enabled") is True, "secret_disabled")
            os.environ[name] = record["value"]

    def cost(self, now):
        query = {"type": "ActualCost", "timeframe": "Custom", "timePeriod": {
            "from": self.plan["start"], "to": datetime.fromtimestamp(now, timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")},
            "dataset": {"granularity": "None", "aggregation": {"totalCost": {"name": "PreTaxCost", "function": "Sum"}}}}
        return self.request("POST", self.arm + "/providers/Microsoft.CostManagement/query?api-version=2023-11-01", body=query)

    def publish(self, signed):
        self.request("PUT", self.plan["bundle_url"] + "?api-version=7.4", vault=True,
                     body={"value": canonical(signed).decode()})

    def retire(self):
        self.request("DELETE", self.plan["job_url"])


async def main_async():
    from azure.data.tables.aio import TableClient
    from azure.identity import ManagedIdentityCredential
    from azure.identity.aio import ManagedIdentityCredential as AsyncCredential
    from app.config import Settings
    from app.pilot_access import build_coordinator
    from app.pilot_table import AzureTableStore

    plan = json.loads(os.environ["AI_PILOT_RENEWAL_PLAN_JSON"])
    client_id = os.environ["AI_PILOT_RENEWAL_CLIENT_ID"]
    logger = logging.Logger("pilot.renewal.sdk")
    logger.disabled = True
    logger.propagate = False
    with ManagedIdentityCredential(client_id=client_id, logger=logger, logging_enable=False, retry_total=0) as identity:
        with httpx2.Client(timeout=15, follow_redirects=False) as client:
            cloud = AzureRenewal(plan, identity, client)
            if int(time.time()) >= plan["end"]:
                cloud.retire()
                return {"status": "period_ended", "end": plan["end"]}
            cloud.load_secrets()
            credential = AsyncCredential(client_id=client_id, logger=logger, logging_enable=False, retry_total=0)
            table = TableClient(os.environ["AI_PILOT_TABLE_ENDPOINT"], os.environ["AI_PILOT_TABLE_NAME"], credential=credential,
                retry_total=0, logging_enable=False, logger=logger, tracing_enable=False, connection_timeout=3, read_timeout=5)
            store = AzureTableStore(table)
            store.credential = credential
            try:
                settings = Settings()
                async with asyncio.timeout(160):
                    return await renew_owner(plan, settings, cloud, build_coordinator(store, settings=settings))
            finally:
                await store.close()


if __name__ == "__main__":
    try:
        print(json.dumps(asyncio.run(main_async())), flush=True)
    except Exception as error:
        reason = str(error) if isinstance(error, RenewalBlocked) else type(error).__name__
        print(json.dumps({"status": "failed_closed", "reason": reason, "model_requests": 0}), flush=True)
        raise SystemExit(1) from None