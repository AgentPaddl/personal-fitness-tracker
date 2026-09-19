# Private pilot deployment: 2026-09-19

## Authorization and current state

User authorization: EUR 20 total for the first 30 days, plus EUR 5 once for setup
and acceptance. The original ten targeted nonprivate model attempts were extended
by exactly four separately authorized cases, for a non-replenishing total14;
no automatic retry or extension. These are operational stop thresholds with acknowledged
billing residual risk, not guaranteed invoice ceilings. The prior benchmark is
separate. No production deployment, installed app or private record was changed.

Deployment is **AI off, not accepted for ordinary use**. No real nutrition/image
data were sent. Acceptance counter: **14/14**, without model retries: six original
successful synthetic text/refinement responses, four original image429s with
unknown usage, and four newly completed image cases. L1/L2/P1 returned valid
estimates; P5 returned semantic non-food with no saveable estimate. No new429.
The first signed technical grant was exercised, revoked under the same valid
token, and invalidated by rotating only its release key. The bounded continuation
grants and the capacity-correction grant are also revoked. Four full-cost holds remain, totaling USD0.9372; their
completed response executions no longer occupy slots. No financial hold or
counter was reset. Only the owner's identity is configured;
the wife is not admitted and no placeholder identity was substituted.

The conservative period anchor was recorded immediately before the first pilot
resource-group creation:

- Start: **2026-09-18T22:19:10Z** (2026-09-19 00:19:10 Europe/Berlin).
- End: **2026-10-18T22:19:10Z** (2026-10-19 00:19:10 Europe/Berlin).
- Exactly 30 days. Registration/preflight did not create billed services.
- Policy expiry is bound to that end. Neither a new calendar month nor technical
  approval renewal extends it. Signed technical evidence lasts at most 24 hours.
- Subscription and tenant were verified in the pre-existing private CLI context;
  the default work Azure context was neither changed nor used for deployment.

Private outputs, identities, contacts, keys and operation results are in ignored
`local/20260919/`, directory mode 0700, generated secret-bearing JSON mode 0600.
Never print parameter files, token caches, app settings or Key Vault values.
The signed-in Owner/Global Administrator received no additional roles.

## Provisioned resources

Resource group: `pft-pilot-20260919`, Sweden Central. Baseline inventory contained
only the separate benchmark storage account, which remains untouched.

| Resource | Actual configuration |
| --- | --- |
| ACR `pftposyuw3m453fx4` | Basic, admin disabled; temporary local push credential removed |
| ACA environment `pft-pilot-20260919-environment` | Consumption workload profile only, Azure-managed network, no customer VNet or paid log destination |
| ACA `pft-pilot-20260919-gateway` | Public HTTPS, 0.25 vCPU / 0.5 GiB, min0/max1; AI release disabled |
| Functions `pft-pilot-20260919-api` | FC1, Python 3.13, 512 MiB, max1, HTTP concurrency2, no always-ready |
| Storage `pftposyuw3m453fx4` | LRS, Shared Key and anonymous blobs disabled; private `deployments` container, new `PilotLedger` table |
| Key Vault `pftp-osyuw3m453fx4` | RBAC, secret-scoped readers, seven-day soft delete and purge protection |
| OpenAI `pft-pilot-20260919-model` | Local key authentication disabled; `pilot-mini`, GPT-5.4-mini `2026-03-17`, DataZoneStandard capacity20, verified20 RPM/20,000 TPM, NoAutoUpgrade |
| Managed identities | Separate `pft-pilot-20260919-backend-id` and `pft-pilot-20260919-gateway-id` |
| Entra registrations | Three new single-tenant applications/service principals: native client, backend API, gateway API |
| Budget | Resource-group cost budget EUR12; Actual80 and Forecast100 notifications to the owner's existing Entra contact |

Backend: `https://pft-pilot-20260919-api.azurewebsites.net/api`.
Gateway: `https://pft-pilot-20260919-gateway.gentleriver-150ab3f0.swedencentral.azurecontainerapps.io`.
The app knows only the backend URL and public Entra configuration.

Initial deployed image (superseded by the auth-first image below):
`pftposyuw3m453fx4.azurecr.io/gateway@sha256:58a47d0c4ea78d6ffcbb45241464e0ee172b0369a278489c978823bac36fe2a0`.
Alpine layers reused from the reviewed candidate; new admission code included.
Trivy: zero reported vulnerabilities and secrets, with the already documented
Alpine EOL-list coverage warning. This is scanner evidence, not zero risk.

Gateway grants: exact Table Data Contributor, account-scoped OpenAI User,
registry-scoped AcrPull, six secret-reader grants. Backend: dedicated host Blob
Data Owner, two secret-reader grants, exact `Gateway.Invoke` application-role
assignment. No Contributor, general model role or Table role for the backend.
Inherited subscription Owner remains an administrative privilege of the operator,
not a workload grant. Inspect inherited roles again before release.

## Acceptance evidence and gaps

Completed live:

- Tenant/subscription, EUR billing and Microsoft Customer Agreement metadata;
  model DataZone quota200 unused before deployment; provider registration changed
  reported ACA environment quota from zero to 15; Functions region supported.
- Actual ARM validation and deployment. Provider checks exposed three real local
  template defects: null (not string `none`) for no log destination, scoped
  extension-resource ID for AcrPull dependency, and
  `scaleAndConcurrency.triggers.http` for HTTP concurrency. All corrected;
  concurrency2/max1/512 MiB read back from the actual Functions resource.
- Backend health200; anonymous readiness401, anonymous analysis401 and forged
  platform identity headers401 after startup. Initial timeout and one 503 were
  observed during deployment/startup, not treated as authentication success.
- Gateway health200; readiness/analysis503 while release is disabled. This does
  **not** prove JWT/HMAC discrimination under an active release.
- Real gateway Managed Identity can query the table. Signed-in operator without
  a Table data role gets403 using a single direct data request. Anonymous table
  query returns404; ARM and authorized query independently establish existence.
- New ledger initialized once with the actual policy digest, acceptance
  attempts0/reserved0 and no benchmark. Two separate gateway processes raced a
  synthetic Table row: exactly one CAS commit and one conflict. Probe row deleted;
  actual ledger counters unchanged.
- Immutable image pushed, inspected and tested. New targeted tests: 186 local
  ledger/runtime tests before manifest/login additions; 31 relevant tests inside
  the actual image; manifest and login tests separately passed afterwards.
- Actual-output unsigned generic iOS Release build succeeded. Bundle
  `com.benedikt.Trainingsplan`, team `2SF7PV3WCD`, build5 unchanged. No installation.

The personal native-client sign-in completed on 2026-09-19 at 07:17:05Z.
The existing token-free record reports exact tenant/owner identity matching,
HTTP503 and the expected backend `not_ready` response, with zero model calls.
The helper checks the MSAL ID-token tenant/oid against the recorded sole owner
before sending the request; it does not persist access or refresh tokens. Actual
Easy Auth ARM readback independently restricts the backend audience, native
client, tenant issuer and sole owner oid, with token storage disabled. This
proves native admission to readiness, not the analysis route's injected claim
mapping or downstream JWT/HMAC discrimination.

Additional live checks in this continuation:

- Eight public boundary checks passed: both health endpoints200; backend
  anonymous readiness, forged platform headers and malformed token401; disabled
  gateway analysis503; query-bearing analysis and docs404. No automatic retry.
- Resource-group/inherited role inspection and Graph app-role readback still
  match the separated identities and exact required `Gateway.Invoke` role.
  Functions remains HTTPS-only, max1/512MiB/HTTP2/no always-ready.
- A bounded console snapshot contained eight technical request events, no
  generated key values, synthetic request text or Bearer marker. This does not
  establish log privacy during active provider traffic.
- Model metrics were available but contained no request/input/output samples;
  missing telemetry is not proof of zero invoice charges. Cost Management again
  returned429; the budget's delayed EUR0 display is not an accrued-cost total.

The new model-free `qualify_ledger.py` exercises replay/conflict/foreign identity,
unknown-hold restart, double settlement and policy mismatch in a unique synthetic
partition. It never calls a provider. It verifies the real ledger's content and
ETag are unchanged and deletes only that test partition. Three focused local
tests passed, including a full partition-isolation test and the API-off gate;
the final ledger/runtime regression run passed all 191 tests.
The earlier executed probe stopped at the ordinary settings loader's intentional
AI-off release check, before Table access. The helper now explicitly supplies
`Settings()` without changing the HTTP runtime. Its next transport attempt was
rejected at **07:31:18Z** with HTTP429/Retry-After600.

The subsequent continuation checked UTC time at **07:41:25Z**, after the
**07:41:18Z** deadline, then made **exactly one** new Container Exec attempt.
That attempt started at **07:41:54Z** and completed successfully at
**07:42:38Z**. The in-process result, not merely the CLI exit code, proves:

- Duplicate operation, changed fingerprint, invalid UUID and foreign identity
  are denied by the Coordinator using the real Azure Table store.
