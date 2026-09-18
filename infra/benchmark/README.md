# Isolated public-data benchmark

Implemented preparation only. No resource provisioning, Table data-plane calls
or paid generations were performed during offline validation. The existing
production API, authentication, readiness, iOS and build numbers are unchanged.
This CLI measures the existing use case, Coordinator and Azure adapter; it does
not claim to validate deployed HTTP ingress, backend Easy Auth or mobile latency.

## Approval and prerequisites

- Explicitly approve this isolated public-endpoint/IP-restricted topology, resource
  inventory, operator, 18-attempt USD 4.2174 model reserve and separate EUR 1
  ancillary planning allowance. Neither allowance is an Azure invoice hard cap.
- Use Python 3.13, the pinned `ai-gateway/requirements.txt` and test dependencies,
  Azure CLI and a normal interactive Entra **user** login in a dedicated
  `AZURE_CONFIG_DIR`. No service-principal secret, API key, SAS or stored application
  credential is used. Azure CLI manages its own normal login/token cache outside
  the repository; use a temporary owner-only directory and log out/remove it after
  the approved session. The runner never exports or saves access tokens.
- Provisioning needs rights to create the listed resources and role assignments.
  Runtime adds only resource-group Reader, account-scoped Cognitive Services OpenAI
  User and table-scoped Storage Table Data Contributor. The lifecycle script also
  requires Microsoft Graph permission to read the signed-in user's object ID.
  Existing inherited Owner permissions are not reduced by these assignments.
- Confirm Sweden Central capacity/minimum/increments for `gpt-5.4-mini`, snapshot
  `2026-03-17`, `DataZoneStandard`. The template requests 1-10 capacity units,
  usually 10; verify the actual TPM/RPM mapping. No automatic region, SKU, model,
  tier or version substitution is permitted. ARM/provider-policy validation and
  actual RBAC/network behavior remain live checks after separate approval.
- Complete [approval.example.json](approval.example.json) outside the repository.
  Placeholders are intentionally invalid. Use a unique immutable run ID (lowercase
  letters/digits/hyphens, <=24 characters), globally unique lowercase account names
  starting `pftbench`, the approved IDs and one global IPv4 address. Set integer
  Unix timestamps with `created_at <= now < expires_at <= created_at + 86400`.
  Choose the window close to execution so setup/tests fit. Do not edit the approval
  after initialization; it is part of the permanent ledger binding.

No host-side credentials are embedded in this repository. Do not pass tokens on
command lines or enable debug HTTP/identity logging. Set the following runtime
flags only in a genuinely local nonproduction shell. They are necessary but not
sufficient: every model case also requires real ARM attestation of the exact
isolated resource IDs/tags, keyless configuration, network rules, pinned deployment,
prices and a matching Entra identity. Renaming `APP_ENV` cannot attest a production
resource. Azure workload-identity environments and auth-bypass flags are rejected.

```sh
export APP_ENV=development AI_PILOT_ENABLED=true
export AZURE_CORE_COLLECT_TELEMETRY=no AZURE_EXTENSION_USE_DYNAMIC_INSTALL=no
```

Set `AZURE_CONFIG_DIR` to the dedicated login directory before normal `az login`.
All commands below run from `ai-gateway/` with its `.venv/bin/python`. `$APPROVAL`
is the external approval JSON path; `$RESULTS` is an external owner-only directory.
Never use the regular app's resource group, configuration or identity assertions.

## Local checks

```sh
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -B -m app.benchmark check
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -B -m app.benchmark_infra plan --approval "$APPROVAL"
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -B -m pytest -q -p no:cacheprovider tests/test_benchmark.py tests/test_openai_api.py tests/test_pilot.py
```

`check` and `plan` make no cloud requests. The plan emits a confirmation digest
binding approval and ARM-template bytes; `$CONFIRMATION` below means that reviewed
digest, not a secret. No arbitrary dataset path or request text is accepted. The
manifest and all eight assets must match their frozen hashes. Requests reuse the
existing FoodAnalysisUseCase builder and validators. Code, dependencies, Python
version, complete prompts/schemas and approval are bound at initialization.

