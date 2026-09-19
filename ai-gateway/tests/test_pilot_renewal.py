import asyncio
from copy import deepcopy
from types import SimpleNamespace

import pytest

from app import pilot_release, pilot_renewal
from app.pilot import PilotError
from tests.test_api_runtime import release_config
from tests.test_pilot import migrate_owner, owner_coordinator, owner_transition_fixture


@pytest.fixture
def renewal(monkeypatch, release_config):
    old, policy = owner_transition_fixture()
    old.policy = old.policy.model_copy(update={"deployment_verified_until": policy.owner_usage.expires_at})
    old.policy_id = pilot_renewal.sha(old.policy.model_dump(mode="json"))
    old.store.rows["ledger"][0]["policy"] = old.policy_id
    policy = policy.model_copy(update={"deployment_verified_until": policy.owner_usage.expires_at})
    now = int(old.clock())
    monkeypatch.setenv("AI_API_ONLY_ENABLED", "false")
    asyncio.run(migrate_owner(old, policy))
    control = owner_coordinator(old, policy)
    monkeypatch.setenv("AI_API_ONLY_ENABLED", "true")
    monkeypatch.setenv("AI_PILOT_POLICY_JSON", policy.model_dump_json())
    monkeypatch.setattr(pilot_release.time, "time", lambda: now)
    settings = release_config.model_copy(update={"ai_provider_max_concurrency": 1})
    digest = pilot_release.configuration_digest(settings)
    evidence = {name: {"configuration_sha256": digest, "checked_at": now,
        "checks": {check: True for check in checks}} for name, checks in
        {**pilot_release.CHECKS, "ledger": pilot_release.OWNER_LEDGER_CHECKS}.items()}
    signed = pilot_release.prepare_approval(settings, evidence)
    resource = {"id": "/synthetic/gateway", "identity": {}, "properties": {
        "managedEnvironmentId": "/synthetic/environment", "configuration": {"secrets": []},
        "template": {"containers": [{"env": [{"name": "AI_API_ONLY_ENABLED", "value": "true"},
                                               {"name": "AI_PILOT_ENABLED", "value": "true"}]}]}}}
    documents = {"auth": {"properties": {}}, "backend": {"identity": {}, "properties": {}},
        "storage": {"properties": {}}, "model": {"sku": {}, "properties": {"model": {}, "versionUpgradeOption": "none"}},
        "roles": {"value": []}}
    records = {key: value[0] for key, value in control.store.rows.items() if key.startswith("op-")}
    plan = {"end": policy.owner_usage.expires_at, "configuration_sha256": digest,
        "gateway_sha256": pilot_renewal.sha(pilot_renewal.resource_projection("gateway", resource)),
        "resources": [{"kind": kind, "url": kind, "sha256": pilot_renewal.sha(pilot_renewal.resource_projection(kind, value))}
                      for kind, value in documents.items()],
        "audit_sha256": pilot_renewal.sha(control.store.rows["owner-transition-v1"][0]),
        "operations_sha256": pilot_renewal.sha(records), "acceptance_keys": list(records),
        "fixed_evidence": {name: signed["approval"]["evidence"][name] for name in ("budget", "privacy")}}

    class Cloud:
        def __init__(self):
            self.signed = signed
            self.resource_value = resource
            self.writes = []
            self.gateway_reads = 0
            self.before_publish_check = lambda: None

        def gateway(self):
            self.gateway_reads += 1
            if self.gateway_reads == 2:
                self.before_publish_check()
            return self.resource_value

        def resource(self, url):
            return documents[url]

        def bundle(self):
            return deepcopy(self.signed)

        def cost(self, now):
            return {"properties": {"columns": [{"name": "PreTaxCost"}, {"name": "Currency"}], "rows": [[0.1, "EUR"]]}}

        def publish(self, value):
            self.writes.append(deepcopy(value))
            self.signed = value

        def retire(self):
            self.writes.append("retire_only_own_job")

    return SimpleNamespace(plan=plan, settings=settings, control=control, cloud=Cloud(), now=now)


def run(case):
    return asyncio.run(pilot_renewal.renew_owner(case.plan, case.settings, case.cloud, case.control, clock=lambda: case.now))


def test_renewal_preserves_all_records_budget_privacy_and_period(renewal):
    before = deepcopy(renewal.control.store.rows)
    result = run(renewal)
    assert result["status"] == "renewed" and result["model_requests"] == 0
    assert result["expires_at"] <= min(renewal.now + 86400, renewal.plan["end"])
    assert renewal.control.store.rows == before
    assert len(renewal.cloud.writes) == 1
    assert {name: renewal.cloud.signed["approval"]["evidence"][name] for name in ("budget", "privacy")} == renewal.plan["fixed_evidence"]