- Unknown full-cost holds survive Coordinator reconstruction; replay and double
  settlement are denied, and a mismatched policy digest fails closed.
- Only the isolated synthetic partition was modified; it was deleted afterwards.
  The actual pilot ledger content and ETag were unchanged, with **attempts0,
  reserved0**, no active operations, and no provider invocation.
- Pilot ledger SHA-256:
  `8e1995108f21459ea5c269813c8fb6926a04e45ecd79b27c78483a41d6b606c7`.

The token-free private receipt is `local/20260919/ledger-retry-1789803714.json`.
This is a real Table/Coordinator test, not an HTTP HMAC-tampering test or a real
provider-response-loss test. Earlier passed CAS/routing/RBAC checks were not
repeated. No further Container Exec call was made in this continuation.
The Functions Flex SCM
environment is administratively reachable, but its command endpoint returned404;
no new diagnostic endpoint or workload permission was added.

At that earlier checkpoint, still required before any model call: analysis-route Easy Auth claim mapping;
end-to-end backend Managed Identity JWT/HMAC; native and
foreign workload rejection; delegated/direct bypass attempts; actual ingress
body/slow-client/scale behavior; active-path log inspection and live
revocation/renewal qualification. Offline regressions do not attest these checks.
No `CHECKS` record has been fabricated and no signature has been issued.
The gateway remains `AI_API_ONLY_ENABLED=false`. The backend's similarly named
flag is true to select mandatory workload authentication; it is not an enabled
gateway model release. No model request was made during that earlier continuation.

### Earlier existing-path qualification blocker

The blocker at commit `a9edc0d`, before the ordering correction below, was
**not another throttle**.
`ApiIngress._dispatch` calls its release guard before workload verification,
body buffering and the domain's HMAC verification on both `/readyz` and
`/v1/food-analysis`. Two new focused local control-flow tests confirm that a
failing release guard returns503 without reaching those stages, regardless of
the supplied token. They are local ordering evidence, not live JWT validation.

| Existing authorized path | Evidence possible / not established |
| --- | --- |
| Native readiness and ARM/Graph inspection | Existing evidence establishes owner/native admission and configured workload role/issuer/audience. It does not show that the gateway validated an actual backend MI token. |
| Disabled gateway readiness/analysis | Establishes the closed release gate, not rejection specifically caused by native/foreign JWTs, wrong roles/signatures, or a tampered HMAC body/operation/timestamp. No more equivalent503 probes were sent. |
| Real Table qualifier | Replay, conflicts, unknown holds, restart, policy binding and unchanged pilot accounting now passed. It cannot establish HTTP authentication or invalidate cached workload tokens. |
| Existing in-process JWT/HMAC and renewal tests | Previously passed with synthetic signing keys, claims and grants. No blanket rerun and no relabelling as cloud evidence. |
| Approval/renewal CLI | Requires complete true, configuration-bound evidence, including JWT/HMAC checks. It cannot honestly bootstrap those checks by signing an incomplete checklist. No current accepted grant exists to revoke or renew live. |

Non-substitutable live evidence is therefore: an actual backend MI JWT accepted
by the gateway with negative caller/claim controls; authenticated HMAC rejection
on the real route without provider dispatch; and an accepted technical grant
subsequently revoked/expired with denial under still-valid cached workload tokens
and unchanged accounting. Being disabled from the outset is not a revocation test.
The prepared artifact has no independent model-free HTTP qualification path past
the release guard. Fabricated attestations, bypassing that guard, adding a debug
endpoint or loosening access are not used to break this dependency. Model
acceptance remains blocked; neither a repeated readiness-only login nor another
Table/Exec retry resolves it. A separately reviewed qualification design is
needed to resolve this dependency before progressing to model calls.

### Auth-first correction

The user authorized correcting this dependency without bypassing authentication.
The existing gateway route now checks early limits, exact workload JWT/service
secret, the bounded JSON body and request HMAC/user allowlist, then activation,
then the unchanged Coordinator/budget/one-shot provider permit. Readiness checks
the workload before activation and ledger but has no analysis HMAC. The second
HMAC check in the domain remains as defense in depth. Anonymous requests now
receive403 instead of the previous release-first503; valid signed requests while
AI is off still receive503 without any reservation or provider dispatch.

Initial synthetic technical grants require pre-activation evidence and last at
most3600seconds. Revocation is a second-stage test, not a prerequisite to issuing
the first test grant. It must use authenticated readiness/nonmanifest probes,
not artificial model calls. No grant or participant consent is implied by the
code change. Existing policy, fixed end date, acceptance counters and budget are
unchanged. The earlier blocked-path description is historical, not the corrected
artifact's behavior.

Corrected image:
`pftposyuw3m453fx4.azurecr.io/gateway@sha256:1229c6d530ce628bfa5c1d8cdd105845883e34117f446667032e9e18131e6ac8`.
Local affected suites:211passed before the additional live-probe-helper test;
28ingress variants additionally used the real Coordinator/permit with an in-memory
CAS store to prove unchanged ledger on every denial. These are local tests.
Trivy on the actual image:0reported vulnerabilities,0secrets; existing Alpine
EOL-list warning remains. An unpatched public-base probe alternative was scanned
and rejected due to High findings, not deployed. Live correction evidence follows
only after actual deployment and probes; no incomplete evidence is signed.

### Live auth-first results

Commit `cbfed3b` was pushed normally and deployed only to the private pilot.
Revision `pft-pilot-20260919-gateway--0000002` is Healthy/Provisioned with100%
traffic and the corrected immutable image above. The final readback at
**08:21:29Z** still has `AI_API_ONLY_ENABLED=false`, and latest/ready revision
both equal0000002. The CLI update response omitted ordinary environment values;
a fresh resource readback confirmed unchanged values except the intended image
digest. Empty `value` fields added alongside unchanged secret references were
serialization differences, not secret rotation. No grant/signature was issued.

The temporary manual job `pft-pilot-authcheck-20260919` used the same scanned
image, existing backend/gateway identities and existing secret-reader/AcrPull
roles. No role, ingress or debug endpoint was added. Each execution had one
replica,0.25vCPU/0.5GiB,180-second limit and retryLimit0:

- `t5bfl7q`: all nine authentication checks passed at **08:09:29Z**. The actual
  backend MI JWT plus request HMAC received503 with AI off. Missing workload,
  damaged JWT signature, wrong service secret, wrong HMAC, changed body,
  changed operation, expired assertion and foreign signed user each received403.
- `1ab4av7`: six boundary checks passed: unsupported media415, declared
  oversize413, malformed/nonobject JSON400, chunked oversize413, and incomplete
  chunked body408 after10.03seconds. The subsequent foreign-workload token
  acquisition failed without a specifically recognizable role-denial code.
  The overall job failed; its passed boundary cases are not a passed full run.
- `riecq7e`: a targeted diagnostic did not repeat those passed cases. The real
  ledger remained at attempts0/reserved0/no active operations with the same
  SHA-256 `8e1995108f21459ea5c269813c8fb6926a04e45ecd79b27c78483a41d6b606c7`.
  Foreign MI token acquisition again returned `ClientAuthenticationError`, with
  no extracted AADSTS code or HTTP status. No foreign-token request reached the
  gateway. This is **not** a verified wrong-workload/role rejection and does not
  satisfy `foreign_workload_denied`; there is no automatic retry.

The terminal did not expose tokens, key values or raw identity errors. Receipts
are private `auth-job-evidence-*`, `boundary-job-evidence-*`,
`foreign-job-evidence-*` and `auth-final-state-*` JSON files. The job was deleted
after its stopped executions; local Colima profile `pft-pilot-review` was stopped.
The pilot ledger was not reset or modified by these HTTP qualifications.

Earlier local regression: **220passed** across the affected runtime/ledger suites;
the deployed Linux image had separately passed49selected ingress/release tests.
New helper tests cover fail-stop/no-retry behavior, bounded incomplete bodies,
unclassified identity failure, normalized nonmanifest input, AI-off before login
and in-memory token clearing after failure. Local tests are not live evidence.

The new `login-analysis-probe` command reuses the existing native app and requires
a fresh personal login because the prior login persisted no tokens. It first
requires AI off, then tests analysis identity mapping via400/operation_required,
a valid operation via503/pilot_unavailable, and direct native-token rejection
at the gateway with otherwise correct service/HMAC headers. All payloads are
outside the acceptance manifest. The503 alone cannot distinguish a backend
token-acquisition failure from gateway admission; correlate with content-free
gateway evidence before claiming end-to-end success. The subsequent personal
login completed at **08:28:46Z**: exact native identity matched; missing operation
returned400/operation_required, valid operation503/pilot_unavailable, and the
direct native token403/pilot_forbidden. Gateway metadata independently records
`release status=503` at08:28:46.1529779Z and `workload status=403` at
08:28:46.3225275Z. This establishes actual backend JWT/HMAC admission through
the analysis path to the closed release gate. It is authentication, not renewed
authorization or consent. Tokens stayed in memory; no model attempt occurred.

