# Isolated public-data benchmark

The prepared workflow supports separately authorized real execution. Offline
validation never provisions resources or calls paid models. The existing
production API, authentication, readiness, iOS and build numbers are unchanged.
This CLI measures the existing use case, Coordinator and Azure adapter; it does
not claim to validate deployed HTTP ingress, backend Easy Auth or mobile latency.

## Approval and prerequisites

- Explicitly approve this isolated public-endpoint/IP-restricted topology, resource
  inventory and operator. The current operational threshold is EUR 10 including
  tax, FX, retention and cleanup, with explicitly accepted delayed-billing risk.
  The technical 18-attempt USD 4.2174 model reserve is unchanged. Approval reserves
  EUR 1.20 per USD, a 1.50 tax multiplier and EUR 2 ancillary allowance, totaling
  EUR 9.59132 worst-case planning exposure. These are not invoice guarantees.
  Verify current rates and stop new work if the total projection exceeds EUR 10.
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
Set `BENCHMARK_CONTROL_DIR` to a permanent external owner-only directory (0700).
Its append-only Table admission log is bound to the approval and must never be
removed/reset while resources remain. Across tests, runs and restarts, it limits
normal work to 2,500 requests / 40,000 conservative operation units and reserves
another 500 requests / 10,000 units for cleanup. This is not Azure billing data.
Create it exactly once with the offline `prepare-control` command below, before
the first Table test/access. Requests never recreate a missing counter. Existing
logs from the completed screening remain compatible; do not initialize them again.
Missing, damaged, linked, insecurely permissioned or locked logs block access,
including cleanup. Review such failures without deleting/replacing the log.

The nonblocking local `flock` protects only the synchronous read/validate/append/
file-and-directory-sync critical section, not an entire Table transaction or
benchmark case. It is explicitly released in `finally` before HTTP, including
error/cancellation paths, even if a duplicate descriptor remains open. There is
no persistent lock record to expire. Process exit releases the kernel lock when
all owning descriptors close; a closed benchmark row cannot keep it held.
`counter_locked` now means acquisition contention only; other OS failures are
`counter_io`. Before this correction, sync `BlockingIOError` could be mislabeled
as contention, so old diagnostics do not establish a holder. Appends are unbuffered
and length-checked; short writes stop before HTTP and damaged logs stay fail-closed.
Neither a failure nor a CAS conflict refunds an appended request charge.
Table ETags cannot replace this lock: they do not serialize the local shared
quota or account for reads/failed requests. Never unlock another operation's
descriptor, steal/remove a lock, reset the log or replay an uncertain request.

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

For a newly approved allocation only, initialize its local counter once:

```sh
.venv/bin/python -B -m app.benchmark_infra prepare-control --approval "$APPROVAL" --apply --confirm "$CONFIRMATION"
```

This makes no cloud requests and requires the reviewed confirmation. It is not a
recovery/reset procedure. A different directory or run ID does not create another
budget under an existing authorization. The fixed continuation mechanisms below
carry earlier attempts, reserves and ancillary costs through reviewed aggregate
checkpoints; they are not arbitrary new run IDs or additional allowances.

## Final-round handoff and bounded prices

The authorized round is now **closed and exhausted**: seven attempts, six valid
answers and one T6 refusal with unknown usage, without retries. Five new criteria
pass, P3 is partial and T6 does not pass. Model deployment/account and model role
are verified absent; the dedicated Azure profile is logged out. The following
describes the executed mechanism, not permission to resume it.

The authorized final round uses `--final-round` on `continuation-adopt`,
`continuation-next`, `continuation-stop` and model-only `benchmark_infra restore`.
It has one fixed namespace and exactly P3, P4, R3, R4, P5, P6, T6, preserving the
original requests. Neither closed predecessor can resume. Adoption verifies all
45 predecessor payloads and their ETags in the same transaction as the new child.
Seed 11 consumed slots, USD 2.5773 technical allocation, USD 0.01084875 known
usage and both USD 0.2343 T5/R2 holds. Seven additional claims exhaust the original
18-slot / USD 4.2174 technical ceiling. The inherited Parent-CAS state machine,
single-use permits, minute spacing, unknown-state halt and zero model retries
are unchanged. Existing consumed markers are not removed or reused.

