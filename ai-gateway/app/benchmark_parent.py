"""Same-partition cumulative CAS accounting for one closed benchmark continuation."""

from copy import deepcopy
from dataclasses import asdict
from decimal import Decimal
import json
from pathlib import Path
import secrets
import time
from uuid import UUID

from app.benchmark import Approval, RunState, code_hash, load_cases, make_coordinator, sha
from app.benchmark_continuation import continuation_plan
from app.benchmark_diagnostics import BenchmarkDiagnostics
from app.pilot import PilotError, digest, units
from app.providers.pricing import GPT_54_MINI


PARENT_KEY = "continuation-parent-v1"
PREFIX = "continuation-v1-"
RESERVE = units(GPT_54_MINI.reserve_usd(2000))


class ParentStore:
    parent_key = PARENT_KEY
    prefix = PREFIX

    def __init__(self, store, directory, *, cleanup=False):
        self.store, self.directory = store, Path(directory)
        self.plan = continuation_plan(directory, cleanup=cleanup)
        self.approval = Approval.model_validate_json((self.directory / "approval.json").read_text())
        requests = {case["id"]: (case, request) for case, request in load_cases()[1]}
        self.cases = [requests[item["case_id"]] for item in self.plan["queue"]]
        self.binding = sha(["continuation-v1", self.plan["parent_binding"], self.plan["parent_result_hashes"],
                            self.plan["snapshot_sha256"], code_hash(), self.plan["queue"]])
        self.diagnostics = getattr(store, "diagnostics", BenchmarkDiagnostics())
        self.control = make_coordinator(self, self.approval)
        self.state = RunState(self, self.control, self.approval, self.cases)

    async def parent(self):
        parent, etag = await self.store.read(self.parent_key)
        if (not parent or parent.get("binding") != self.binding
                or type(parent.get("slots")) is not int or not 5 <= parent["slots"] <= 18
                or parent.get("technical_reserved") != parent["slots"] * RESERVE
                or parent.get("t5_reserve") != RESERVE
                or parent.get("state") == "closed"):
            raise PilotError()
        return parent, etag

    def key(self, key):
        if key not in {"ledger", "benchmark", *("case-" + case["id"] for case, _ in self.cases)} and not (
                key.startswith("op-") and len(key) == 67 and all(character in "0123456789abcdef" for character in key[3:])):
            raise PilotError()
        return self.prefix + key

    async def read(self, key):
        return await self.store.read(self.key(key))

    async def adopt(self):
        self.approval.check_window()
        snapshot = json.loads((self.directory / "closed-ledger-snapshot.json").read_text())["records"]
        changes = []
        for record in snapshot:
            actual, etag = await self.store.read(record["key"])
            if etag is None or actual != record["data"]:
                raise PilotError()
            changes.append((record["key"], actual, etag))
        previous = {record["key"]: record["data"] for record in snapshot}
        ledger = deepcopy(previous["ledger"])
        ledger.update(blocked=False, last_time=max(ledger["last_time"], previous["benchmark"]["closed_at"]))
        ledger["benchmark"].update(attempts=5, reserved=5 * RESERVE)
        for bucket in ledger["buckets"].values():
            bucket["count"] += 1
            bucket["cost"] += RESERVE
        parent = {"version": 1, "binding": self.binding, "state": "idle", "slots": 5,
                  "technical_reserved": 5 * RESERVE, "t5_reserve": RESERVE,
                  "known_cost": units(Decimal(self.plan["aggregate"]["known_model_cost_usd"])),
                  "unknown_reserve": RESERVE, "inflight": None, "cursor": 0,
                  "parent_approval_hash": self.plan["parent_approval_hash"],
                  "snapshot_sha256": self.plan["snapshot_sha256"], "created_at": int(time.time())}
        run = {"binding": self.state.binding, "state": "idle", "cursor": 0,
               "not_before": previous["benchmark"]["closed_at"] + 60,
               "run_id": self.approval.run_id, "initialized": True,
               "approval_hash": self.plan["parent_approval_hash"], "parent_binding": self.binding}
        changes += [(self.parent_key, parent, None), (self.key("ledger"), ledger, None),
                    (self.key("benchmark"), run, None)]
        for case, request in self.cases:
            operation = UUID(int=(int(time.time() * 1000) << 80) | (7 << 76)
                             | (secrets.randbits(12) << 64) | (2 << 62) | secrets.randbits(62))
            changes.append((self.key("case-" + case["id"]), {
                "operation": str(operation), "request_hash": sha(asdict(request)), "state": "ready"}, None))
        await self.store.commit(changes)

    async def commit(self, changes):
        parent, parent_etag = await self.parent()
        values = {key: data for key, data, _ in changes}
        if len(values) != len(changes) or any(etag is None for key, _, etag in changes if not key.startswith("op-")):
            raise PilotError()
        run = values.get("benchmark")
        operations = [key for key in values if key.startswith("op-")]
        if run is not None:
            if parent["cursor"] >= len(self.cases):
                raise PilotError()
            case, request = self.cases[parent["cursor"]]
            case_key = "case-" + case["id"]
            if set(values) != {"benchmark", case_key} or run.get("binding") != self.state.binding:
                raise PilotError()
            record = values[case_key]
            if record.get("request_hash") != sha(asdict(request)):
                raise PilotError()
            if run["state"] == "busy":
                self.approval.check_window()
                if (parent["state"] != "idle" or parent["inflight"] is not None
                        or parent["slots"] >= 18 or run["cursor"] != parent["cursor"] or record["state"] != "started"):
                    raise PilotError()
                parent["slots"] += 1
                parent["technical_reserved"] += RESERVE
                parent["unknown_reserve"] += RESERVE
                parent["state"] = "claimed"
                parent["inflight"] = {"case_id": case["id"], "operation": "op-" + digest(
                    self.control.secret, "operation", [self.approval.identity, record["operation"]]),
                    "fingerprint": digest(self.control.secret, "request", asdict(request))}
            else:
                if (parent["inflight"] is None or record["state"] != "finished"
                        or run["cursor"] != parent["cursor"] + 1 or not record.get("result_hash")
                        or run["state"] not in {"idle", "completed", "halted"}
                        or run["state"] != "halted" and parent["state"] != "settled"):
                    raise PilotError()
                parent["state"] = run["state"]
                parent["cursor"] += 1
                if run["state"] != "halted":
                    parent["inflight"] = None
        elif len(operations) == 1:
            key = operations[0]
            record = values[key]
            if (not parent["inflight"] or parent["inflight"]["operation"] != key
                    or record.get("fingerprint") != parent["inflight"]["fingerprint"] or record.get("reserved") != RESERVE):
                raise PilotError()
            if set(values) == {"ledger", key}:
                ledger = values["ledger"]
                if ledger["benchmark"] != {"run_id": self.approval.run_id, "attempts": parent["slots"],
                                           "reserved": parent["technical_reserved"]}:
                    raise PilotError()
                if record["state"] == "pending" and not record.get("settled"):
                    self.approval.check_window()
                    if parent["state"] != "claimed":
                        raise PilotError()
                    parent["state"] = "reserved"
                elif record.get("settled") is True and parent["state"] == "dispatched":
                    if record.get("usage_known") is True:
                        if type(record.get("charged")) is not int or record["charged"] < 0:
                            raise PilotError()
                        parent["known_cost"] += record["charged"]
                        parent["unknown_reserve"] -= RESERVE
                    parent["state"] = "settled" if (record["state"] == "succeeded"
                        and record.get("usage_known") is True and not ledger["blocked"]) else "halted"
                else:
                    raise PilotError()
            elif set(values) == {key} and record["state"] == "unknown" and not record.get("settled"):
                self.approval.check_window()
                if parent["state"] != "reserved":
                    raise PilotError()
                parent["state"] = "dispatched"
            else:
                raise PilotError()
        else:
            raise PilotError()
        await self.store.commit([(self.key(key), data, etag) for key, data, etag in changes]
                                + [(self.parent_key, parent, parent_etag)])

    async def close(self):
        parent, parent_etag = await self.parent()
        run, run_etag = await self.read("benchmark")
        ledger, ledger_etag = await self.read("ledger")
        now = int(time.time())
        parent.update(state="closed", closed_at=now, purge_after=now + 2678400)
        run.update(state="closed", closed_at=now, purge_after=now + 2678400)
        ledger["blocked"] = True
        await self.store.commit([(self.parent_key, parent, parent_etag), (self.key("benchmark"), run, run_etag),
                                 (self.key("ledger"), ledger, ledger_etag)])
        return parent