A targeted fourth job execution, `owqtk7q`, completed successfully at08:33:32Z.
It obtained an actual Azure Storage audience token using the existing gateway
UAMI and sent it once to the gateway with otherwise correct service/HMAC headers:
**403 at the gateway**. No role or permission was added. This is a combined
wrong-principal/wrong-audience negative case, **not an isolated correct-audience
wrong-principal or role test** (`isolates_wrong_principal_only=false`). Token
acquisition failures, including AADSTS501051, are never authorization evidence.
The actual ledger content and ETag were unchanged, attempts0/reserved0/no active
operations, with the same SHA-256 recorded above. Private receipts are
`native-analysis-probe-*`, `native-analysis-log-evidence-*` and
`issued-foreign-evidence-*`; bounded gateway logs exposed neither the configured
secrets nor Bearer values nor the synthetic probe text. This log snapshot does
not attest all platform logs or an as-yet-unexecuted active model path.

The later account-linked contract investigation and explicit bounded retention
approval below completed the synthetic-only privacy evidence. The foreign-token
criterion is supported by the actual combined negative case above and separate
exact-role readback/local claim tests, not an invented isolated-principal live
test. This limited scope is explicit in the private evidence provenance.

### First grant and same-token revocation

A first synthetic technical grant was signed at **08:53:06Z**, expiring at
**09:53:06Z**, for configuration SHA-256
`59c42e5854ce3685b2468399f8da25013a511fd4eeefcd6403a189651318255c`.
All six evidence groups bind this digest. The underlying live receipts, resource
readbacks, prior CAS/RBAC evidence, contract findings and owner's retention
approval are recorded separately; evidence booleans are not independent proof.
No ordinary-use grant, new participant or longer pilot period was authorized.

The operator's direct Key Vault data-plane secret write returned403 because the
operator has no secret-set data role. Publication used the already authorized
ARM `Microsoft.KeyVault/vaults/secrets` resource path instead, with no added role.
The gateway references the resulting explicit approval/signature secret versions.

Earlier attempts remain partial: `egxg8xa` failed without a captured terminal
cause; `p1coaqq` ran after premature revocation and correctly returned503 instead
of the expected active200; `zcbeiuv` established active readiness200/nonmanifest403
and unchanged ledger. The first same-process witness `dviaydm` established its
active phase, but stopping the job removed its transient log access, so its
completion was **not** counted as a passed revocation test.

The final witness `srt0gcy` kept one actual backend-UAMI JWT only in RAM. At
**09:14:47Z**, readiness returned200 and signed nonmanifest analysis403. The
operator set AI off and confirmed `cycleoff2` was the actual **latest ready**
revision before signalling that exact job. At **09:16:03Z**, the same token
received readiness503 and nonmanifest503. Token expiry was09:14:37Z the next day;
all four checks have the identical SHA-256 fingerprint, not merely the same
client ID. Separate gateway events confirm two release503 responses.

The completed witness stored a minimal token-/payload-free receipt in the
isolated `qualification-release-v1/result` row. Reader `r4wk5yh` retrieved it;
private receipt `technical-durable-result-1789809402.json` contains the complete
200/403/503/503 sequence. Actual pilot-ledger content **and ETag** stayed unchanged:
attempts0, reserved0, no active operation, same ledger SHA-256 as above. Neither
readiness nor the nonmanifest probe invoked a model. Receipt read and ETag cleanup
are separate operations, so losing a reader log does not destroy the evidence.
This proves runtime flag revocation under a still-valid token, not Entra token
invalidation or retroactive cancellation of an already dispatched model call.

Synthetic acceptance is a separate policy option. It admits only SHA-256 hashes
of normalized nonprivate DTOs and only one person. Its CAS-backed lifetime
attempt/reservation counters do not reset at midnight, calendar month, process
restart, settlement or technical release renewal. Limits: ten attempts and
USD2.343 aggregate full-input reserve. Ordinary/benchmark policies omit this new
field, preserving their existing policy digest. Manifest changes cannot reuse an
existing ledger silently. Transition to ordinary use needs explicit reviewed
carry-forward, never deletion/reset of accumulated spend or unknown holds.

Manifest: T2, T5, T4, T1, L1, L2, P1, R1, R4, P5 from existing fabricated text,
synthetic labels and reviewed CC0 image fixtures. Tests cover extraction, units,
ambiguity, amount bases, image, refinement and a non-food abstention control.
P5 is not evidence of safety-filter refusal; a generic error is not successful
abstention. No private user input or repeated setup model call is permitted.
Expected T2: 272 kcal, 13.2 g protein, 34 g carbohydrate, 6.8 g fat.

### Initial model acceptance stopped at an unknown hold

After the same-token safety qualification, the same still-valid one-hour grant
was enabled for the existing manifest, without renewal or policy change.
`qualify_models.py` sent one explicitly selected case per manual retry0 job.
It verified the normalized hash and exact prior lifetime counters, created a
non-overwritable dispatch intent, and inspected real operation settlement before
allowing progression. No provider SDK/image/runtime change or extra role was made.

| Case | Actual outcome | Quality / accounting |
| --- | --- | --- |
| T2 | 200 | Exact272kcal/13.2g protein/34g carbohydrate/6.8g fat; known USD0.0019701 |
| T5 | 200 | Decimal comma/kg conversion exact195/4.05/42/0.45; known USD0.00154275 |
| T4 | 200 | Explicit100g/300g and cooked/dry ambiguity; confidence0.34; disclosed generic100g assumption; known USD0.001343925 |
| T1 | 200 | Cooked weight/arithmetic exact195/4.05/42/0.45; known USD0.00152955 |
| L1 | 429 | No usable response; operation state `unknown`, usage unknown, full USD0.2343 hold retained |
| L2, P1, R1, R4, P5 | Not sent | No image/refinement/non-food acceptance claimed |

Known four-call model cost is **USD0.006386325**, according to the configured
versioned price table and validated usage, not a final EUR invoice. Including the
unresolved hold gives **USD0.240686325** conservatively charged/held. The separate
non-replenishing acceptance counter is **5 attempts / USD1.1715 full reserves**;
successful settlement does not return that lifetime allowance.

L1 execution `be14iiy` returned429 after admission. The API adapter maps upstream
429 to the rate-limit error; absent usable accounting, the Coordinator deliberately
keeps the dispatched operation `unknown` and active. This is not proof of zero
provider charge or a precise RPM/TPM/capacity diagnosis. No provider error body
was retained by the runner, and a later generation-log snapshot was empty.
Do not invent a more specific cause from429 alone. No second L1 call or next-case
start occurred. The active entry was a fail-closed execution-slot blocker,
not exhausted financial headroom or a model-quality result. Reconcile against actual provider/usage
evidence and a reviewed hold-preserving procedure before any further admission;
do not clear `active`, reset the ledger, raise capacity or replay L1 to proceed.

A bounded active gateway console snapshot contained four domain200 events and
no configured key values, Bearer token, manifest text or image prefix. Synthetic
results were fetched through the existing administrative Exec channel directly
into protected local diagnostics, not application logs. This is bounded evidence,
not a claim about all Microsoft platform logs. Final private result receipt:
`model-final-private-receipt-1789810032.json`.

Final gateway revision **`pft-pilot-20260919-gateway--locked`** is AI off, healthy
and the sole active revision. Only the release key was rotated through the
existing ARM path and pinned secret reference; the new process verified that
key was actually loaded. Service, request-HMAC, fingerprint keys, policy and pilot
period stayed unchanged. The old signed grant cannot be reused with the new key.
The release-cycle receipt was deleted before the first model case. At09:29:25Z,
the five isolated model diagnostic rows were ETag-deleted only after comparison
against their privately received hashes. Actual ledger content **and ETag** were
unchanged by cleanup: attempts5, lifetime reserves1171500000 nanodollars, one
unknown active hold. Real operation/accounting records were not deleted.

Final model-free job `l8vr5qg` passed all nine authentication checks against this
locked revision: correct workload/HMAC503, eight malformed/foreign/expired
authentication cases403. No model call or reservation was attempted. Its receipt
was secured, no job execution was running, and the temporary job was deleted and
its absence read back at09:31:30Z. Registry/hosting resources remain within the
original pilot period and still incur charges; AI-off is not full teardown.
Production, iPhone, wife admission and the unrelated benchmark remain unchanged.

Final affected regression: **245 passed, 1 skipped**. New code also passed Pylance
syntax checks and editor diagnostics; `git diff --check` passed. The new helper
tests exercise no-network single dispatch, create-only intent, hash/order checks,
duplicate/active refusal, HTTP/transport/unknown-usage stops, same-token release
and receipt isolation. This does not turn the five untested live cases into passes.

### Investigation and bounded continuation from064628f