## Separately authorized cloud setup

Do not run this until resource creation is approved:

```sh
.venv/bin/python -B -m app.benchmark_infra provision --approval "$APPROVAL" --apply --confirm "$CONFIRMATION"
```

The subscription-scoped [ARM template](main.json) creates:

- `rg-pft-mini-bench-<run_id>` in Sweden Central, with purpose/run/manifest/expiry tags.
- One OpenAI S0 account/custom subdomain, local authentication disabled, one
  `mini-bench` DataZoneStandard deployment, exact version, `NoAutoUpgrade`.
- One StorageV2 Standard_LRS account and `MiniBenchmark` Table; Shared Key and
  anonymous blob access disabled, TLS 1.2+, HTTPS only, Microsoft-managed account
  encryption for Table data. Budget the account-encrypted meter alternative.
- Default-deny firewalls on both services, one public IPv4 rule, no broad trusted
  Azure service bypass. These are restricted public endpoints, not Private Link.
- Three scoped user role assignments described above and ARM deployment records.

No Functions, Container Apps, ACR, VM, Foundry project, private networking, logging
workspace or production resources are created. Provision refuses an existing RG
to avoid mutating/reinitializing a previous run. An interrupted deployment requires
manual inspection of its exact resource IDs before continuation; do not choose a
new run ID to evade consumed attempts. There is no automatic deployment retry.

## Real Table tests, no model calls

After separate authorization for Table writes, use the real approval and login:

```sh
RUN_BENCHMARK_TABLE_TESTS=1 BENCHMARK_APPROVAL_FILE="$APPROVAL" \
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -B -m pytest -q -p no:cacheprovider tests/test_benchmark_table_integration.py
```

These tests perform read-only ARM/price attestation and real Table operations in
random `test-` partitions. They never construct a model provider. They cover two
clients, claim/reservation races, duplicate initialization, simulated lost write
acknowledgement backed by a real committed transaction, restart, settlement,
40-day virtual rollover, lifetime 18-limit, and cleanup retaining unknown totals.
They delete only their own random partitions. An externally killed test may leave
a `test-` partition; inspect and remove only that partition. Simulation of lost
acknowledgement is not a physical network-fault or regional outage experiment.
The production Managed Identity Table test remains a separate opt-in test.

## Initialize once, then run one case

Freeze reviewed code and obtain the separate paid-run approval first. Initializing
does not call a model, but writes the live benchmark ledger:

```sh
.venv/bin/python -B -m app.benchmark init --approval "$APPROVAL"
.venv/bin/python -B -m app.benchmark next --approval "$APPROVAL" --results "$RESULTS"
```

`init` atomically creates the ledger, run state and 18 fixed case/UUIDv7 mappings.
Existing, partial or ambiguously acknowledged initialization is never overwritten.
`next` executes at most **one** new case. Re-run it explicitly only after a known
success and at least 60 seconds; there is no retry loop or warmup. Each invocation
uses a new process/connection, so latency is recorded as `cold`; no warm-service or
p95 claim is made. Attestation is repeated before every invocation and must still
be less than 30 seconds old at dispatch/token acquisition. ARM is not an atomic
lock on deployment changes; returned model/tier and usage are independently checked.
JWT claims bind tokens to the expected user/tenant/audience; Azure services validate
the bearer tokens. Local unverified JWT decoding alone is not authentication.

Before reservation the run is CAS-claimed `busy`. Competing or restarted processes
cannot take it over. Every prior result must still match its durable case hash.
The original Coordinator remains the only budget/permit/dispatch authority. A
single-use permit binds the request, profile, prices and output cap. SDK retries,
redirects, fallback, repair and LLM judging are disabled. The first real case is
the compatibility check and counts within 18; no separate paid smoke test exists.

Only after known settlement and an fsynced exclusive result file does the run move
to its next case. Unknown usage, any error, drift, lost result, uncertain Table
acknowledgement or process interruption prevents further dispatch. `busy` has no
timeout/lease takeover. There is no resume-unknown, skip, reset, replacement-ID or
budget-refill command. A stopped matrix may be incomplete; review it as such.

