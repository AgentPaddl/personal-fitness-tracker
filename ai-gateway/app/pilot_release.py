"""Short-lived owner approval, bound to the API-only artifact and pilot config."""

import hashlib
import hmac
import json
import os
from pathlib import Path
import re
import time
from uuid import UUID

from app.pilot import PilotError, PilotPolicy, canonical, enabled
from app.providers.pricing import GPT_54_MINI

BINDINGS = (
    "AI_PILOT_RESOURCE_GROUP", "AI_PILOT_TENANT_ID", "AI_PILOT_ALLOWLIST_JSON",
    "AI_PILOT_TABLE_ENDPOINT", "AI_PILOT_TABLE_NAME", "AI_PILOT_POLICY_JSON",
    "GATEWAY_WORKLOAD_AUDIENCE", "GATEWAY_BACKEND_PRINCIPAL_ID", "GATEWAY_BACKEND_CLIENT_ID",
    "API_ONLY_IMAGE_DIGEST", "AI_PILOT_ALL_IN_MONTHLY_EUR", "AI_PILOT_GATEWAY_CLIENT_ID",
)
EVIDENCE = {"identity", "deployment", "table_rbac", "ledger", "budget", "privacy"}
RENEWABLE = {"identity", "deployment", "table_rbac", "ledger"}
CHECKS = {
    "identity": {"exact_backend_role", "native_token_denied", "foreign_workload_denied", "tampered_request_denied", "easy_auth_provenance"},
    "deployment": {"api_only_inventory", "image_digest_verified", "pilot_legacy_access_absent", "body_limits_verified", "scale_limits_verified", "model_profile_verified"},
    "table_rbac": {"table_scoped_role", "no_shared_keys", "anonymous_access_denied", "foreign_identity_denied"},
    "ledger": {"new_pilot_ledger", "policy_digest_matches", "cas_race_passed", "replay_denied", "unknown_holds_preserved"},
    "budget": {"period_budget_approved", "billing_currency_eur", "prices_reviewed", "shutdown_owner_assigned"},
    "privacy": {"health_data_basis_recorded", "datazone_terms_reviewed", "no_payload_logs_verified", "retention_deletion_approved"},
}
ACCEPTANCE_PRIVACY_CHECKS = {"synthetic_manifest_reviewed", "metadata_basis_recorded", "datazone_terms_reviewed", "no_payload_logs_verified", "retention_deletion_approved"}
OWNER_LEDGER_CHECKS = (CHECKS["ledger"] - {"new_pilot_ledger"}) | {"acceptance_frozen", "owner_phase_migrated", "shared_period_cost_preserved"}
ACCEPTANCE_GRANT_SECONDS = 3600


def is_api_artifact():
    return Path(__file__).with_name(".api-only").is_file()


def configuration_digest(settings):
    values = {name: os.environ[name] for name in BINDINGS}
    values["model"] = [settings.azure_openai_endpoint, settings.azure_openai_model_routes(),
                       settings.azure_openai_profiles(), settings.azure_openai_prices().model_dump(mode="json"),
                       settings.ai_provider_max_output_tokens, settings.ai_provider_timeout_seconds,
                       settings.ai_provider_max_concurrency]
    values["keys"] = [hashlib.sha256(os.environ[name].encode()).hexdigest() for name in (
        "GATEWAY_SERVICE_TOKEN", "AI_PILOT_SIGNING_KEY", "AI_PILOT_FINGERPRINT_KEY",
    )]
    return hashlib.sha256(canonical(values)).hexdigest()