Azure Monitor's existing `AzureOpenAIRequests` metric for `pilot-mini` shows four
HTTP200 responses and one HTTP429 in the original acceptance window, including
the429 in the09:26Z bucket. Together with the admitted, dispatched and settled
L1 operation this establishes an **Azure model-provider429**, not the gateway's
connection cap or the pre-admission pilot limiter. An offline actual-SDK test
reproduces one dispatch, `rate_limited` metadata, unknown usage/full reserve and
the occupied personal slot. `max_retries=0` remains unchanged.

The original receipt did not retain provider Retry-After, the provider request ID
or the provider error body; the gateway did not persist/forward these headers.
They cannot honestly be reconstructed. ARM deployment readback confirms
DataZoneStandard capacity1, **1 request/60s and1,000 tokens/60s**. Regional quota
is200 capacity units (200,000 TPM), of which1 is assigned; it is not this
deployment's request allowance. Neither quota nor capacity was raised. Original
start gaps were94,71,51,42 seconds. L1 followed T1 after42 seconds, a rate-limit
risk rather than proof of the precise cause. The2,000-token completion cap plus
prompt/image estimates also matters to throttling, independently of billed usage.

The exact previous blocker was `person.concurrent=1`: L1's `state=unknown`,
`settled=true` record occupied the owner's sole slot. The operator runner also
deliberately stopped on an active entry/unknown usage. The ledger was not blocked;
known charges plus the L1 hold were USD0.240686325. Five further full reserves
would total USD1.412186325 conservatively charged/held, within USD2.343, while
the non-replenishing lifetime allowance would reach exactly10/USD2.343.
Financial uncertainty is therefore not evidence of active provider execution or
an exhausted budget.

The tested operator-only `complete_terminal_429` correction was applied with AI
disabled, exact receipt/ledger hashes and both ETags. L1's full USD0.2343 charge,
unknown usage/state, fingerprint, counts, bucket costs and lifetime reservations
were unchanged. Only its execution slot was removed and completion evidence was
recorded. A first unconfirmed administrative transport delivery was read back as
unchanged before resubmission; it was not presumed successful. Later Exec-channel
management429 throttling was kept separate from model outcomes. No timeout or
cancelled operation was converted into terminal-response evidence.

The same configuration/image received a new one-hour technical grant under the
existing owner authorization, using the current release key and still-fresh
evidence. The configuration digest did not change: release-key material is not
part of that digest, although approval signatures depend on it. The operator
runner now requires65 seconds since the last admitted attempt, preserves safe
gateway error metadata and still sends each selected case only once. This spacing
does not establish that every image fits the1,000 TPM deployment. L2 also returned
`provider_rate_limited` after a multi-hour interval, so the original42-second gap
cannot explain all observed throttling. Its unknown full-cost hold was likewise
preserved while separately closing only its confirmed response execution.

P1 also returned a confirmed provider429 and retained its full USD0.2343 hold.
Its bounded console slice omitted the full status record; the durable Table
receipt proved attempt7 and the terminal429. It was not retried. The same
hold-preserving procedure closed only its execution slot with AI off. Existing
Azure model metrics independently showed exactly two429s for L2/P1, no extra
inference calls. R1 and R4 both returned200 with validated known accounting:

| Case | Outcome | Quality / accounting |
| --- | --- | --- |
| L2 | Provider429 | No quality result; full USD0.2343 unknown hold |
| P1 | Provider429 | No photo acceptance; full USD0.2343 unknown hold |
| R1 | 200 | Exact halving to130kcal/2.7g protein/28g carbohydrate/0.3g fat; confidence0.98; known USD0.000855525 |
| R4 | 200 | Baseline260/5.4/56/0.6 retained, no compounded correction or photo-access claim; confidence0.94; known USD0.000875325 |
| P5 | Provider429 | Full USD0.2343 unknown hold; transport rejection is not semantic abstention or non-food acceptance |

Before the final two cases the gateway was disabled and the unchanged technical
configuration was signed for another bounded hour using the existing authority,
not an extension of the fixed pilot period, funding or ten-attempt allowance.
Readiness guards prevented starts against incomplete revision transitions;
those guards made no model requests. Six successful text/refinement calls now
have known configured-price cost **USD0.008117175**, not a final invoice.

P5 was the tenth and final model attempt. All five previously unstarted cases
were sent once; no L1 or other failed case was repeated. Continuation dispatch
starts were separated by292,2993,246,112 seconds, each above the new65-second
gate. Existing Azure model metrics show exactly **six200 and four429** across
both runs, matching ten ledger admissions. All image cases L1/L2/P1/P5 were
throttled; text/refinement success does not establish label/photo/non-food
behavior. Precise RPM versus estimated-token versus shared-capacity attribution
remains unavailable without provider headers/body. No quota increase, lower
output cap, changed prompt, fallback or diagnostic inference was used.

Final main-ledger counters are **10 attempts / USD2.343 lifetime full reserves**.
Known cost USD0.008117175 plus four unchanged USD0.2343 holds equals
**USD0.945317175 conservatively charged/held**. Unknown usage was never replaced
with zero. There are no active execution slots and `blocked=false`; another model
attempt is nevertheless prohibited by the exhausted non-replenishing attempt
allowance, separately from AI-off/revoked release. Real operation records,
fingerprints and replay protection remain intact. P5's terminal-response slot
was closed under the same reviewed procedure, without deleting its financial hold.

The sole active ready revision is
**`pft-pilot-20260919-gateway--resume-locked`**, with the unchanged reviewed image.
At12:30:52Z the actual process confirmed AI off, the newly rotated release key
loaded, and both continuation signatures invalid under that key. Only release-key
material changed; service/HMAC/fingerprint keys, policy, quota, identity scope and
fixed pilot end stayed unchanged. Five isolated diagnostic rows were compared
with privately captured receipts and ETag-deleted. Main-ledger content and ETag
were unchanged by diagnostic cleanup. Minimal accounting/uncertainty evidence
is retained privately; synthetic response evidence has the approved bounded
diagnostic retention, not indefinite payload retention.

The final model-free authentication job passed all nine checks against the locked
revision: valid workload/HMAC503, eight invalid authentication cases403, zero
model requests. Its actual execution succeeded. The temporary job was deleted
after all executions ended; the12:34:50Z readback confirms **zero pilot jobs**.
The continuation used ten bounded jobs: five model cases and five model-free
administrative/authentication executions. Production, installed iPhone data,
participant admission and the separate benchmark remained unchanged. AI-off is
not full pilot teardown; registry/hosting resources remain until their scheduled
period-end cleanup and continue to incur charges.

The reviewed correction is confined to the operator helper; the deployed runtime
was not rebuilt or patched. **367 affected tests passed, one skipped**, covering
actual-SDK429 attribution, single dispatch, timeout/unknown conservatism, CAS
conflicts, unchanged holds/counters, receipt binding, replay and spacing gates.
Pylance syntax checks, editor diagnostics and diff whitespace checks passed.

## Read-only throttling investigation from b64b6fa

On2026-09-19 at13:46-13:53Z, read-only ARM/Monitor queries confirmed
`gpt-5.4-mini` version`2026-03-17`, `DataZoneStandard`, capacity/currentCapacity1,
Succeeded, NoAutoUpgrade, **1 RPM /1,000 TPM**. The SwedenCentral subscription
usage line is1/200 units; Model Capacities independently reports199 additional
units available. These are deployment allocations, not requests already used.
No capacity, quota, release, ledger, role or other cloud configuration changed;
no inference was made. AI remained false on ready revision`--resume-locked`,
and the jobs list remained empty. Production/iPhone/participant scope is unchanged.

The cause of the allocation is local: `provision.py` explicitly writes
`modelCapacity: 1`, introduced in commit`c788aec` (AI-off bootstrap). Both protected
initial and acceptance parameter artifacts retain1, and `main.json` passes that
required parameter directly to the deployment SKU. Azure did not cap this account
at1. The bootstrap chose the smallest allocation without request-size-based
throughput sizing; no historical rationale beyond that explicit choice is proven.
The infrastructure template still allows1-20, and was not changed in this task.

### Rate estimation is not billing

Official documentation checked on2026-09-19:

- [Azure quota guide](https://learn.microsoft.com/en-us/azure/foundry/openai/how-to/quota):
  admission uses an approximate maximum processed-token estimate, including prompt
  size and the output cap; partly character-based, distinct from post-response
  billed usage. RPM can be enforced in1-10-second windows. Shared-capacity pressure
  and temporary effective-limit reductions can also yield429.
- [Azure model quotas](https://learn.microsoft.com/en-us/azure/foundry/openai/quotas-limits):
  ratios vary by model. Its GPT-5.4-mini GlobalStandard table has1 RPM/1,000 TPM;
  the actual DataZoneStandard ratio here is established by live ARM readback,
  not borrowed from another model or a generic tier table.
- [Azure reasoning parameters](https://learn.microsoft.com/en-us/azure/foundry/openai/how-to/reasoning):
  GPT-5.4-mini supports Chat Completions `max_completion_tokens`; it bounds
  visible output, reasoning and formatting. Our cap is2,000, reasoning is`none`,
  one result (`n=1`), no best-of multiplier. The quota guide calls the output
  parameter `max_tokens`; it does not publish the exact GPT-5.4-mini v1 estimator.
- [Azure vision guide](https://learn.microsoft.com/en-us/azure/foundry/openai/how-to/gpt-with-vision):
  image size/detail affect processing; its GPT-4-era tile examples are not a
  GPT-5.4-mini rate-limit formula. Our profile explicitly uses`detail=high`.
- [OpenAI vision calculation](https://developers.openai.com/api/docs/guides/images-vision#calculating-costs),
  supplementary, **not an Azure throttling specification**: current GPT-5.4-mini
  image billing uses32px patches, multiplier1.2, high-detail budget2,500 patches
  and maximum side2,048. Within our1,280px side bound this suggests at most
  1,600 patches /1,920 image input tokens, before prompt and output. Do not use
  GPT-4o tiles or GPT-4.1-mini's1.62 multiplier for this model, and do not turn
  this sizing estimate into a known charge or replace the full financial reserve.

The pilot permits one PNG/JPEG, at most3MiB decoded /1,280px per side, and
65,536 canonical bytes for messages plus schema. Compression bytes/base64 length
are not billed image-token counts. The exact Azure estimator's treatment of the
encoded image and strict schema is not specified in the reviewed sources.
Offline inspection of the existing image cases, with no payload logging:

| Case | Pixels | Image bytes | Base64 characters | Strict messages/schema bytes |
| --- | --- | ---: | ---: | ---: |
| L1 | 800x500 | 19,960 | 26,616 | 1,721 |
| L2 | 800x500 | 21,297 | 28,396 | 1,735 |
| P1 | 1000x883 | 126,348 | 168,464 | 1,735 |
| P5 | 1000x458 | 111,390 | 148,520 | 1,693 |

Therefore1,000 TPM is undersized for output-cap-aware text/image planning; merely
waiting65 seconds cannot fix an oversized individual estimate. Nevertheless,
six text/refinement requests succeeded with the same2,000 cap. That observation
prevents claiming that `2,000 >1,000` alone proves the exact rejection mechanism.
All four image requests received429, including L2 after hours without a request.
Input-related estimated-token pressure is the leading hypothesis; exact RPM/TPM
versus temporary shared-capacity attribution remains unknown because those
responses' provider IDs, Retry-After and rate headers were not retained.

### Proposed capacity and cost effect

Recommend **capacity20, expected20 RPM /20,000 TPM**, as the smallest rounded
planning allocation for the existing *short* requests at the gateway's ceiling
of four total requests/minute (two/person), not a proven service guarantee.
Budget roughly1,000 prompt/schema tokens +1,920 image tokens +2,000 output tokens
=4,920/request; four are19,680/minute, rounded up to20 units. The tested images
are smaller, and ordinary two-user use at one request/person/minute leaves about
half of this allowance spare. Text/refinement known input counts were437-924.
This is a transparent planning envelope, **not the Azure character estimator**.
At four worst-envelope requests/minute headroom is thin; spread arrivals and
inspect effective headers. Do not promise simultaneous acceptance in every
short RPM window, sustained maximum traffic, or all possible65,536-byte inputs.
Large/adversarial inputs or effective limits below ARM require separate sizing
review, not silent input-limit changes, capacity escalation, retries or fallback.
Neither capacity2 (little room beyond output) nor capacity4 (RPM alone) addresses
the input budget. A future approved capacity20 change needs19 of the199 free units;
verify actual resulting rate limits after propagation before enabling any call.

[Azure deployment-type billing](https://learn.microsoft.com/en-us/azure/foundry/foundry-models/concepts/deployment-types)
classifies DataZoneStandard as **pay-per-token**, unlike reserved PTU SKUs.
Raising this base-model Standard allocation does not purchase dedicated capacity
or add a fixed model hosting/PTU fee; it raises potential throughput. More actual
accepted consumption can cost more. Existing ACR/Functions/ACA/storage costs,
tax, FX, delayed billing and cleanup reserves remain. No SKU, price profile,
output cap, participant admission or budget limit was changed. No PTU is proposed.

### Four holds and minimum retest

Fresh Azure Monitor again reports six200/four429. ProcessedPromptTokens total4,457
and GeneratedTokens total897, with nonzero minute buckets only alongside the six
successful responses. These are aggregate metrics without a request-ID dimension,
not per-operation settlement or proof that rejected requests cost zero. One
Cost Management ActualCost query by resource returned429 (client-type wait19s).
It used a single HTTP POST with transport retries disabled and was **not retried**.
The last successful posted cost remains the earlier EUR0.0522464784475356 net,
not a current all-in total. No request-correlated financial evidence was obtained.
L1/L2/P1/P5 therefore each retain USD0.2343, total **USD0.9372**; no live ledger
was read through Exec, mutated or reconciled. Known charges remain USD0.008117175,
charged/held USD0.945317175, and the original lifetime counter stays10/USD2.343.
Protected receipts and new read-only evidence remain under the ignored private
pilot directory; provider/account identifiers and billing raw responses are not
committed. AI-off does not stop existing infrastructure charges.

The local diagnostic patch captures only bounded provider IDs, HTTP status,
Retry-After and six rate-limit headers on success/HTTP errors, in internal
metadata and the existing timestamped pilot log sink. Missing/invalid headers
are omitted; transport failures invent none. Public DTOs/errors/Retry-After and
the single-dispatch policy are unchanged. No credentials, image/text content or
raw error body is logged. No automatic retry, paid log destination or live rollout
was introduced. It cannot retrospectively recover missing IDs. For future runs,
capture diagnostic events against each case's private operation receipt under
the existing seven-day diagnostic retention and unknown-accounting exceptions.

The smallest **proposed new acceptance set is four attempts**, once each:
L1 per100g-label arithmetic; L2 per-serving distinction; P1 food recognition plus
portion/recipe uncertainty; P5 semantic non-food abstention. A transport failure
does not pass P5. Keep existing tolerances; do not repeat the six successful
text/refinement cases or add a diagnostic warmup. This is screening, not a
two-person load/latency guarantee or a weighed-photo accuracy claim.

Additional maximum model reserve: **4 x USD0.2343 = USD0.9372**. With explicit
conservative planning factors EUR1.20/USD and1.50 for tax, reserve EUR1.69 for
those new calls, plus a separate proposed EUR0.50 ancillary/cleanup envelope:
**EUR2.19 additional all-in retest reserve**, not an increase of the EUR20+5 cap.
Existing holds are not spent twice or released: retaining them and reserving
four new attempts would bring known/held/new model exposure to USD1.882517175.
Fresh billing or a separately accepted bounded delayed-billing assessment must
establish available room before approval; this query failure does not do so.

**Zero attempts remain authorized now.** The exhausted ten-attempt grant, policy
and counters were not extended/reset. Four future attempts require a separate
explicit, time-limited authorization and funded reserve, reviewed diagnostic
artifact build/scan and AI-off deployment/capacity change, fresh readbacks and
release evidence. Keep cases sequential at least65 seconds apart and respect
longer provider wait hints; stop for operator review on any429/unknown outcome,
never retry it automatically. Finish locked and clean. No wife's admission or
iPhone/production action is part of that proposal.

Local verification: **373 affected tests passed, one skipped**; actual SDK mock
transport, bounded/malformed headers, one attempt despite retry hints, unknown
usage preservation, configured INFO sink and unchanged public429 response.
Pylance syntax checks and editor diagnostics were clean. These tests do not
qualify live header availability or the proposed deployment capacity.

## Authorized capacity correction and four-case continuation

The owner explicitly authorized this continuation from `9988064`: change only the
existing private DataZoneStandard deployment to capacity20, deploy diagnostics,
and attempt L1, L2, P1 and P5 once each. Total acceptance ceiling14, not a fresh
14-attempt run. The original EUR20 period plus EUR5 setup budget and original
period end remain unchanged. No production, iPhone or participant change.

Fresh account/tenant/owner checks matched the private pilot. One bounded Cost
Management query succeeded with EUR0.0583771002919457728 net posted, no pagination.
That is delayed, incomplete billing, not all accrued cost. The existing EUR12
net operational stop is retained. A conservative EUR18 envelope for that stop
with a50% tax/FX/delay margin, the authorized additional EUR2.19, and EUR4.81
unallocated reserve sum to the existing EUR25, not new funding. Existing hosting,
unknown holds and cleanup obligations remain; no free-tier discount is assumed.

ARM readback after the update: DataZoneStandard capacity20/currentCapacity20,
Succeeded, request limit20 per60seconds and token limit20,000 per60seconds.
Model/version/NoAutoUpgrade and financial profile were not changed. This is
verified allocation, not a shared-capacity or latency guarantee.

New API-only image, pinned and initially deployed disabled:
`sha256:e0c48f7132f0864f543cb788d1c34d8d4c8917f08915b19053331c4505578098`.
Trivy reported zero vulnerability/secret findings, retaining the known Alpine
3.24 EOL-list warning. Offline digest-bound inventory verified the API-only
marker, no Copilot package/provider/CLI, Azure CLI, Git, Node or curl. Alpine's
existing BusyBox wget remains; this is not a claim of a shell-free image.
The active ready revision was `--correction-off`; all environment settings other
than image digest and policy were equal, and AI remained disabled. Fresh Easy
Auth, exact table-scoped gateway role, disabled Storage Shared Key, and scale
0..1 were verified unchanged.

The AI-off amendment requires the reviewed old policy, ledger hash and ETag,
exact10-attempt/USD2.343 lifetime counters, no active work, and the exact revised
policy hash. Its single CAS transaction changes only the ledger policy binding
and creates an immutable amendment receipt. Day/month count ceilings become14;
acceptance lifetime ceiling becomes14/USD3.2802. Daily/monthly USD2.343 cost caps,
time window, identities, payload hashes, all buckets and all10 operation records
stay unchanged. The four old unknown USD0.2343 holds were compared unchanged.
No new production ledger was initialized. New case receipts use `correction-`
keys, preserving the ten historical receipts and preventing repeat intents.

The image-only internal contract in the API-only artifact now requires strict
`is_food` plus a nullable estimate. Non-food must return false/null; inconsistent,
missing or malformed classification is rejected. False/null is mapped to the
existing public invalid-output error, with no saveable estimate and only a
payload-free semantic diagnostic. Ordinary production and public DTOs are
unchanged. Classification remains model-based; a single P5 case is not a
universal non-food detector. No second model call, retry or fallback is added.

Local verification before activation:774 passed,14 skipped across the complete
gateway suite. The skips include explicitly opt-in real integrations. Editor
diagnostics and whitespace checks were clean. Live completion evidence follows
after the remaining gates and four bounded cases; at this checkpoint no new
model request had been sent.

Fresh live qualification subsequently passed9 JWT/HMAC checks,6 body-boundary
checks, an actually issued foreign-workload token rejection, and isolated ledger
replay/unknown-hold/policy-drift checks. The real ledger and ETag were unchanged;
the isolated qualification partition was deleted. An initial Table probe expected
401/403 but observed anonymous404 (resource hiding); that failed qualification is
retained, not relabeled. A targeted follow-up established unauthorized backend403,
and the corrected complete qualification passed. The exact backend role remained
the sole assignment; Easy Auth remained equal to its previously qualified config.
Original native, privacy and price evidence was explicitly revalidated for the
unchanged boundaries without falsely claiming a new native login or consent.

Temporary job replicas can disappear before their console is retrieved. Subsequent
job receipts are AES-GCM encrypted with a purpose-derived key and create-only in a
separate diagnostic Table partition before being emitted in bounded log chunks.
Private local receipts are0600 under0700 directories. The ledger never contains
food input/output; synthetic result receipts are separate and removed after
verified local capture. No new data-plane role or paid log destination was added.

The one-hour synthetic grant was issued at15:25:17Z, expiring16:25:17Z, bound to
configuration SHA-256 `1fc49d54b62c2f19422bc075ff78f367a7cffa4df1966565e070f815ef12ea63`.
It uses the original fixed pilot-period expiry and does not authorize participants.
All four additional cases completed without provider429:

| Case | Gateway HTTP | End-to-end seconds | Known model USD | Evaluation |
| --- | ---: | ---: | ---: | --- |
| L1 | 200 | 13.431 | 0.0013794 | Exact300 kcal /15g protein /30g carbohydrate /12g fat |
| L2 | 200 | 2.067 | 0.001655775 | Exact180 kcal /6g protein /27g carbohydrate /4.5g fat; correct50g portion basis |
| P1 | 200 | 3.056 | 0.001749 | Cooked rice, assumed240g; unknown weight and invisible added oil/butter/ingredients with nutrition effects disclosed |
| P5 | 502 | 1.862 | 0.0008877 | Provider200 with valid non-food classification; semantic event confirmed, no public/saveable estimate |

The L1/L2 provider responses reported20 RPM/20,000 TPM,19 requests remaining and
18,807/18,802 token units remaining respectively, with3-second reset hints.
These are actual provider diagnostics, not the full financial reservation or
billed input-token count. Safe request IDs are retained privately. The measured
time includes gateway HTTP and ledger receipt handling, not an isolated provider
latency percentile. All ten old operation records still matched exactly.

P1's first job delivery failed before Python started: a184,848-character single
command argument exceeded Linux's per-argument limit. This is a container startup
failure, not a provider429 or a model response. The corrected private operator
transport splits the same bundle into at most12,000-character argv pieces and
joins them in memory; an offline roundtrip verified identical case content.
No automatic job or model retry is enabled. Before corrected delivery, require
an independent exact ledger/ETag comparison with the12-attempt L2 receipt and
absence of the create-only `correction-P1` intent; missing logs alone are not
evidence of zero model dispatch. Keep the failed execution evidence separately.
That independent read confirmed exactly12 attempts, identical ledger/ETag and no
P1 intent. The corrected delivery then produced exactly one provider request and
advanced the counter to13. P1's first keyword check looked only for recipe-related
words and was too narrow; the concrete warning describes invisible added
ingredients and their effect. Its semantic screening passes, without numeric
ground truth or a claim that confidence0.86 is calibrated. P1 also returned the
actual20/20,000 provider limits,19 remaining requests and18,807 remaining token
units. P5 was admitted only after another independently checked65-second gap.

P5's existing generic invalid-output error is intentional fail-closed behavior,
not a provider outage or an inferred success from a transport failure. The
provider returned200 with known usage; the use case emitted exactly one
`image_food_status=non_food` event and no estimate. The operation records a
successful, billable provider completion while the public meal response is
rejected. P5 also reports20/20,000 limits,19 remaining requests and18,815 token
units. All four provider IDs/header receipts are retained privately; no Retry-After
was returned and no429 occurred. Actual admission gaps were107,336 and110 seconds.

Final accounting:14 attempts, USD3.2802 lifetime full reserves (not actual spend),
USD0.005671875 known cost for the four new calls, USD0.01378905 known cost over
all ten provider successes, plus the same four USD0.2343 unknown holds totaling
USD0.9372. Conservative charged/held: **USD0.95098905**. Active0, blockedfalse,
remaining attempts0. Every one of the original ten operation records matched
exactly; no financial hold, replay fingerprint or counter was reset. One final
Cost Management query succeeded with the same EUR0.0583771002919457728 posted net,
no pagination: still delayed/incomplete, not a final all-in invoice. EUR20+5,
the original period, EUR12 net stop and hosting/tax/FX/cleanup reserves remain.
Final ARM again confirms capacity20,20 RPM/20,000 TPM. Azure Monitor counts14
requests (ten200/four429), agreeing with the authoritative ledger; aggregate metrics do not settle
the historical holds. The gateway was disabled first, then its release key rotated
and loaded through a versioned reference into the ready `--correction-locked`
revision. There is no remaining model authorization.

The final model-free job verified the new key in process, rejection of the same
still-unexpired configuration-bound grant, and all9 JWT/HMAC boundary checks
with valid analysis admission returning503. It confirmed14 operations, active0,
all10 historical operations unchanged, known cost13,789,050 units and unknown
holds937,200,000 units. Cleanup deleted exactly11 locally secured temporary rows
(four correction model receipts and seven encrypted diagnostic receipts), using
content hashes and ETags. The real ledger, operation records and ETag remained
unchanged; the immutable amendment audit was preserved. The diagnostic partition
was empty afterwards. All13 correction job executions were terminal before the
temporary job resource was deleted; a fresh list showed zero jobs. The sole
active gateway revision is `--correction-locked`, Healthy, with AI off. The local
ACR credential was removed and the dedicated Colima build VM stopped. Protected
local evidence remains subject to the already approved retention; cleanup does
not claim immediate erasure of platform logs or accounting exceptions.

Remaining ordinary-pilot blockers are concrete: the four historical holds lack
request-correlated financial resolution; participant/health-data purposes, legal
basis and abuse-monitoring exceptions still need clearance; the wife's own
identity/privacy/device acceptance is absent; and physical iPhone backup,
data-preserving update, review/save/cancel/manual-entry and failure-path acceptance
has not been performed. Four screening cases do not establish representative
photo accuracy, calibrated confidence, concurrent-load behavior or p95 latency.
Daily all-service cost review and retention/teardown duties remain operational,
not an installed unattended cap or cleanup scheduler. No separate missing DPA
signature was identified in the account-linked review. Production, installed
iPhone app and participant admission remain unchanged; no further model call is
authorized by unused budget headroom.

## Costs and stop conditions

The latest correction readback is **EUR0.0583771002919457728 net posted**, with
the model accounting and unchanged reserve assessment above. The13 correction
jobs add at most **USD0.01755** configured replica compute at the previously
reviewed180-second limits/rates; together with the earlier26 jobs,39 bounded
executions give **USD0.05265**. These are configured compute bounds, not all-in
invoices: control/storage/startup, gateway use, tax/FX and late billing remain
separately reserved. All14 model attempts are exhausted; four full-cost holds
remain. EUR20+5, the original period and EUR12 net stop are unchanged.

The following earlier cost snapshots are chronological evidence, superseded by
the correction readback above, not additional or renewed funding.

The prior continuation returned **EUR0.0522464784475356 net posted** since
the unchanged period start. Its final refresh returned management429; neither that
earlier amount nor the model usage ledger is an all-in accrued EUR invoice.
The ten additional180-second jobs add at most **USD0.01350** configured replica
compute at the previously reviewed rates, or **USD0.03510** for all26 bounded
jobs across both phases. Control/storage/startup, administrative Exec/gateway,
tax/FX and delayed billing remain separately reserved. The original EUR20 period
and EUR5 setup ceilings, hosting/cleanup reserves and EUR12 net operational stop
are unchanged. The ten-attempt model allowance is exhausted regardless of
remaining monetary headroom; unknown model usage still has its full financial hold.

Verified EUR public Consumption prices on 2026-09-19: ACR Basic EUR0.1431/day;
DataZone input EUR0.7084/million and output EUR4.2504/million. Public prices are
not a promise of actual contract rates. Billing currency EUR confirmed separately.
Cost Management initially returned429, then no rows; the new budget reports0.
These are delayed records, **not proof that no charges have accrued**.
An earlier pilot-filtered custom-period query returned429. The final auth-first
continuation query succeeded and reported **EUR0.0000621947449768161 net** since
the original period start. This is delayed, partial posted cost, not a final
accrued total or proof that hosting/registry costs are absent. Do not repeatedly
poll or treat throttling as free usage. The three bounded qualification jobs add
at most **USD0.00405** of configured replica compute at the reviewed active rates
(3 x180seconds x[0.25 x0.000024 +0.5 x0.000003]); platform/control/storage costs,
startup effects and tax remain separately reserved. No model spend is reported
by the unchanged acceptance ledger.

The subsequent issued-foreign-token job adds at most **USD0.00135** of configured
replica compute using the same180-second limit and rates. The four executions'
combined configured compute bound is **USD0.00540**, not an invoice or an all-in
setup cost. The existing tax, delayed billing, hosting and cleanup reserves remain.

Before model acceptance, the last successful custom-period query reported
**EUR0.00322847501287996 net**. Both the immediate pre-model and final post-model
queries returned429, without polling/retry loops. The recent posted amount plus
the unchanged conservative full-model, hosting, tax/FX, late-billing and cleanup
reserves supported the bounded run; posted records are not accrued totals.
There were **16 bounded job executions** in total: the earlier three and13 retained
in the final job execution list. At180seconds maximum each, their configured
replica-compute bound is **USD0.02160**. This excludes control/storage/startup/tax
effects and administrative Exec/gateway usage, which remain separately reserved.
The four-call known cost and L1 unknown hold above are authoritative ledger facts,
not replaced by the older zero-attempt snapshots in this chronological record.

- ACR thirty days: **EUR4.293 net**, about EUR5.109 including illustrative 19% VAT.
- Ten full 272k-input/2k-output reservations: **EUR2.011856 net**, about EUR2.395
  with 19% VAT. This is a token bound, not expected typical usage.
- Within the extra EUR5, retain about **EUR2.60** for setup hosting, operations,
  tax/rate variation and late billing. Do not double-count ACR days already in
  the thirty-day envelope. Stop setup if its remaining reserve is insufficient.
- Hosting/storage/KV/egress remain additional. Prior USD rates and before-grant
  assumptions in README remain the conservative reference; small EUR meter
  values from the latest query were rounded and were **not** interpreted as free.
  Use no free-grant discount until eligibility/remaining grant is verified.
- Operational all-service stop: **EUR12 cumulative net since period start**,
  or earlier if accrued estimates plus outstanding reservations, remaining fixed
  charges, expected tax and cleanup exceed the approved envelope. EUR12 plus 19%
  VAT leaves EUR5.72 of the EUR20 as conservative headroom; do not spend that
  reserve simply because invoices lag. Higher actual tax needs earlier stop.
- Azure's monthly budget is only a delayed notification. Its dates (September1
  to November1) are provider calendar boundaries, **not pilot authorization**.
  Sum September and October group costs for the exact thirty-day period; do not
  reset funding on October1. Actual80 alerts at EUR9.60 per calendar month.
- Owner: repository/subscription owner. Review cumulative costs and recent
  usage before activation, after acceptance, daily during operation and at each
  technical renewal. No unattended cost monitor or automatic hosting teardown
  has been installed. If monitoring cannot be maintained, leave AI off and
  remove the pilot rather than assume a budget alert stops billing.

Unauthenticated load, retries inside Azure control services, cold-start tails and
platform overlap can accrue hosting costs even with model admission off. The
policy is not an all-in DDoS spending cap. AI-off does not stop the registry fee.
No routine runtime flags may enable Copilot or reuse benchmark headroom.

## Concrete privacy review

This is technical/privacy preparation, not a legal opinion or participant
consent. The account-linked agreement acceptance below is verified; it must not
be mistaken for blanket approval of every processing purpose or retention policy.

| Service / data | Scope, retention and remaining decision |
| --- | --- |
| iOS / SwiftData | Existing local records remain on device. Only an explicit analysis sends selected text or preprocessed image. No device export or actual health data sent during deployment. |
| Entra / Easy Auth | Processes account IDs, authentication events and network metadata. Token store disabled at Functions. New native probe uses in-memory MSAL cache only. Tenant sign-in/audit retention and account deletion obligations remain to be recorded. |
| Functions / ACA | Request payloads transient in memory; no intended payload logging. No paid Log Analytics/Application Insights configured. Platform/administrative logs still exist; absence of app ingestion is not absence of Microsoft telemetry. Live payload-log verification remains open. |
| Azure OpenAI / Foundry Models | Azure-hosted, not an OpenAI-operated API. EU DataZone processing can span the zone, not Sweden only. `store=false`, no Responses/Assistants/Files/Batch or stored completions requested. No use for foundation-model training without permission according to official docs. |
| Abuse monitoring | The actual account has no `ContentLogging=false` capability. Do not assume modified monitoring approval. Automated review and possible authorized Microsoft human review remain; EEA deployments' human reviewers are stated to be in EEA. Exact applicable flagged-content retention/deletion and exceptions require confirmation; the current reviewed pages did not establish a numeric retention ceiling. |
| Table | Real pilot ledger: pseudonymous HMAC identifiers, operation state, count/cost/uncertainty, no raw input/result. The isolated temporary qualification partition held synthetic results only, deleted after verified private receipt. Configured operation retention31days is implemented cleanup logic, not an installed recurring cleanup scheduler. Preserve accounting/holds during any transition. |
| Blob / ACR / Key Vault | Backend package, container code and secrets, no nutrition archive. Key Vault soft-deleted material is purge-protected7days. Deleting the live group does not instantly erase provider-retained or soft-deleted data. |

### Account-linked contract evidence, 2026-09-19

Read-only ARM Billing API2024-04-01 linked this exact private subscription's
`billingProperty/default` to its billing account. The account's `agreements`
collection, expanded with `Participants`, contains one Microsoft Customer
Agreement: **Active**, **ClickToAccept**, effective
**2026-09-18T13:33:53.9101293Z**. Its participant is **Accepted** at that same
instant and matches the verified owner's contact. Only the boolean match is
reported; names, contacts, billing identifiers and signed document links remain
private. No contractual acceptance or signature was performed by this agent.

The `agreementLink` returned an Office viewer; its authorized WOPI content was
downloaded privately as the actual German **Microsoft-Kundenvertrag**, not a
generic replacement downloaded from a public template page. Original DOCX SHA-256:
`72431ff06d62e32ba19f49aed82e256caecc6a895334d87725c50b13c4e8c3ac`.
Its footer identifies `Microsoft Customer Agreement: 102C9D654B3C`. This is the
document's observed identifier, **not a proven publication/revision date**. The
acceptance timestamp likewise does not establish the template's revision date.

The actual document contains these relevant provisions:

- Opening agreement paragraph: DPA, applicable Product Terms and SLAs are
  constituents of the agreement.
- **Datenschutz und -verarbeitung**: processing follows the agreement and DPA,
  expressly incorporated by reference. Required third-party permissions remain
  the customer's responsibility.
- **Definitionen**, **DPA**: refers to the Microsoft Products and Services Data
  Protection Addendum at `https://aka.ms/DPA`, as updated.
- **Vertragsaenderungen**, DPA/SLA: their own update provisions govern changes.
  **Rangfolge** places DPA ahead of these general terms and Product Terms.
- **Ergaenzende-Einkaufsbedingungen fuer Einzelne Nutzer**, definition and item5:
  a specifically defined Individual User is a person **other than an
  administrator**, subscribing for members of the subscriber's organization;
  item5 replaces the privacy section with the Microsoft Privacy Statement for
  that category. Private payment alone does not establish that category. The
  verified owner is also this tenant's administrator; no employer/school
  self-service purchase was established. Do not erase this exception or assume
  it applies merely because the subscription is privately paid.

The public DPA page currently identifies **English, May2026**, listed
May22,2026. The retrieved document SHA-256 is
`d79e06734ddff63593375c5134f3e362da7ddf6d265308776a2c7db4b7233f41`.
Its **Applicable DPA Terms and Updates / Limits on Updates** applies the then-current
DPA at purchase/renewal for the subscription term, with separately stated
new-feature and government-requirement exceptions. This supports May2026 for the
new September subscription on the available publication record; ARM does not
return a separately signed DPA or a customer-specific DPA version field. Do not
claim a separately executed DPA or immutable future terms.

The MCA **Privacy & Security Terms / General** describes DPA obligations and its
priority. **Core Online Services** includes Functions/App Service, Container
Apps, ACR, Microsoft Entra ID and Foundry Models sold by Azure. Product-specific
exceptions still apply, notably Bing grounding/Web IQ, which this pilot does not
use. This is not a claim that every Microsoft account/billing activity is solely
processor activity or that EU DataZone eliminates transfer exceptions.

On the available contract text, a **separate DPA signature is not an identified
missing step**: the accepted MCA incorporates it directly. The evidence does
not require the owner to make a blanket assertion of legal clearance. Verified
portal navigation for account inspection is **Azure portal > Cost Management +
Billing > Billing scopes > the private MCA billing account > Settings >
Properties** (skip scope selection if only one exists). The contract itself was
retrieved via that account's Billing REST `agreements` collection and its
`agreementLink`; no unverified portal signing workflow is asserted.

The owner's current instruction permits only synthetic inputs and necessary own
account metadata; wife and real health/private inputs remain excluded. Following
the concrete contract findings, the owner expressly approved local technical
diagnostic retention of at most7days and pseudonymous operation retention
of31days. Spend and uncertain holds remain until resolved, without resetting
attempt limits. Cleanup is operator-managed, not scheduled. Necessary contract/
billing evidence stays access-controlled and outside Git. This approval does not
override Microsoft platform, abuse, legal or soft-delete retention and does not
promise complete erasure within7/31days. It is an explicit bounded operational
decision, not a blanket legal attestation. The operator must review diagnostic
expiry by2026-09-26 and operation cleanup after the applicable31days; unresolved
accounting must not be deleted to make a cleanup appear complete.

Transfers: EU DataZone and EU Data Boundary are not unconditional promises of
no third-country access. Boundary commitments have documented limited transfer,
support and security exceptions; nonregional service/ARM settings also matter.
Record applicable SCCs/other transfer basis, subprocessors, support access and
necessary supplementary measures under the actual agreement. Do not attest a
transfer-impact assessment or consent based only on the chosen region.

Legal basis: assess whether the strictly personal/family activity falls under
GDPR Article2(2)(c); do not silently assume that exception for cloud processing
or any later sharing. If GDPR applies, document controller/contact, purpose,
Article6 basis and, where nutrition/fitness becomes health data, an Article9
condition. Explicit, informed, freely given and withdrawable consent may be the
chosen path, but no such consent has been collected here. Synthetic prompts do
not remove the separate account/IP/accounting metadata processing obligation.

Participant information before enabling real input must state data categories,
recipients/services, estimate limitations, processing geography/transfer
exceptions, abuse review/retention, deletion limits, contact, rights/withdrawal
and a usable manual-entry alternative. Wife admission additionally requires her
actual tenant identity, her own information/decision and physical-device
acceptance. Do not infer consent from spouse relationship or a paid subscription.

DPIA screening: tiny private scope and no automated health decision reduce risk;
health inference, images, new AI technology, credential compromise and external
processing increase it. This is not a documented large-scale Article35(3)(b)
operation, but owner must assess Article35 high-risk criteria and applicable
supervisory lists, record the conclusion/reasons, and perform a DPIA if required.
No automatic diagnosis, treatment advice or automatic saving is authorized.

Official sources reviewed:

- [Azure model data/privacy](https://learn.microsoft.com/en-us/azure/ai-foundry/responsible-ai/openai/data-privacy)
- [Abuse monitoring](https://learn.microsoft.com/en-us/azure/ai-foundry/openai/concepts/abuse-monitoring)
- [Microsoft DPA](https://www.microsoft.com/licensing/docs/view/Microsoft-Products-and-Services-Data-Protection-Addendum-DPA)
- [MCA Privacy and Security Terms](https://www.microsoft.com/licensing/terms/product/PrivacyandSecurityTerms/MCA)
- [Account agreements and participants API](https://learn.microsoft.com/en-us/rest/api/billing/agreements/list-by-billing-account?view=rest-billing-2024-04-01)
- [MCA billing account and portal properties](https://learn.microsoft.com/en-us/azure/cost-management-billing/understand/mca-overview)
- [EU Data Boundary and exceptions](https://learn.microsoft.com/en-us/privacy/eudb/eu-data-boundary-learn)

## Resume, stop and cleanup

Use only the original private Azure CLI configuration directory. Pass it via
`--azure-config` to `provision.py`; never replace the default work CLI context.
The helper verifies account/tenant, stores private state and refuses to repeat
an unresolved mutation. After a failed operation, inspect the actual resource
and private diagnostics before resuming; do not delete an intent to blindly retry.
`prepare.py acceptance-manifest` and backend/Entra/iOS packaging are offline.
Deployments use `main.json`; runtime parameters remain private and AI false.
The deployment record and private operation files preserve the intervening
provider validation corrections. `provision.py` intentionally cannot activate AI.

Both `provision.py login-probe` and the subsequent `login-analysis-probe` have
passed; do not repeat them merely to reconfirm completed evidence. Their tokens
were intentionally discarded. Never substitute an administrative CLI token for
the native client, broaden consent, or paste credentials into chat. Complete
fresh configuration-bound evidence before any later release, and resolve the
recorded unknown hold without discarding its cost or reusing an attempt. The
original release key is revoked; historical private parameter files are evidence,
not a ready-to-apply activation configuration. All14 authorized attempts have
now been spent. The four-case capacity correction passed its bounded label/photo/
non-food screening; four historical provider429 costs remain unknown. No further
model attempt is allowed under this exhausted grant. This screening is not a
general quality/latency guarantee, participant release or device acceptance.
The old release-first HTTP circularity has already been corrected.

On a stop trigger or no later than the period end:

1. Set `AI_API_ONLY_ENABLED=false` on the new gateway and revoke its signed
   release; never alter the existing production app. Stop the new Functions app
   and deactivate the new gateway revisions. Verify analysis no longer works.
   Already-dispatched/unknown model operations remain charged/reserved.
2. Before teardown, retain a minimal access-controlled accounting/uncertainty
   and cost snapshot with the approved retention. Do not dump payloads, keys or
   tokens. No participant nutrition data is stored in this pilot ledger.
3. Delete **only** `pft-pilot-20260919` after matching its recorded ownership and
   inventory. This also removes the billed ACR; stopping compute alone is not
   cleanup. Preserve the unrelated `rg-pft-mini-bench-screen20260918` storage and
   every production resource. Wait for deletion completion; inspect for residual
   managed resources, storage, budgets and late charges without broad deletion.
4. Remove only the three new Entra registrations/service principals and their
   new consent/role bindings recorded in private state. Managed identities are
   removed with their resources. Do not revoke old production identities/tokens.
5. Verify Key Vault's seven-day purge-protected recovery period and provider
   deletion/retention exceptions; do not claim immediate irreversible erasure.
   Delete local secret-bearing runtime files, logs and token material after the
   approved evidence retention. Keep only sanitized deployment/accounting facts.
6. Recheck delayed costs after teardown. No automatic extension or renewal of
   funding, privacy basis or participant scope is permitted.

## iPhone acceptance, not yet performed

No TestFlight and no automatic installation. `ios/Config/Pilot.local.xcconfig`
was generated from the real deployment outputs and is ignored by Git. Existing
Debug/Release settings remain unchanged unless the explicit pilot xcconfig is
selected. Unsigned build output is outside the repository.

Before a signed update on the owner's device: export/backup existing records,
record meal/workout/weight/settings counts, connect the existing iPhone and use
the same bundle/team identity. **Do not uninstall** and do not recreate SwiftData.
Verify installed launch, native sign-in/redirect/cancellation, data counts and
manual entry first; use only approved nonprivate analysis fixtures after server
qualification. Verify review/save-once/cancel and network-loss handling. An
unsigned build alone cannot establish any of these physical-device properties.
Rollback is an accepted API-only build or AI off, never Copilot fallback.