## Results and quality

`$RESULTS/<run_id>` must be outside the repository and owner-only (0700); result
files are exclusive 0600, never overwritten. They contain only this approved
public/synthetic dataset's validated estimates, numeric quality checks, timings,
raw usage counts, independently settled known costs, retained reserves and generic
error codes. No raw provider bodies, credentials or private meal input are stored.
The durable Table stores control metadata/hashes, not estimates or images. Runtime
logs remain content-free. A disk failure leaves the run blocked, not replayable.
If Table reads fail after a possible dispatch, locally available usage is still
recorded with unknown settled cost. `reserve_exposure_usd` keeps the conservative
maximum exposure even when the actual retained reservation cannot be read.

Record human review alongside an immutable result with scores 0 (fails) through
4 (fully meets criterion); omit inapplicable dimensions, never mark an unreviewed
result usable. A transport failure alone is not successful P5 abstention:

```sh
.venv/bin/python -B -m app.benchmark review --result "$RESULTS/<run_id>/P1.json" \
  --usable yes --portion 3 --nutrition 3 --uncertainty 4
```

The review sidecar references the original result hash. There is no free-text
input in this command. Review all 17 estimation cases and P5 separately. Photo
portions are unknown; **no exact calorie or macro ground truth** is assigned.
Labels/text/refinements use declared arithmetic and preregistered tolerances.
Six photo variants come from three sources, not six independent meals. Preserve
the [licenses and reference notes](../../ai-gateway/tests/fixtures/gpt54-mini-assets/README.md).
Include failures in attempt/spend totals. Report known cost plus retained unknown
reserve, not unknown-as-zero; quality and cost per usable result require completed
human review. One pass is screening, not statistical accuracy or p95 proof.

## Stop and retain, then destroy

After a completed/stopped run or expiry, the separately approved stop command
atomically closes the run/blocks its ledger, then deletes the OpenAI account and
deployment. It works with the original expired approval; its cleanup credential
can request only Table tokens, never model tokens:

```sh
.venv/bin/python -B -m app.benchmark_infra stop --approval "$APPROVAL" --apply --confirm "$CONFIRMATION"
```

Keep the Table, scoped reviewer/operator role and restricted network access for
at least **31 days from closure** (2,678,400 seconds), longer for unknowns. The
same approved owner is the runner and reviewer; the cleanup script does not create
a second principal. Do not run tombstone cleanup on the benchmark partition. The
permanent counters are never reduced, including at expiry or month boundaries.
Provider deletion/revocation does not undo already in-flight calls or billed cost.
Do not run stop concurrently with an active case; interruption requires inspection.

Only a closed run with elapsed retention, a complete operation inventory, no
active/pending/unknown operations and known settlement can be destroyed. The
command first fsyncs a restricted, permanent closed-run control archive outside
the repo, then deletes the exact isolated RG including storage and roles:

```sh
.venv/bin/python -B -m app.benchmark_infra destroy --approval "$APPROVAL" \
  --archive "$ARCHIVE_DIR/<run_id>.json" --apply --confirm "$CONFIRMATION"
```

The archive directory must be 0700. Keep it so deleted infrastructure cannot be
mistaken for a new unused budget. Unknown or missing records **block destruction**;
operator reconciliation/extended retention needs a separate review, never a fresh
ledger. No automatic reconciliation or force-delete flag is provided. If archive
creation succeeds but deletion fails, inspect the cloud before continuing manually;
the script will not overwrite the archive. Azure may retain account soft-delete
metadata and ARM deployment history; no purge of that history is performed here.

The EUR 1 ancillary envelope must include 31-day storage retention, Table test and
runtime transactions, network transfer, FX/tax and any extension. It is not enforced
by Azure billing. No hosting or log ingestion charges are intentionally introduced.
After review, remove the local synthetic result artifacts according to the approved
retention; retain the nonsecret closed-run archive and licensed fixture provenance.