def validate_release(settings):
    try:
        if (not is_api_artifact() or os.environ.get("AI_API_ONLY_ENABLED") != "true"
                or not enabled() or settings.app_env != "production" or settings.ai_provider != "azure_openai"
                or settings.gateway_dev_auth_bypass or settings.azure_openai_api_key is not None
                or any(os.environ.get(name) for name in ("COPILOT_GITHUB_TOKEN", "GH_TOKEN", "GITHUB_TOKEN"))):
            raise ValueError()
        from app.workload_auth import WorkloadVerifier

        WorkloadVerifier.configured()
        str(UUID(os.environ["AI_PILOT_GATEWAY_CLIENT_ID"]))
        if (not re.fullmatch(r"pft-pilot-[a-z0-9-]{3,40}", os.environ["AI_PILOT_RESOURCE_GROUP"])
                or not re.fullmatch(r"Pilot[A-Za-z0-9]{1,58}", os.environ["AI_PILOT_TABLE_NAME"])
                or not re.fullmatch(r"https://[a-z0-9]{3,24}\.table\.core\.windows\.net/?", os.environ["AI_PILOT_TABLE_ENDPOINT"])
                or not re.fullmatch(r"sha256:[a-f0-9]{64}", os.environ["API_ONLY_IMAGE_DIGEST"])
                or not re.fullmatch(r"[1-9][0-9]{0,3}", os.environ["AI_PILOT_ALL_IN_MONTHLY_EUR"])):
            raise ValueError()
        policy = PilotPolicy.model_validate_json(os.environ["AI_PILOT_POLICY_JSON"])
        now = time.time()
        if (policy.benchmark is not None or not now < policy.deployment_verified_until <= now + 31 * 86400
                or policy.max_output_tokens != 2000 or settings.ai_provider_max_output_tokens != 2000
                or settings.ai_provider_max_concurrency > policy.total.concurrent):
            raise ValueError()
        for field in ("minute", "day", "month", "concurrent", "daily_usd", "monthly_usd"):
            if getattr(policy.person, field) > getattr(policy.total, field):
                raise ValueError()
        if policy.person.daily_usd < GPT_54_MINI.reserve_usd(2000):
            raise ValueError()
        identities = json.loads(os.environ["AI_PILOT_ALLOWLIST_JSON"])
        pairs = {(str(UUID(entry["tid"])), str(UUID(entry["oid"]))) for entry in identities}
        if not 1 <= len(identities) <= 2 or len(pairs) != len(identities) or {tenant for tenant, person in pairs} != {os.environ["AI_PILOT_TENANT_ID"]}:
            raise ValueError()
        if policy.acceptance and (len(identities) != 1 or now >= policy.acceptance.expires_at):
            raise ValueError()
        if policy.owner_usage and now >= policy.owner_usage.expires_at:
            raise ValueError()
        routes = settings.azure_openai_model_routes()
        if (len(set(routes.values())) != 1
                or set(settings.azure_openai_profiles().values()) != {GPT_54_MINI.identifier}):
            raise ValueError()
        keys = [os.environ[name] for name in ("GATEWAY_SERVICE_TOKEN", "AI_PILOT_SIGNING_KEY", "AI_PILOT_FINGERPRINT_KEY", "AI_PILOT_RELEASE_KEY")]
        if len(set(keys)) != 4 or any(len(key) < 32 for key in keys):
            raise ValueError()
        approval = verify_approval(settings, {"approval": json.loads(os.environ["AI_PILOT_RELEASE_JSON"]),
                                             "signature": os.environ["AI_PILOT_RELEASE_SIGNATURE"]})
        if now >= approval["expires_at"]:
            raise ValueError()
        return approval
    except Exception:
        raise PilotError() from None


async def verify_ledger():
    from app.pilot_access import build_coordinator

    control = build_coordinator()
    try:
        ledger, _ = await control._read_ledger()
        if ledger.get("benchmark") is not None:
            raise PilotError()
    finally:
        await control.store.close()


def verify_approval(settings, signed):
    try:
        approval = signed["approval"]
        now = time.time()
        policy = PilotPolicy.model_validate_json(os.environ["AI_PILOT_POLICY_JSON"])
        lifetime = ACCEPTANCE_GRANT_SECONDS if policy.acceptance and not policy.owner_usage else 86400
        if (set(signed) != {"approval", "signature"}
                or set(approval) != {"configuration_sha256", "issued_at", "expires_at", "evidence", "approved"}
                or approval["approved"] is not True
                or any(type(approval[field]) is not int for field in ("issued_at", "expires_at"))
                or not 0 < approval["issued_at"] <= now
                or not approval["issued_at"] < approval["expires_at"] <= approval["issued_at"] + lifetime
                or policy.acceptance is not None and approval["expires_at"] > policy.acceptance.expires_at
                or policy.owner_usage is not None and approval["expires_at"] > policy.owner_usage.expires_at
                or not approval["expires_at"] <= policy.deployment_verified_until <= now + 31 * 86400
                or now >= policy.deployment_verified_until or policy.benchmark is not None
                or approval["configuration_sha256"] != configuration_digest(settings)
                or set(approval["evidence"]) != EVIDENCE
                or any(not re.fullmatch(r"[a-f0-9]{64}", value) for value in approval["evidence"].values())):
            raise ValueError()
        key = os.environ["AI_PILOT_RELEASE_KEY"].encode()
        expected = hmac.new(key, canonical(approval), hashlib.sha256).hexdigest()
        if len(key) < 32 or not hmac.compare_digest(expected, signed["signature"]):
            raise ValueError()
        return approval
    except Exception:
        raise PilotError() from None


