"""Explicit-context, AI-off bootstrap for the separately authorized private pilot."""

import argparse
from datetime import datetime, timedelta, timezone
import json
import os
from pathlib import Path
import secrets
import subprocess
import sys
import time
from uuid import UUID

from prepare import entra_requests

ROOT = Path(__file__).resolve().parent


def private_json(destination, value):
    with destination.open("x", encoding="utf-8") as stream:
        os.chmod(destination, 0o600)
        json.dump(value, stream, indent=2)
        stream.flush()
        os.fsync(stream.fileno())


class Bootstrap:
    def __init__(self, args):
        self.args = args
        self.directory = ROOT / "local" / args.name
        self.directory.mkdir(parents=True, exist_ok=True, mode=0o700)
        os.chmod(self.directory, 0o700)
        self.environment = {**os.environ, "AZURE_CONFIG_DIR": str(args.azure_config.resolve()),
                            "AZURE_CORE_COLLECT_TELEMETRY": "false"}

    def cli(self, *arguments):
        completed = subprocess.run(["az", *arguments, "--only-show-errors", "--output", "json"],
                                   env=self.environment, capture_output=True, text=True, check=False)
        if completed.returncode:
            destination = self.directory / f"error-{secrets.token_hex(4)}.json"
            private_json(destination, {"stderr": completed.stderr, "stdout": completed.stdout})
            raise RuntimeError(f"Azure operation failed; private diagnostic: {destination.name}")
        return json.loads(completed.stdout) if completed.stdout.strip() else None

    def once(self, name, *arguments):
        result = self.directory / f"{name}.json"
        intent = self.directory / f"{name}.intent.json"
        if result.exists():
            return json.loads(result.read_text())
        if intent.exists():
            raise RuntimeError(f"Unresolved {name} operation; inspect Azure before repeating it.")
        private_json(intent, {"started_at": datetime.now(timezone.utc).isoformat()})
        value = self.cli(*arguments)
        private_json(result, value)
        return value

    def verify_account(self):
        account = self.cli("account", "show")
        if (account["id"] != self.args.subscription or account["tenantId"] != self.args.tenant
                or account["state"] != "Enabled" or account["user"]["type"] != "user"):
            raise RuntimeError("Private Azure context does not match the approved subscription/tenant.")
        owner = self.cli("ad", "signed-in-user", "show")
        contacts = self.cli("rest", "--method", "get", "--url",
                            "https://graph.microsoft.com/v1.0/me?$select=id,mail,otherMails")
        if contacts["id"] != owner["id"]:
            raise RuntimeError("Budget contact identity mismatch.")
        return {**owner, **contacts}

    def initialize(self, owner):
        state_file = self.directory / "period.json"
        group = "pft-pilot-" + self.args.name
        if not state_file.exists():
            if self.cli("group", "exists", "--subscription", self.args.subscription, "--name", group):
                raise RuntimeError("Pilot group already exists without a local ownership record.")
            apps = self.cli("ad", "app", "list", "--filter", f"startswith(displayName,'{group}')")
            if apps:
                raise RuntimeError("Pilot applications already exist without a local ownership record.")
            inventory = self.cli("resource", "list", "--subscription", self.args.subscription)
            private_json(self.directory / "baseline.json", inventory)
            start = datetime.now(timezone.utc).replace(microsecond=0)
            private_json(state_file, {"subscription": self.args.subscription, "tenant": self.args.tenant,
                                     "owner": owner["id"], "group": group, "start": start.isoformat(),
                                     "end": (start + timedelta(days=30)).isoformat(),
                                     "authorized_period_eur": 20, "authorized_setup_eur": 5,
                                     "operational_net_stop_eur": 12, "max_model_attempts": 10})
        state = json.loads(state_file.read_text())
        if (state["subscription"] != self.args.subscription or state["tenant"] != self.args.tenant
                or state["owner"] != owner["id"] or state["group"] != group
                or datetime.now(timezone.utc) >= datetime.fromisoformat(state["end"])):
            raise RuntimeError("Pilot ownership or authorized period mismatch.")
        self.once("resource-group", "group", "create", "--subscription", self.args.subscription,
                  "--name", group, "--location", "swedencentral", "--tags",
                  "purpose=private-pilot", "ai=disabled", f"expiresAt={state['end']}")
        applications = {kind: self.once(f"{kind}-app", "ad", "app", "create", "--display-name", f"{group}-{kind}",
                                       "--sign-in-audience", "AzureADMyOrg")
                        for kind in ("gateway", "backend", "native")}
        data = {"gatewayAudience": applications["gateway"]["appId"],
                "backendAudience": applications["backend"]["appId"], "backendPrincipalId": None}
        for kind in ("gateway", "backend", "native"):
            body = entra_requests(data, applications["gateway"]["id"])[f"{kind}ApplicationPatch"]
            body_file = self.directory / f"{kind}-patch.json"
            if not body_file.exists():
                private_json(body_file, body)
            self.once(f"{kind}-configured", "rest", "--method", "patch", "--url",
                      f"https://graph.microsoft.com/v1.0/applications/{applications[kind]['id']}",
                      "--body", "@" + str(body_file))
            principal = self.once(f"{kind}-sp", "ad", "sp", "create", "--id", applications[kind]["appId"])
            if kind == "gateway":
                self.once("gateway-role-required", "ad", "sp", "update", "--id", principal["id"],
                          "--set", "appRoleAssignmentRequired=true")
        params_file = self.directory / "parameters.json"
        if not params_file.exists():
            email = owner.get("mail") or owner.get("userPrincipalName", "")
            if ("@" not in email or "#EXT#" in email) and len(owner.get("otherMails", [])) == 1:
                email = owner["otherMails"][0]
            if "@" not in email or "#EXT#" in email:
                raise RuntimeError("No usable owner email for budget notifications.")
            policy = json.loads((ROOT / "policy.proposed.json").read_text())
            policy["deployment_verified_until"] = int(datetime.fromisoformat(state["end"]).timestamp())
            for scope in ("total", "person"):
                policy[scope].update(day=10, month=10, daily_usd="2.343", monthly_usd="2.343")
            start = datetime.fromisoformat(state["start"])
            end = datetime.fromisoformat(state["end"])
            budget_end = (end.replace(day=1) + timedelta(days=32)).replace(day=1)
            parameters = {"pilotName": self.args.name, "tenantId": self.args.tenant,
                          "nativeClientId": applications["native"]["appId"],
                          "backendAudience": applications["backend"]["appId"],
                          "gatewayAudience": applications["gateway"]["appId"],
                          "allowlist": [{"tid": self.args.tenant, "oid": owner["id"]}], "policy": policy,
                          "allInMonthlyEUR": 12, "billingCurrency": "EUR",
                          "budgetStartDate": start.replace(day=1).strftime("%Y-%m-%dT00:00:00Z"),
                          "budgetEndDate": budget_end.strftime("%Y-%m-%dT00:00:00Z"),
                          "budgetEmails": [email], "deployGateway": False, "enableAI": False,
                          "modelCapacity": 1,
                          **{name: secrets.token_urlsafe(48) for name in ("serviceToken", "signingKey", "fingerprintKey", "releaseKey")}}
            private_json(params_file, {"$schema": "https://schema.management.azure.com/schemas/2019-04-01/deploymentParameters.json#",
                                       "contentVersion": "1.0.0.0", "parameters": {key: {"value": value} for key, value in parameters.items()}})
        print(f"AI-off bootstrap prepared; period {state['start']} to {state['end']}.")

    def deploy(self, mode):
        state = json.loads((self.directory / "period.json").read_text())
        if (state["subscription"] != self.args.subscription or state["tenant"] != self.args.tenant
                or datetime.now(timezone.utc) >= datetime.fromisoformat(state["end"])):
            raise RuntimeError("Pilot period or subscription mismatch.")
        params_file = self.directory / "parameters.json"
        parameters = json.loads(params_file.read_text())["parameters"]
        if parameters["enableAI"]["value"] is not False or parameters["deployGateway"]["value"] is not False:
            raise RuntimeError("Bootstrap permits only AI-off infrastructure without gateway deployment.")
        self.once(mode, "deployment", "group", mode, "--subscription", self.args.subscription,
                  "--resource-group", state["group"], "--name", "pilot-bootstrap-v1",
                  "--template-file", str(ROOT / "main.json"), "--parameters", "@" + str(params_file))
        print(f"AI-off ARM {mode} completed.")


    def login_probe(self, *, analysis=False):
        import msal
        import requests

        state = json.loads((self.directory / "period.json").read_text())
        if (state["subscription"] != self.args.subscription or state["tenant"] != self.args.tenant
                or datetime.now(timezone.utc) >= datetime.fromisoformat(state["end"])):
            raise RuntimeError("Pilot ownership or authorized period mismatch.")
        deployment = json.loads((self.directory / "runtime-create.json").read_text())["properties"]["outputs"]
        if analysis:
            group = deployment["resourceGroup"]["value"]
            if group != "pft-pilot-" + self.args.name:
                raise RuntimeError("Unexpected analysis probe resource group.")
            enabled = self.cli("containerapp", "show", "--subscription", self.args.subscription,
                "--resource-group", group, "--name", group + "-gateway", "--query",
                "properties.template.containers[0].env[?name=='AI_API_ONLY_ENABLED'].value | [0]")
            if enabled != "false":
                raise RuntimeError("Native analysis qualification requires AI off.")
        scope = f"api://{deployment['backendAudience']['value']}/FoodAnalysis.Access"
        application = msal.PublicClientApplication(
            deployment["nativeClientId"]["value"],
            authority=f"https://login.microsoftonline.com/{self.args.tenant}",
            token_cache=msal.TokenCache(), enable_pii_log=False,
        )
        flow = application.initiate_device_flow(scopes=[scope])
        if "user_code" not in flow:
            raise RuntimeError("Native pilot sign-in could not be started.")
        print(flow["message"], flush=True)
        result = application.acquire_token_by_device_flow(flow)
        if "access_token" not in result:
            raise RuntimeError("Native pilot sign-in was not completed; no token persisted.")
        claims = result.get("id_token_claims", {})
        if claims.get("tid") != self.args.tenant or claims.get("oid") != state["owner"]:
            raise RuntimeError("Signed-in pilot identity does not match the sole approved participant.")
        base = deployment["apiBaseURL"]["value"]
        if analysis:
            try:
                record = self.native_analysis_checks(deployment, state, result["access_token"])
            finally:
                result.clear()
            private_json(self.directory / f"native-analysis-probe-{secrets.token_hex(4)}.json", record)
            print("Native analysis checks: " + json.dumps(record), flush=True)
            return
        with requests.Session() as client:
            client.mount("https://", requests.adapters.HTTPAdapter(max_retries=0))
            response = client.get(base + "/readiness", headers={"Authorization": "Bearer " + result["access_token"]},
                                  timeout=(10, 30), allow_redirects=False)
        result.clear()
        body_matches = response.status_code == 503 and response.json() == {"status": "not_ready"}
        record = {"checked_at": datetime.now(timezone.utc).isoformat(), "native_identity_matches": True,
                  "readiness_status": response.status_code, "expected_ai_off_backend_response": body_matches,
                  "model_attempts": 0}
        private_json(self.directory / f"native-login-probe-{secrets.token_hex(4)}.json", record)
        print(f"Native pilot request: HTTP {response.status_code}; expected AI-off response: {body_matches}; model calls: 0.")
        if not body_matches:
            raise RuntimeError("Native-to-backend admission needs investigation; no model request made.")


    def native_analysis_checks(self, deployment, state, token):
        import requests
        from qualify_auth import PAYLOAD, headers

        base = deployment["apiBaseURL"]["value"]
        gateway = deployment["gatewayBaseURL"]["value"]
        if (base != "https://pft-pilot-20260919-api.azurewebsites.net/api"
                or gateway != "https://pft-pilot-20260919-gateway.gentleriver-150ab3f0.swedencentral.azurecontainerapps.io"):
            raise RuntimeError("Unapproved native analysis target.")
        parameters = json.loads((self.directory / "acceptance-parameters.json").read_text())["parameters"]
        operation = str(UUID(int=(int(time.time() * 1000) << 80) | (7 << 76) | (2 << 62) | 1))
        native = {"Authorization": "Bearer " + token}
        cases = [
            ("native_analysis_identity", base + "/food-analysis", native, 400, "operation_required"),
            ("native_analysis_ai_off", base + "/food-analysis", {**native, "X-Operation-Id": operation}, 503, "pilot_unavailable"),
            ("native_token_denied", gateway + "/v1/food-analysis",
             headers(token, (self.args.tenant, state["owner"]), operation,
                 parameters["signingKey"]["value"], parameters["serviceToken"]["value"], PAYLOAD), 403, "pilot_forbidden"),
        ]
        checks = []
        with requests.Session() as client:
            client.mount("https://", requests.adapters.HTTPAdapter(max_retries=0))
            for name, target, authorization, expected, code in cases:
                response = client.post(target, headers=authorization, json=PAYLOAD,
                                       timeout=(10, 30), allow_redirects=False)
                passed = response.status_code == expected and response.json().get("error", {}).get("code") == code
                check = {"check": name, "status": response.status_code, "expected": expected, "passed": passed}
                checks.append(check)
                print("NATIVE_CHECK " + json.dumps(check), flush=True)
                if not passed:
                    raise RuntimeError("Native analysis qualification failed: " + name)
        return {"checked_at": datetime.now(timezone.utc).isoformat(), "native_identity_matches": True,
                "checks": checks, "model_attempts": 0}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("initialize", "validate", "create", "login-probe", "login-analysis-probe"))
    parser.add_argument("--azure-config", type=Path, required=True)
    parser.add_argument("--subscription", required=True)
    parser.add_argument("--tenant", required=True)
    parser.add_argument("--name", required=True)
    args = parser.parse_args()
    for identifier in (args.subscription, args.tenant):
        if str(UUID(identifier)) != identifier:
            parser.error("Canonical subscription and tenant UUIDs are required.")
    if (not args.azure_config.is_dir() or not 3 <= len(args.name) <= 12
            or not args.name.isascii() or not args.name.isalnum() or args.name != args.name.lower()):
        parser.error("Existing private CLI configuration and a lowercase alphanumeric pilot name are required.")
    os.umask(0o077)
    bootstrap = Bootstrap(args)
    owner = bootstrap.verify_account()
    if args.command == "initialize":
        bootstrap.initialize(owner)
    elif args.command in {"login-probe", "login-analysis-probe"}:
        bootstrap.login_probe(analysis=args.command == "login-analysis-probe")
    else:
        bootstrap.deploy(args.command)


if __name__ == "__main__":
    try:
        main()
    except Exception as error:
        print(f"Bootstrap stopped: {error}", file=sys.stderr)
        raise SystemExit(1) from None