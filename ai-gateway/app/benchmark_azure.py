"""Entra-only local benchmark resource attestation. No resource provisioning."""

import base64
import fcntl
import json
import logging
import os
import stat
import time
from urllib.parse import urlsplit

import httpx2
from azure.data.tables.aio import TableClient
from azure.identity.aio import AzureCliCredential

from app.benchmark import MANIFEST_HASH, result_directory, sha
from app.pilot import PilotError
from app.pilot_table import AzureTableStore, _sdk_logger
from app.providers.openai_api import AzureOpenAIProvider
from app.providers.pricing import GPT_54_MINI


def local_guard():
    if (os.environ.get("APP_ENV") != "development" or os.environ.get("AI_PILOT_ENABLED") != "true"
            or not os.environ.get("AZURE_CONFIG_DIR")
            or os.environ.get("GATEWAY_DEV_AUTH_BYPASS", "false").lower() != "false"
            or any(os.environ.get(name) for name in (
                "WEBSITE_INSTANCE_ID", "CONTAINER_APP_NAME", "IDENTITY_ENDPOINT", "MSI_ENDPOINT",
                "KUBERNETES_SERVICE_HOST", "AZURE_CLIENT_SECRET", "AZURE_OPENAI_API_KEY",
            ))):
        raise PilotError()


def token_identity(token, approval, scope):
    try:
        payload = token.token.split(".")[1]
        claims = json.loads(base64.urlsafe_b64decode(payload + "=" * (-len(payload) % 4)))
        audience = scope.removesuffix("/.default").rstrip("/")
        audiences = {audience}
        if audience == "https://management.azure.com":
            audiences.add("https://management.core.windows.net")
        if (claims.get("tid") != str(approval.tenant_id) or claims.get("oid") != str(approval.operator_id)
                or claims.get("appid", claims.get("azp")) != "04b07795-8ddb-461a-bbee-02f9e1bf7b46"
                or claims.get("aud", "").rstrip("/") not in audiences
                or claims.get("exp", 0) <= time.time() + 120 or token.expires_on <= time.time() + 120):
            raise ValueError()
    except Exception:
        raise PilotError() from None


class CheckedCredential:
    def __init__(self, credential, approval, *, ledger_cleanup=False):
        self.credential, self.approval = credential, approval
        self.ledger_cleanup = ledger_cleanup

    async def get_token(self, *scopes, **kwargs):
        local_guard()
        if not self.ledger_cleanup:
            self.approval.check_window()
        if self.ledger_cleanup and scopes != ("https://storage.azure.com/.default",):
            raise PilotError()
        if len(scopes) != 1 or scopes[0] not in {
            "https://management.azure.com/.default", "https://storage.azure.com/.default", "https://ai.azure.com/.default"
        }:
            raise PilotError()
        token = await self.credential.get_token(*scopes, **kwargs)
        token_identity(token, self.approval, scopes[0])
        return token