def prepare_approval(settings, evidence, *, previous=None):
    configuration = configuration_digest(settings)
    now = time.time()
    policy = PilotPolicy.model_validate_json(os.environ["AI_PILOT_POLICY_JSON"])
    prior = verify_approval(settings, previous) if previous is not None else None
    required = RENEWABLE if prior is not None else EVIDENCE
    if (set(evidence) != required or policy.benchmark is not None
            or not now < policy.deployment_verified_until <= now + 31 * 86400):
        raise PilotError()
    for name, record in evidence.items():
        checks = CHECKS[name]
        if name == "privacy" and policy.acceptance and not policy.owner_usage:
            checks = ACCEPTANCE_PRIVACY_CHECKS
        if name == "ledger" and policy.owner_usage:
            checks = OWNER_LEDGER_CHECKS
        if (set(record) != {"configuration_sha256", "checked_at", "checks"}
                or record["configuration_sha256"] != configuration
                or type(record["checked_at"]) is not int or not now - 86400 <= record["checked_at"] <= now
                or set(record["checks"]) != checks
                or any(value is not True for value in record["checks"].values())):
            raise PilotError()
    hashes = dict(prior["evidence"]) if prior is not None else {}
    hashes.update({name: hashlib.sha256(canonical(record)).hexdigest() for name, record in evidence.items()})
    if policy.owner_usage:
        deadline = min(int(now) + 86400, policy.owner_usage.expires_at)
    elif policy.acceptance:
        deadline = min(int(now) + ACCEPTANCE_GRANT_SECONDS, policy.acceptance.expires_at)
    else:
        deadline = policy.deployment_verified_until
    approval = {"configuration_sha256": configuration, "issued_at": int(now),
                "expires_at": min(policy.deployment_verified_until, deadline,
                                  *(record["checked_at"] + 86400 for record in evidence.values())),
                "approved": True, "evidence": hashes}
    if approval["expires_at"] <= approval["issued_at"]:
        raise PilotError()
    key = os.environ["AI_PILOT_RELEASE_KEY"].encode()
    if len(key) < 32:
        raise PilotError()
    return {"approval": approval, "signature": hmac.new(key, canonical(approval), hashlib.sha256).hexdigest()}


async def initialize_ledger(settings):
    from app.pilot_access import build_coordinator

    policy = PilotPolicy.model_validate_json(os.environ["AI_PILOT_POLICY_JSON"])
    if (not re.fullmatch(r"pft-pilot-[a-z0-9-]{3,40}", os.environ["AI_PILOT_RESOURCE_GROUP"])
            or not re.fullmatch(r"Pilot[A-Za-z0-9]{1,58}", os.environ["AI_PILOT_TABLE_NAME"])
            or policy.benchmark is not None or os.environ.get("AI_API_ONLY_ENABLED") != "false"):
        raise PilotError()
    control = build_coordinator(settings=settings)
    try:
        ledger, _ = await control.store.read("ledger")
        if ledger is not None:
            raise PilotError()
        await control.store.commit([("ledger", control.initial_ledger(), None)])
    finally:
        await control.store.close()


def main():
    import argparse
    import asyncio
    from app.config import Settings

    parser = argparse.ArgumentParser(description="Offline approval binding; ledger initialization is a separately authorized cloud operation.")
    parser.add_argument("command", choices=["digest", "approve", "renew", "initialize-ledger"])
    parser.add_argument("--previous", type=Path)
    parser.add_argument("--evidence", type=Path)
    parser.add_argument("--destination", type=Path)
    parser.add_argument("--owner-approved", action="store_true")
    parser.add_argument("--confirm-new-pilot-ledger", action="store_true")
    args = parser.parse_args()
    settings = Settings()
    if args.command == "digest":
        print(configuration_digest(settings))
    elif args.command in {"approve", "renew"}:
        if (args.evidence is None or args.destination is None
                or args.command == "approve" and not args.owner_approved
                or args.command == "renew" and args.previous is None):
            parser.error("Evidence/output and initial owner approval or a previous signed grant are required.")
        previous = json.loads(args.previous.read_text()) if args.command == "renew" else None
        result = prepare_approval(settings, json.loads(args.evidence.read_text()), previous=previous)
        with args.destination.open("x") as target:
            json.dump(result, target, indent=2)
    else:
        if not args.confirm_new_pilot_ledger:
            parser.error("Explicit new pilot ledger confirmation is required.")
        asyncio.run(initialize_ledger(settings))


if __name__ == "__main__":
    main()