Before adoption, the new isolated Table handoff test checks competing claims,
second adoption, unknown settlement, reconstructed control state and unchanged
closed predecessors. It uses at most 250 requests / 1,400 normal units, with
4,200 normal units still reserved in planning for actual adoption and seven
cases. Its own known keys are tracked before writes and deleted in `finally`;
a failed cleanup blocks model restoration. It never constructs a model provider.

**A live Retail lookup is not a security boundary.** The original large Storage
filter returned HTTP 404; its 31-meter shortened variant returns HTTP 400 with
`Invalid OData parameters supplied`. A three-meter query succeeds, but returns
93 items across regions/SKUs. This identifies a query-shape problem, not unknown
unlimited charges; it does not establish the exact OData parser limit. Do not
use foreign-region or ZRS entries as LRS rates. Preserve bounded response bodies,
query identity, status and source timestamps before checking success. Small
queries need exact region/SKU/unit/currency validation and pagination checks.

For this final round, `final-price-basis.json` selects a previously verified
`continuation-resource-review.json`, bound by SHA-256 and the original approval.
It records source URL, verification time through the source, Sweden Central,
Standard_LRS / DataZoneStandard, units/currencies, uncertainty and unknown posted
billing. The source must be no older than six hours; expiry is the earlier of
that deadline and the **unchanged original approval expiry**. Altered evidence,
missing meters, wrong units/region/SKU, stale or future-dated evidence and a
projection exceeding the existing reserves reject execution. Source age means
time since verification, not the tariff's older effective-start date.

Use the verified USD 0.825 / 0.0825 / 4.95 per million model-token rates and the
conservative primary LRS maxima EUR 0.1005 per 10,000 Table units and EUR 0.0502
per GB-month, with **10% additional tariff uncertainty**. No rate is invented.
Full existing consumption bounds, including earlier requests and cleanup, give:

```text
ancillary = ((5 * 0.1005 + 0.0502) * 1.10 + 0.50) * 1.50 * 1.20
          = EUR 1.994346 <= the existing EUR 2 reserve
seven-case maximum = 2 + (0.01084875 + 9 * 0.2343) * 1.10 * 1.50 * 1.20
                   = EUR 6.196706525 <= the existing EUR 10 authorization
```

The nine reserves in the projection are both holds plus seven additional calls.
The EUR 0.50 transfer allowance, one GB-month retention, 50,000 total weighted
Table units and tax/FX reserves are unchanged. Weighted units conservatively
charge scans/batches and failed HTTP attempts; they are not posted transactions.
No missing invoice is interpreted as zero, no third billing query is consumed
and neither a per-child budget nor a new authorization is introduced.

Each dispatch still performs full **live** identity and ARM attestation of exact
resource IDs/tags, keyless configuration, IP rules and pinned deployment, then
validates the bounded price basis. A valid basis removes Retail availability
from that path; it does not bypass identity, resources, ledger or budget gates.
This is a conservative operational plan with accepted billing delay, not a hard
invoice guarantee. Retention and eventual cleanup remain part of the same budget.