def validate_resources(approval, group, account, deployment, storage, inventory):
    tags = {"purpose": "pft-public-benchmark", "benchmarkRun": approval.run_id,
            "manifestSha256": MANIFEST_HASH, "expiresAt": str(approval.expires_at)}
    for resource, identifier in ((group, approval.group_id), (account, approval.account_id), (storage, approval.storage_id)):
        if (resource.get("id", "").lower() != identifier.lower() or resource.get("location", "").lower() != "swedencentral"
                or any(resource.get("tags", {}).get(key) != value for key, value in tags.items())):
            raise PilotError()
    expected_ids = {approval.account_id.lower(), approval.storage_id.lower(),
                    (approval.group_id + "/providers/Microsoft.Resources/deployments/pft-bench-" + approval.run_id).lower(),
                    (approval.account_id + "/deployments/mini-bench").lower(),
                    (approval.storage_id + "/tableServices/default").lower(),
                    (approval.storage_id + "/tableServices/default/tables/MiniBenchmark").lower()}
    if inventory.get("nextLink") or not inventory.get("value") or any(
        resource.get("id", "").lower() not in expected_ids for resource in inventory["value"]
    ):
        raise PilotError()
    account_properties, storage_properties = account.get("properties", {}), storage.get("properties", {})
    for properties in (account_properties, storage_properties):
        network = properties.get("networkAcls", {})
        addresses = network.get("ipRules", [])
        if (properties.get("provisioningState") != "Succeeded" or properties.get("publicNetworkAccess") != "Enabled"
                or network.get("defaultAction") != "Deny" or network.get("bypass") != "None"
                or network.get("virtualNetworkRules") or len(addresses) != 1
                or addresses[0].get("value") != approval.egress_ipv4
                or addresses[0].get("action", "Allow") != "Allow"):
            raise PilotError()
    if (account.get("kind") != "OpenAI" or account.get("sku", {}).get("name") != "S0"
            or account_properties.get("disableLocalAuth") is not True
            or account_properties.get("customSubDomainName") != approval.account_name
            or account_properties.get("endpoint", "").rstrip("/") != f"https://{approval.account_name}.openai.azure.com"
            or storage.get("kind") != "StorageV2" or storage.get("sku", {}).get("name") != "Standard_LRS"
            or storage_properties.get("allowSharedKeyAccess") is not False
            or storage_properties.get("allowBlobPublicAccess") is not False
            or storage_properties.get("supportsHttpsTrafficOnly") is not True
            or storage_properties.get("minimumTlsVersion") != "TLS1_2"
            or storage_properties.get("primaryEndpoints", {}).get("table", "").rstrip("/") != f"https://{approval.storage_name}.table.core.windows.net"):
        raise PilotError()
    properties = deployment.get("properties", {})
    model = properties.get("model", {})
    if (deployment.get("id", "").lower() != (approval.account_id + "/deployments/mini-bench").lower()
            or properties.get("provisioningState") != "Succeeded"
            or model.get("format") != "OpenAI" or model.get("name") != GPT_54_MINI.model
            or model.get("version") != GPT_54_MINI.version
            or deployment.get("sku", {}).get("name") != GPT_54_MINI.sku
            or deployment.get("sku", {}).get("capacity") != approval.capacity
            or properties.get("versionUpgradeOption") != "NoAutoUpgrade"):
        raise PilotError()