class FinalParentStore(ParentStore):
    parent_key = "final-parent-v1"
    prefix = "final-v1-"

    def __init__(self, store, directory, *, cleanup=False):
        from app.benchmark_continuation import final_continuation_plan

        self.store, self.directory = store, Path(directory)
        self.plan = final_continuation_plan(directory, cleanup=cleanup)
        self.approval = Approval.model_validate_json((self.directory / "approval.json").read_text())
        requests = {case["id"]: (case, request) for case, request in load_cases()[1]}
        self.cases = [requests[item["case_id"]] for item in self.plan["queue"]]
        self.binding = sha(["final-v1", self.plan["predecessor_binding"], self.plan["predecessor_snapshot_sha256"],
                            self.plan["predecessor_result_hashes"], code_hash(), self.plan["queue"], 11, 2 * RESERVE])
        self.diagnostics = getattr(store, "diagnostics", BenchmarkDiagnostics())
        self.control = make_coordinator(self, self.approval)
        self.state = RunState(self, self.control, self.approval, self.cases)

    async def parent(self):
        parent, etag = await super().parent()
        if (parent["slots"] < 11 or parent.get("r2_reserve") != RESERVE
                or parent.get("unknown_reserve", 0) < 2 * RESERVE
                or parent.get("predecessor_snapshot_sha256") != self.plan["predecessor_snapshot_sha256"]):
            raise PilotError()
        return parent, etag

    async def adopt(self):
        self.approval.check_window()
        snapshot = json.loads((self.directory / "continuation-closed-snapshot.json").read_text())["records"]
        changes = []
        for record in snapshot:
            actual, etag = await self.store.read(record["key"])
            if etag is None or actual != record["data"]:
                raise PilotError()
            changes.append((record["key"], actual, etag))
        previous = {record["key"]: record["data"] for record in snapshot}
        ledger = deepcopy(previous[PREFIX + "ledger"])
        ledger.update(blocked=False, last_time=max(ledger["last_time"], previous[PARENT_KEY]["closed_at"]))
        ledger["benchmark"].update(attempts=11, reserved=11 * RESERVE)
        for bucket in ledger["buckets"].values():
            bucket["count"] += 1
            bucket["cost"] += RESERVE
        parent = {"version": 2, "binding": self.binding, "state": "idle", "slots": 11,
                  "technical_reserved": 11 * RESERVE, "t5_reserve": RESERVE, "r2_reserve": RESERVE,
                  "known_cost": previous[PARENT_KEY]["known_cost"], "unknown_reserve": 2 * RESERVE,
                  "inflight": None, "cursor": 0, "parent_approval_hash": self.plan["parent_approval_hash"],
                  "predecessor_snapshot_sha256": self.plan["predecessor_snapshot_sha256"], "created_at": int(time.time())}
        run = {"binding": self.state.binding, "state": "idle", "cursor": 0,
               "not_before": previous[PREFIX + "benchmark"]["closed_at"] + 60,
               "run_id": self.approval.run_id, "initialized": True,
               "approval_hash": self.plan["parent_approval_hash"], "parent_binding": self.binding}
        changes += [(self.parent_key, parent, None), (self.key("ledger"), ledger, None), (self.key("benchmark"), run, None)]
        for case, request in self.cases:
            operation = UUID(int=(int(time.time() * 1000) << 80) | (7 << 76)
                             | (secrets.randbits(12) << 64) | (2 << 62) | secrets.randbits(62))
            changes.append((self.key("case-" + case["id"]), {
                "operation": str(operation), "request_hash": sha(asdict(request)), "state": "ready"}, None))
        if len(changes) > 100:
            raise PilotError()
        await self.store.commit(changes)