@pytest.mark.parametrize("fault", ["disabled", "revoked", "network", "cost", "drift", "blocked", "hold", "audit", "missing"])
def test_failures_publish_nothing_and_preserve_ledger(renewal, monkeypatch, fault):
    if fault == "disabled": renewal.cloud.resource_value["properties"]["template"]["containers"][0]["env"][0]["value"] = "false"
    if fault == "revoked": monkeypatch.setenv("AI_PILOT_RELEASE_KEY", "revoked-synthetic-secret-key" * 2)
    if fault == "network": renewal.cloud.cost = lambda now: (_ for _ in ()).throw(TimeoutError())
    if fault == "cost": renewal.cloud.cost = lambda now: {"properties": {"columns": [{"name": "PreTaxCost"}, {"name": "Currency"}], "rows": [[12, "EUR"]]}}
    if fault == "drift": renewal.plan["gateway_sha256"] = "0" * 64
    if fault == "blocked": renewal.control.store.rows["ledger"][0]["blocked"] = True
    if fault == "hold": renewal.control.store.rows[renewal.plan["acceptance_keys"][0]][0]["charged"] = 0
    if fault == "audit": renewal.plan["audit_sha256"] = "0" * 64
    if fault == "missing": renewal.plan["resources"].pop()
    before = deepcopy(renewal.control.store.rows)
    with pytest.raises((pilot_renewal.RenewalBlocked, PilotError, TimeoutError)):
        run(renewal)
    assert renewal.cloud.writes == []
    assert renewal.control.store.rows == before


@pytest.mark.parametrize("race", ["disable", "revoke", "ledger"])
def test_concurrent_operator_changes_prevent_publication(renewal, race):
    def change():
        if race == "disable":
            renewal.cloud.resource_value["properties"]["template"]["containers"][0]["env"][0]["value"] = "false"
        elif race == "revoke":
            renewal.cloud.resource_value["properties"]["configuration"]["secrets"] = [{"name": "release-key", "keyVaultUrl": "synthetic-new-version"}]
        else:
            record, _ = renewal.control.store.rows["ledger"]
            renewal.control.store.rows["ledger"] = (record, "changed")
    renewal.cloud.before_publish_check = change
    with pytest.raises(pilot_renewal.RenewalBlocked):
        run(renewal)
    assert renewal.cloud.writes == []


def test_period_end_retires_job_without_new_grant(renewal):
    renewal.now = renewal.plan["end"]
    before = deepcopy(renewal.control.store.rows)
    result = run(renewal)
    assert result["status"] == "period_ended"
    assert renewal.cloud.writes == ["retire_only_own_job"]
    assert renewal.control.store.rows == before


@pytest.mark.parametrize("action", ["disable", "revoke"])
def test_operator_stop_after_final_read_cannot_be_undone_by_publication(renewal, monkeypatch, action):
    publish = renewal.cloud.publish

    def stop_then_publish(signed):
        if action == "disable":
            monkeypatch.setenv("AI_API_ONLY_ENABLED", "false")
        else:
            monkeypatch.setenv("AI_PILOT_RELEASE_KEY", "operator-rotated-synthetic-key" * 2)
        publish(signed)

    renewal.cloud.publish = stop_then_publish
    assert run(renewal)["status"] == "renewed"
    import json
    monkeypatch.setenv("AI_PILOT_RELEASE_BUNDLE_JSON", json.dumps(renewal.cloud.signed))
    with pytest.raises(PilotError):
        pilot_release.validate_release(renewal.settings)


def test_expired_job_retires_before_secrets_settings_or_table_access(monkeypatch):
    import json
    from unittest.mock import MagicMock, patch

    cloud = MagicMock()
    monkeypatch.setenv("AI_PILOT_RENEWAL_PLAN_JSON", json.dumps({"end": 1}))
    monkeypatch.setenv("AI_PILOT_RENEWAL_CLIENT_ID", "synthetic-client")
    with patch.object(pilot_renewal, "AzureRenewal", return_value=cloud), \
            patch("azure.identity.ManagedIdentityCredential"), \
            patch("azure.identity.aio.ManagedIdentityCredential") as table_identity, \
            patch("app.config.Settings") as settings:
        assert asyncio.run(pilot_renewal.main_async())["status"] == "period_ended"
    cloud.retire.assert_called_once_with()
    cloud.load_secrets.assert_not_called()
    table_identity.assert_not_called()
    settings.assert_not_called()


def test_cost_failure_has_no_empty_zero_or_foreign_currency_fallback(renewal):
    for rows in ([], [[0.1, "USD"]], [[float("nan"), "EUR"]]):
        renewal.cloud.cost = lambda now: {"properties": {"columns": [{"name": "PreTaxCost"}, {"name": "Currency"}], "rows": rows}}
        with pytest.raises(pilot_renewal.RenewalBlocked):
            run(renewal)
    assert renewal.cloud.writes == []