class TableRequestBudget:
    def __init__(self, approval, *, cleanup=False):
        directory = os.environ.get("BENCHMARK_CONTROL_DIR")
        if not directory:
            raise PilotError()
        self.filename = result_directory(directory) / (approval.run_id + "-table-requests.log")
        self.binding = sha(approval.model_dump(mode="json"))
        self.max_requests, self.max_units = (3000, 50000) if cleanup else (2500, 40000)

    def initialize(self):
        descriptor = os.open(self.filename, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
        with os.fdopen(descriptor, "wb") as output:
            output.write((self.binding + "\n").encode())
            output.flush()
            os.fsync(output.fileno())
        self._sync_directory()

    def _sync_directory(self):
        descriptor = os.open(self.filename.parent, os.O_RDONLY)
        try:
            os.fsync(descriptor)
        finally:
            os.close(descriptor)

    def __call__(self, request):
        route = urlsplit(request.http_request.url)
        units = 100 if route.path.endswith("/$batch") else 1000 if (
            request.http_request.method == "GET" and "PartitionKey=" not in route.path) else 1
        try:
            descriptor = os.open(self.filename, os.O_RDWR | os.O_APPEND | os.O_NOFOLLOW | os.O_NONBLOCK)
        except OSError:
            raise PilotError() from None
        with os.fdopen(descriptor, "r+b") as output:
            info = os.fstat(output.fileno())
            if (not stat.S_ISREG(info.st_mode) or stat.S_IMODE(info.st_mode) != 0o600
                    or info.st_nlink != 1 or info.st_uid != os.getuid()):
                raise PilotError()
            fcntl.flock(output, fcntl.LOCK_EX | fcntl.LOCK_NB)
            output.seek(0)
            content = output.read(100001)
            lines = content.decode().splitlines()
            if (len(content) > 100000 or not content.endswith(b"\n") or not lines or lines[0] != self.binding
                    or any(line not in {"1", "100", "1000"} for line in lines[1:])
                    or len(lines) > self.max_requests or sum(map(int, lines[1:])) + units > self.max_units):
                raise PilotError()
            output.write(f"{units}\n".encode())
            output.flush()
            os.fsync(output.fileno())
            self._sync_directory()


class AzureBenchmark:
    def __init__(self, approval):
        local_guard()
        approval.check_window()
        self.approval, self.attested_at = approval, 0
        self.raw_credential = AzureCliCredential(subscription=str(approval.subscription_id))
        self.credential = CheckedCredential(self.raw_credential, approval)
        self.http = httpx2.AsyncClient(timeout=15, follow_redirects=False, trust_env=False)
        for name in ("azure.identity", "azure.identity.aio._internal.decorators",
                     "azure.identity.aio._credentials.azure_cli", "httpx2", "httpcore2"):
            logging.getLogger(name).disabled = True

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        await self.http.aclose()
        await self.raw_credential.close()

    async def arm(self, resource, version):
        token = await self.credential.get_token("https://management.azure.com/.default")
        response = await self.http.get("https://management.azure.com" + resource,
                                       params={"api-version": version}, headers={"Authorization": "Bearer " + token.token})
        if response.status_code != 200 or len(response.content) > 2_000_000:
            raise PilotError()
        return response.json()

    async def attest(self):
        self.attested_at = 0
        config = self.approval
        group = await self.arm(config.group_id, "2024-03-01")
        account = await self.arm(config.account_id, "2024-10-01")
        deployment = await self.arm(config.account_id + "/deployments/mini-bench", "2024-10-01")
        storage = await self.arm(config.storage_id, "2023-05-01")
        inventory = await self.arm(config.group_id + "/resources", "2021-04-01")
        validate_resources(config, group, account, deployment, storage, inventory)
        meters = {"fc81bb98-83fa-569b-a361-70d5904b285d": .825,
                  "41b51273-5b41-5b0b-ba4b-3900379c9800": .0825,
                  "3167a76c-f4a1-53f1-8784-362e76c0787e": 4.95}
        response = await self.http.get("https://prices.azure.com/api/retail/prices", params={
            "currencyCode": "'USD'", "$filter": " or ".join(f"meterId eq '{meter}'" for meter in meters)})
        if response.status_code != 200 or len(response.content) > 2_000_000:
            raise PilotError()
        prices = response.json()
        items = prices.get("Items", [])
        if prices.get("NextPageLink") or len(items) != 3 or {item.get("meterId") for item in items} != set(meters):
            raise PilotError()
        for item in items:
            if (item.get("retailPrice") != meters[item["meterId"]] or item.get("currencyCode") != "USD"
                    or item.get("armRegionName") != "swedencentral" or item.get("unitOfMeasure") != "1M"
                    or item.get("type") != "Consumption" or item.get("isPrimaryMeterRegion") is not True):
                raise PilotError()
        self.attested_at = time.monotonic()
        return {"verified_at": int(time.time()), "approval_hash": sha(config.model_dump(mode="json")),
                "resources_hash": sha([group, account, deployment, storage, inventory]),
                "prices_hash": sha(items), "model": GPT_54_MINI.price.model,
                "region": "swedencentral", "sku": GPT_54_MINI.sku,
                "service_tier": "default-requested-response-must-confirm"}

    def guard(self):
        local_guard()
        self.approval.check_window()
        if not self.attested_at or not 0 <= time.monotonic() - self.attested_at < 30:
            raise PilotError()

    async def model_token(self):
        self.guard()
        token = await self.credential.get_token("https://ai.azure.com/.default")
        self.guard()
        return token.token

    def store(self, *, test_partition=None):
        self.guard()
        partition = "benchmark-" + self.approval.run_id if test_partition is None else test_partition
        if test_partition is not None and not test_partition.startswith("test-"):
            raise PilotError()
        client = TableClient(f"https://{self.approval.storage_name}.table.core.windows.net", "MiniBenchmark",
                             credential=self.credential, retry_total=0, logging_enable=False,
                             raw_request_hook=TableRequestBudget(self.approval), retry_to_secondary=False,
                             redirect_max=0,
                             logger=_sdk_logger, tracing_enable=False, connection_timeout=2, read_timeout=3)
        return AzureTableStore(client, partition=partition)

    def provider(self, control):
        self.guard()
        return AzureOpenAIProvider(endpoint=f"https://{self.approval.account_name}.openai.azure.com",
                                   token_provider=self.model_token, dispatch_guard=self.guard,
                                   model_routes=control.routes, prices=control.prices,
                                   profile_bindings=control.profile_bindings, max_output_tokens=2000)