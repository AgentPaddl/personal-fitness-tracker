# Completed screening: offline review

This review covers the completed public-data GPT-5.4-mini screening and its
uncommitted benchmark-only changes. No resources, Azure diagnostics or model calls
were made for this review. Production, iOS, use-case prompts and the frozen
18-case manifest are unchanged. This document is not execution authorization.
Original approval, resource identifiers, requests/results and live control data
remain outside Git in the private run directory.

## T5: no dispatch, exact admission error unresolved

The previous report conservatively retained USD 0.2343 because T5 had neither
provider metadata nor an operation record. Those absences alone are insufficient
to conclude no dispatch. The additional positive evidence is:

1. Before editing runtime code, recomputation matched the recorded run binding,
   complete request hashes, policy ID and all five durable result hashes. The
   original source, dependency/Python fingerprint and artifact hashes were saved
   privately in `pre-analysis-runtime.zip` and `analysis-baseline.json`.
2. The bound `CaptureProvider.generate` assigns `started = perf_counter()` before
   entering the real adapter, including its permit, attestation and token checks.
   No other runner path invokes the model. The marker is not subsequently cleared.
3. That exact old `run_one` evaluates `total_ms` first, then `admission_ms`. Only an
   unused entry marker causes the latter to sample the monotonic clock again.
   T5 records **264.686 ms admission > 264.683 ms total**. An earlier nonzero entry
   timestamp cannot produce this ordering, even after rounding. This is the
   recorded CPython/macOS monotonic-clock implementation, not wall-clock timing;
   a zero-at-boot timestamp is not a viable adapter-entry time in this CLI run.
4. The private `analyze_completed_run.py` verifies the original hashes and executes
   archived runner code with in-memory storage and a fake provider, with networking
   and subprocesses denied. A pre-provider error reproduces both T5 timing values
   with zero calls. An error after adapter entry records admission <= total and
   one fake call. The actual requests are never sent anywhere.

Together these exclude entry into the model adapter for T5 under the verified
runtime/evidence, rather than infer it from missing billing or response data.
The derived `analysis-reconciliation.json` releases only the **local USD 0.2343
exposure allowance**. It does not edit the original T5 result, approval, ledger,
case state or counters. Four model dispatches remain confirmed; T5 remains a
failed, consumed technical case with no answer, not a successful zero-cost result.

### Cause boundaries

| Candidate | Finding |
| --- | --- |
| Run claim/cooldown | Claim completed; the original result and finished T5 case exist. Pre-claim failures do not write this result. |
| Lifetime/period/concurrency limit | Ledger has four attempts, USD 0.9372 lifetime reserve, no active operations, and USD 0.003774375 settled daily/monthly cost. T5 is in a later minute than T4; limits would return `pilot_limit`, not the observed generic error. |
| Local Table quota | Entire preserved log, including later closure, totals 429 requests / 15,720 units, below 2,500 / 40,000 normal limits. Quota exhaustion is unsupported; the log has no per-request status or timestamps. |
| Request/profile/identity/UUID | Exact T5 request and policy binding reconstruct successfully; input/output bounds and UUID age validate. In-memory reservation using the saved ledger with only the closure block removed succeeds. This tests configuration, not the historical service response. |
| Approval/deadline | T5 attestation is 16:15:40 UTC; approval expires 20:03:49 UTC. Ledger `last_time` is 16:14:19.829401 UTC. Ordinary expiry is excluded by observed times; an unsampled backwards wall-clock jump during reservation cannot be strictly excluded. |
| ARM/model authentication | Fresh ARM/resource/price attestation returned before claim. Model-token acquisition and adapter dispatch guards were never entered. The earlier CLI tenant-plus-subscription incompatibility had been fixed before initialization, and four calls subsequently succeeded. |
| Table access/auth/transaction | A transient read/commit failure, storage-token/RBAC/network failure, or exhausted CAS conflict loop remains possible. Table exceptions were reduced to `pilot_unavailable`; no HTTP status or failing-step evidence survives. |

The failure is before provider entry, in Coordinator admission/reservation. No T5
reservation survived in the preserved closed ledger; its operation was neither
aged out nor cleaned up. Missing operation evidence corroborates the timing proof
but does not replace it. The exact Table/control failure is **not recoverable**
from these artifacts, and increasing limits would not be an evidence-based fix.

## T2: supplied values and arithmetic

The exact request builder, system message, JSON schema and user payload were
reconstructed and matched the recorded hash. The ordinary system prompt requests
a schema-conforming nutrition estimate and treats user content as untrusted data;
it does not provide a deterministic calculator. User input was:

> 200 g Joghurt und 40 g Haferflocken. Je 100 g Joghurt: 60 kcal, Eiweiss 4 g,
> Kohlenhydrate 5 g, Fett 2 g. Je 100 g Haferflocken: 380 kcal, Eiweiss 13 g,
> Kohlenhydrate 60 g, Fett 7 g.

| Field | Reference calculation | Correct | Response |
| --- | --- | --- | --- |
| Calories | 2 * 60 + 0.4 * 380 | 272 kcal | 276 kcal |
| Protein | 2 * 4 + 0.4 * 13 | 13.2 g | 20.2 g |
| Carbohydrate | 2 * 5 + 0.4 * 60 | 34 g | 34 g |
| Fat | 2 * 2 + 0.4 * 7 | 6.8 g | 6.8 g |