Final accounting: eighteen slots / USD 4.2174 lifetime allocation, USD 0.01829025
known model cost, three USD 0.2343 holds (T5, R2, T6), and EUR 3.427956695 buffered
exposure including the full EUR 2 ancillary reserve. T6 is retained active/unknown
in a blocked ledger and closed run; do not clear it or call that state a retry grant.
Counter is 1,670 requests / 39,281 units. Retained Table/Storage cleanup review is
no earlier than **2026-10-19 18:55:12 UTC**; no automatic deletion job exists.
The historical archive gap and uncertainties require reconciliation before removal.
Full findings and limitations are in the [final assessment](../../docs/benchmark-review-2026-09-18.md#final-round-assessment).

## Historical continuation preparation

An earlier seven-case preparation stopped on the bad Retail queries, without
creating a model, run, test partition or case claim. Its own draft was privately
archived and reverted. That history is retained, but the price failure was not
evidence of unbounded cost: the diagnosed query and reviewed, bounded final-round
mechanism above supersede that stop. See the
[current assessment](../../docs/benchmark-review-2026-09-18.md) for actual results,
remaining uncertainty, cumulative cost and the final cleanup checkpoint.
No automatic deletion job exists; the historical archive gap still prevents
blind destruction or counter resets.

The following preparation history is superseded operationally by the closed
[authorized continuation outcome](../../docs/benchmark-review-2026-09-18.md#authorized-continuation-outcome).
Five new calls succeeded; R2 stopped on a local `counter_locked` claim, without
retry. Both runs are closed and the model resource has been deleted. Commands
below describe the reviewed mechanisms, not permission to resume this run.

The [reassessed review](../../docs/benchmark-review-2026-09-18.md) separates direct
historical observations from code inference and reproduction. The earlier local
T5 reserve release is superseded for planning: retain USD 0.2343 and five consumed
case slots. Original results, approval, closure snapshot and reconciliation remain
immutable. T2 remains a failed quality case, not a reason to rerun or change prompts.

An executable **offline** command creates an exclusive owner-only proposal:

```sh
.venv/bin/python -B -m app.benchmark continuation-plan --evidence "$EVIDENCE" --output "$PLANS"
```

`$EVIDENCE` is the existing private run directory containing the original approval,
results, closed snapshot, counter and `analysis-baseline.json`; `$PLANS` is an
external 0700 directory. This command never loads credentials, attests resources,
creates cloud state or calls a provider. It verifies baseline hashes, parent/run
binding, all 18 request hashes, four settled operations, five finished cases and
T2's failed protein check. It rejects altered evidence, counter truncation or
exhaustion. Append-only counter growth is accepted and carried forward. The
baseline is local operator evidence, not a signature or execution authority.

The proposal explicitly has `execution_authorized=false`. It carries:

- 18 aggregate case slots; 5 already consumed; no more than 13 additional cases.
- USD 0.003774375 known model cost plus USD 0.2343 uncertain T5 allowance.
- USD 1.1715 conservative technical allocation for the first five slots; add at
  most USD 3.0459 for thirteen further slots, never exceed USD 4.2174 lifetime.
- EUR 2 shared ancillary/retention/cleanup allowance, not a new allowance per child.
  Projection: EUR 2.428533875 before new calls, EUR 7.911153875 for all thirteen,
  using 1.20 EUR/USD and 1.50 tax reserve. Actual billing remains unknown.
- Original counter consumption (at review: 429 requests / 15,720 units). Normal
  remaining headroom: 2,071 requests / 24,280 units; cumulative cleanup ceiling
  remains 3,000 / 50,000. Never initialize another counter for the continuation.
- Queue: P1, L1, R1, P2, L2, R2, P3, P4, R3, R4, P5, P6, T6. Requests retain the
  original hashes; T1-T5 are not replayed. Photos/labels/refinements come first.

### Smallest later Table diagnostic

The separately authorized one-shot read has now completed successfully. Its
exclusive start marker prevents repeating it. Generic command:

```sh
.venv/bin/python -B -m app.benchmark_probe --evidence "$EVIDENCE" --apply
```

Implemented safeguards:

1. Use the original approval, retained Storage account/Table, same restricted IP,
  tenant/user and original counter. No model account, deployment or new role is
  needed. Use the cleanup-mode `CheckedCredential` solely to allow expired
  approval for **storage tokens only**, but the **normal**, not cleanup, Table
  request allowance. Record a create-once local probe-start marker before access.
2. Construct `BenchmarkTableClient` with `retry_total=0`, `redirect_max=0`, the
  original `TableRequestBudget`, disabled SDK logger and 2s connect/3s read limits.
  Wrap it in `BenchmarkTableStore`, with the same diagnostics instance as the
  credential. Perform exactly one `read("ledger")` in the original benchmark
  partition (outer 5s timeout), then close client/credential. No scan, writes,
  case claim, retry, model token or provider construction.
3. Save an exclusive private receipt containing safe diagnostics and whether the
  canonical ledger hash matches the preserved closed snapshot. Do not print
  ledger contents, request IDs, tokens or exception text. Missing or mismatching
  ledger stops work; do not repair/reset it. Even failures consume any admitted
  request units. If the process dies, its started marker prohibits an automatic
  retry. The local probe must not call `prepare-control`.
4. A success establishes current read access only; it cannot retroactively prove
  what T5 returned or test CAS writes. A 401/403, acquisition, claim-validation,
  transport, timeout, decode/local or counter failure is now distinguishable.
  Only if that result leaves a demonstrated transaction issue should a separately
  approved, bounded create/read/ETag-conflict/delete test in a disposable `test-`
  partition follow. Never experiment on the closed benchmark records.

### Implemented cumulative parent ledger

`ParentStore` now wraps the existing Coordinator store without changing production
admission. `init`/`next` are not continuation commands. The reviewed implementation
uses `continuation-adopt`, `continuation-next` and `continuation-stop`, each with
`--evidence "$EVIDENCE" --apply`. The original continuation has one fixed child;
the final-round flag selects the second fixed handoff described above, never a
caller-selected run ID or partition. Original approval/window remain binding;
this implementation does not authorize execution after that window expires.

1. Create-once parent authorization record in the retained Table, in the original
  partition shared by old and continuation control records. Bind the original
  approval hash, closed snapshot/result hashes, reviewed evidence, plan digest,
  allowed thirteen case/request hashes and exactly one approved child allocation.
  Seed consumed slots=5, technical allocation=1.1715 USD, known cost and full T5
  allowance. Adoption reads and compares all original rows, then submits their
  identical payloads with original ETags together with all new parent/child rows
  in one transaction. Their service ETags change, but closed payloads/counters
  remain identical; the transaction rejects concurrent changes or second adoption.
  No cross-partition atomicity is assumed.
2. In one ETag/CAS transaction, reserve the next unique case plus increment parent
  slots/lifetime allocation and set parent in-flight. Child run IDs are metadata,
  not counter partitions. An unlisted child/request, second initialization, stale
  ETag, missing parent, >=18 slots, >4.2174 USD technical allocation, exhausted
  original Table quota or >10 EUR total exposure rejects admission before permit.
  Admission must fail if the reviewed code/request/price/approval hashes changed.
3. Only that acknowledged parent transaction can authorize the existing single-use
  provider permit. Retain ordinary minute/day/month/concurrency/output/attestation
  and identity gates as additional restrictions. A lost reserve/dispatch/settle
  acknowledgement remains consumed and blocks further calls. No retries or
  takeover after unknown state. Settlement can replace financial allowance with
  known usage, never reduce slot count or lifetime technical allocation.
4. Reconcile current resources and billing/FX/tax/retention before allocation.
  Existing storage and its eventual cleanup belong to this same budget. Model-only
  `benchmark_infra restore` derives only the account, pinned deployment and
  account-scoped role from the original template, with `restore=true`; it cannot
  reprovision Storage. Its exclusive marker prevents a second submission.
  If the extended-retention projection no longer fits EUR 2 ancillary
  or EUR 10 total, stop rather than opening another budget. Earlier billing
  queries remain consumed; no unbounded polling or new query allowance.
5. Regression gates before execution: competing children cannot oversubscribe the
  13 slots; lost acknowledgements/restarts/month rollover never refill slots;
  changing child ID cannot obtain credit; unknown usage retains reserve; prior
  artifact mutation and changed request/model policy reject; original closed
  rows are unchanged. Finish/stop the child, delete its model resource, and retain
  the shared authorization/evidence without lowering counters.

The proposal remains offline and is not a permit. Execution additionally requires
fresh code-bound resource/cost evidence, the matched one-shot read and three passed,
cleaned real-Table scenarios. Adoption/dispatch still require live attestation.
Claims charge the parent slot/reserve before provider admission; reservation,
dispatch marker and settlement each update parent and child in one transaction.
Uncertain outcomes cannot be taken over. A claim rejected before commit produces
no durable slot: record that attempted case privately and stop, never treat it as
free retry credit. Original counter/cleanup headroom remain shared.

`continuation-stop` uses storage-only credentials even after expiry, closes parent
and child atomically, saves an immutable snapshot, then deletes deployment and
account. Model deletion is attempted even if ledger closure fails; every outcome
must be inspected. Storage is retained. Unknown records and the historical archive
gap still forbid automatic destruction. The operator supplies the existing
explicit authorization; local evidence files are not signed approval credentials.

The three real parent tests are selected with `-k real_parent_cas` in
`tests/test_benchmark_table_integration.py`, using the original control directory
and approval. They create only bounded `test-parent-` partitions and delete those
with ETags. Start/result markers prevent rerunning a scenario inadvertently.
The earlier `test_real_benchmark_table` scenarios are not part of continuation
execution and must not be selected as additional unbudgeted testing.

### Completed counter lifecycle investigation

The follow-up from `9437833` is complete, with no model/resource operations.
See the [investigation report](../../docs/benchmark-review-2026-09-18.md#counter-lifecycle-investigation-from-9437833)
for reproduced defects versus unknown historical attribution and the live receipt.
The original counter now stands at 1,203 requests / 33,162 weighted units, leaving
1,297 / 6,838 for normal work and the protected 500 / 10,000 cleanup allowance.
Both closed runs and both uncertainty holds are unchanged. This is not a retry grant.

`test_real_counter_lifecycle` in `tests/test_benchmark_table_integration.py` uses
Storage-only checked credentials, the original normal counter and six random
`test-lock-` partitions. Its exclusive start/result markers are already consumed.
Do not rerun or delete them. The fresh private cost review binds the approval,
runtime, test source and counter prefix; it creates no budget. The test adds caps
of 480 requests / 11,980 units within the reviewed total 500 / 12,000 allowance,
leaving room for the twelve fixed original-ledger comparison reads. It forbids
model attestation/provider construction, uses no SDK HTTP retry or redirect and
deletes only known test rows with ETags. A failure stops further scenarios; any
incomplete test cleanup must be reviewed, never recovered by resetting the counter.

For local regression validation only, clear live environment flags and use:

```sh
RUN_BENCHMARK_TABLE_TESTS=0 .venv/bin/python -B -m pytest tests/test_benchmark.py -k 'table_budget or table_counter_lock or counter_lifecycle_scenarios' -q -p no:cacheprovider
```

The six lifecycle scenarios run against MemoryCAS offline. Live evidence covers
18 full simulated operations, concurrency/ETags and faults around real commits,
but application-state reconstruction is not a live OS-process crash test. Local
subprocess tests separately cover normal/error/abrupt process exits. Neither test
set can identify an unrecorded historical lock owner or authorize uncertain replay.

### Separate quality work package

After the comparison measurement is closed, implement and validate a deterministic
quantity/nutrition calculator for structured, provenance-bound known facts. Cover
g/kg, per-100-g/known-portion scaling, fractional quantities, sums and explicit
component changes using Decimal with final-boundary rounding. Treat unknown
portions, raw/cooked conversion and uncertain OCR as unresolved inputs. Keep T2's
original failure. Version and benchmark the later behavior separately; do not
change prompts, schema, analysis behavior, tolerances or model settings mid-comparison.

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
New results also record `provider_invoked` and a bounded `failure_stage`:
`admission`, `provider`, `post_provider` or `accounting_read` (`null` on success).
The invocation marker precedes entry into the provider adapter, including its
auth/guard checks; `true` does not prove that an HTTP request was sent. A verified
`false` can support a separately reviewed no-dispatch finding. Neither marker
automatically refunds a reserve, consumes another case or reopens a stopped run.
Admission and total duration now use one final monotonic timestamp, so admission
cannot exceed total duration. Do not reinterpret older timing fields using this
new implementation: forensic conclusions require the exact bound runtime source.

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

Closure must record the exact UTC retention-review date, measured results versus
computed costs, remaining resources, unresolved reserves and unavailable billing
data in the external run report. No future cleanup scheduler is installed by this
template: the owner must execute the retention review and approved destroy command.
Preserve original error artifacts even if a later ledger snapshot clarifies that
admission failed before a model dispatch. Never restart a closed run.

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
in an initialized run, finished-case and operation counts must agree. A finished
case without an operation requires separate evidence review even when the ledger
attempt count equals the number of operations. Missing records alone cannot prove
no dispatch. A derived local review does not automatically satisfy this CLI gate.
Operator reconciliation/extended retention needs a separate review, never a fresh
ledger. No automatic reconciliation or force-delete flag is provided. If archive
creation succeeds but deletion fails, inspect the cloud before continuing manually;
the script will not overwrite the archive. Azure may retain account soft-delete
metadata and ARM deployment history; no purge of that history is performed here.

The EUR 2 ancillary reserve within the EUR 10 operational threshold includes
31-day storage retention, Table tests/runtime transactions, network transfer,
FX/tax and cleanup. It is not enforced by Azure billing. Bound ARM status reads,
run the Table suite once, and query billing only at preflight, closure and retention
review. No hosting or log ingestion charges are intentionally introduced.
After review, remove the local synthetic result artifacts according to the approved
retention; retain the nonsecret closed-run archive and licensed fixture provenance.