Decimal recomputation confirms the reference. The quantities, product association
and per-100-g basis are unambiguous. Protein is 7 g (about 53%) too high; calories
are also numerically wrong, although within the preregistered 5% tolerance. The
response claims direct calculation from supplied values, reports confidence 0.98
and no warnings. Its numbers contradict that claim. The output alone cannot
distinguish internal arithmetic error from substituting/ignoring a supplied value.
There is no evidence for a reference error or input ambiguity.

The smallest general correction is a deterministic domain calculator for validated
quantity/nutrient facts, not a T2-specific prompt. Given explicitly confirmed
component mass, basis mass and nutrients, compute each field with Decimal as
`sum(component_mass / basis_mass * declared_nutrient)`, then round once at the
response boundary and apply existing bounds. Preserve declared calories rather
than replacing them with a 4/4/9 macro formula. Suitable deterministic operations:

- g/kg and compatible mass-unit conversion; per-100-g and known-portion scaling.
- Summing components with declared nutrition, including mixed known products.
- Explicit half/double/new-weight corrections against a known baseline.
- Adding, removing or replacing identified components with known quantities/values.

Free-text extraction must first produce validated, provenance-bound facts; uncertain
product association or OCR remains reviewable, not silently trusted. Raw/cooked
conversion, volume without density, unknown portion size and photo inference are
not exact arithmetic. A global regex over meal text is not a safe substitute.
This review proposes that product change; it does not implement it or alter the
historical prompt. Boundary tests should cover unit/basis equivalence, component
order, fractional scaling, sums, replacement and ambiguous inputs, not one meal.

## Code review and validation scope

- Retained the explicit EUR 10 delayed-billing-risk approval with unchanged
  USD 4.2174 model reserve, 18-attempt cap, tax/FX and ancillary allowances.
- Retained subscription-only Azure CLI credential creation with independent
  tenant/operator/audience validation. Production identity paths are untouched.
- Closed the Table-counter restart gap: requests cannot recreate a missing log.
  Initialization is explicit, local, confirmation-bound and exclusive. Corrupt,
  linked, insecure or locked logs fail closed; limits and cleanup headroom remain.
- Added explicit provider-entry and bounded failure-phase evidence, with one final
  monotonic timestamp. No automatic refunds, retries, skips or limit changes.
- Closed an archive gap: initialized runs with more finished cases than operations
  now block destruction, even if operation count matches ledger attempts. A
  no-dispatch reconciliation is a separate review, not a missing-record shortcut.

Focused regression tests cover before/after-provider failure, timing, retained
exposure, stopped-run behavior, counter integrity/limits/locks, offline exclusive
initialization and incomplete archives. Existing real Table integration tests were
not rerun in this offline review. All live artifacts and the analysis program stay
private; only generic code, tests, this review and procedure updates belong in Git.
Validation: 52 focused benchmark tests passed; the complete offline gateway suite
reported 452 passed and 6 skipped, with the live benchmark Table test file explicitly
excluded and external sockets blocked (loopback allowed for local HTTP smoke tests).
Editor diagnostics, Python syntax validation and diff whitespace checks passed.

## Coverage and continuation preparation

T1-T4 are four schema-valid technical successes, not four proven usable estimates.
Only one of two numeric cases passes all preregistered fields; seven of eight
individual fields pass tolerances. Human quality scores/usable flags are still
unassigned. T3/T4 acknowledge uncertainty but have no numeric ground truth. Missing:
T5's unit-conversion answer, T6 injection control, six photos, two labels and four
refinements. The six photo variants are not six independent meals. No photo
accuracy, full-matrix accuracy, p95 or cost-per-usable-result conclusion is justified.

The closed run stays closed. Plan conservatively with **five consumed technical
slots and at most thirteen further cases**, despite only four paid dispatches.
Prioritize P1-P6, L1-L2 and R1-R4 (twelve cases), then T6. Do not rerun T1-T4 or
reuse T5 automatically. Releasing its local financial allowance does not grant a
replacement case or a fresh attempt budget. If dispatch evidence were disputed,
retain the fifth reserve and slot until resolved.

Any future continuation needs explicit execution approval and a reviewed durable
aggregate checkpoint linking old results, code/approval hashes, attempts, unknowns,
lifetime reserve and the existing ancillary counter. A new run ID by itself is
not that checkpoint; the current CLI does not implement cross-run enforcement or
resuming a closed matrix. No new resources or continuation ledger were created.

The authorization remains **EUR 10 total**, including earlier work and later
retention/cleanup. Known usage-priced cost is USD 0.003774375, not invoice cost.
After the local T5 release, reserving the full EUR 2 ancillary allowance plus
known cost at 1.20 EUR/USD and 1.50 tax gives EUR 2.006793875. Thirteen hypothetical
new calls at USD 0.2343 maximum each would raise that projection to EUR 7.489413875,
not create a new EUR 10 allowance. Reconcile actual billing, FX, taxes and all
retention costs before any future authorization; unavailable billing is not zero.

The OpenAI account/deployment remain deleted; the closed Table is retained. Earliest
retention review remains **2026-10-19 16:15:59 UTC**. No cleanup scheduler was added.
The strengthened archive gate rejects this historical five-finished/four-operation
snapshot. The old report's destroy command must not be treated as automatic
permission: review the private no-dispatch proof and arrange a separately approved,
evidence-preserving cleanup procedure. Do not change case states/counters to make
the predicate pass. Retain the archive and reconciliation after eventual deletion.