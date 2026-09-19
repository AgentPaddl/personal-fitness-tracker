# Private pilot deployment: 2026-09-19

## Authorization and current state

User authorization: EUR 20 total for the first 30 days, plus EUR 5 once for setup
and acceptance, at most ten targeted nonprivate model attempts, no automatic
retry or extension. These are operational stop thresholds with acknowledged
billing residual risk, not guaranteed invoice ceilings. The prior benchmark is
separate. No production deployment, installed app or private record was changed.

Deployment is **AI off, not accepted for ordinary use**. No real nutrition/image
data and no model request were sent. Acceptance counter: **0/10**. No signed
release was created. Only the authenticated owner's identity is configured;
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
| OpenAI `pft-pilot-20260919-model` | Local key authentication disabled; `pilot-mini`, GPT-5.4-mini `2026-03-17`, DataZoneStandard capacity1, NoAutoUpgrade |
| Managed identities | Separate `pft-pilot-20260919-backend-id` and `pft-pilot-20260919-gateway-id` |
| Entra registrations | Three new single-tenant applications/service principals: native client, backend API, gateway API |
| Budget | Resource-group cost budget EUR12; Actual80 and Forecast100 notifications to the owner's existing Entra contact |

Backend: `https://pft-pilot-20260919-api.azurewebsites.net/api`.
Gateway: `https://pft-pilot-20260919-gateway.gentleriver-150ab3f0.swedencentral.azurecontainerapps.io`.
The app knows only the backend URL and public Entra configuration.

Published image:
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

Still required before any model call: analysis-route Easy Auth claim mapping;
end-to-end backend Managed Identity JWT/HMAC; native and
foreign workload rejection; delegated/direct bypass attempts; actual ingress
body/slow-client/scale behavior; active-path log inspection and live
revocation/renewal qualification. Offline regressions do not attest these checks.
No `CHECKS` record has been fabricated and no signature has been issued.
The gateway remains `AI_API_ONLY_ENABLED=false`. The backend's similarly named
flag is true to select mandatory workload authentication; it is not an enabled
gateway model release. No model request was made during this continuation.

### Existing-path qualification blocker

The blocker after the successful Table run is **not another throttle**.
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

## Costs and stop conditions

Verified EUR public Consumption prices on 2026-09-19: ACR Basic EUR0.1431/day;
DataZone input EUR0.7084/million and output EUR4.2504/million. Public prices are
not a promise of actual contract rates. Billing currency EUR confirmed separately.
Cost Management initially returned429, then no rows; the new budget reports0.
These are delayed records, **not proof that no charges have accrued**.
The final pilot-filtered custom-period query again returned429; no final accrued
cost total is asserted. Do not repeatedly poll or treat throttling as free usage.

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

This is technical/privacy preparation, not a legal opinion, executed DPA,
attestation of agreement acceptance or participant consent.

| Service / data | Scope, retention and remaining decision |
| --- | --- |
| iOS / SwiftData | Existing local records remain on device. Only an explicit analysis sends selected text or preprocessed image. No device export or actual health data sent during deployment. |
| Entra / Easy Auth | Processes account IDs, authentication events and network metadata. Token store disabled at Functions. New native probe uses in-memory MSAL cache only. Tenant sign-in/audit retention and account deletion obligations remain to be recorded. |
| Functions / ACA | Request payloads transient in memory; no intended payload logging. No paid Log Analytics/Application Insights configured. Platform/administrative logs still exist; absence of app ingestion is not absence of Microsoft telemetry. Live payload-log verification remains open. |
| Azure OpenAI / Foundry Models | Azure-hosted, not an OpenAI-operated API. EU DataZone processing can span the zone, not Sweden only. `store=false`, no Responses/Assistants/Files/Batch or stored completions requested. No use for foundation-model training without permission according to official docs. |
| Abuse monitoring | The actual account has no `ContentLogging=false` capability. Do not assume modified monitoring approval. Automated review and possible authorized Microsoft human review remain; EEA deployments' human reviewers are stated to be in EEA. Exact applicable flagged-content retention/deletion and exceptions require confirmation; the current reviewed pages did not establish a numeric retention ceiling. |
| Table | Pseudonymous HMAC identifiers, operation state, count/cost/uncertainty, no raw input/result. Configured operation retention31days is implemented cleanup logic, not an installed recurring cleanup scheduler. Preserve accounting/holds during any transition. |
| Blob / ACR / Key Vault | Backend package, container code and secrets, no nutrition archive. Key Vault soft-deleted material is purge-protected7days. Deleting the live group does not instantly erase provider-retained or soft-deleted data. |

Contract path: subscription billing metadata identifies Microsoft Customer
Agreement. The published Microsoft Products and Services DPA applies through
applicable Product Terms; the publicly available DPA is not evidence that the
specific customer executed/accepted every applicable document. Owner must retain
the actual agreement/version, confirm Azure/Entra/Foundry coverage, processor
terms and subprocessor notification arrangements. No contractual click-through
or signature was performed by this agent. DPA page's current English document:
May22,2026; verify against the customer's actual contract, not only publication.

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

The initial `provision.py login-probe` has passed; do not repeat it just to
reconfirm the same readiness result. Further authenticated analysis qualification
needs a reviewed bounded runner and a fresh personal sign-in because the probe
intentionally discarded its tokens. Never substitute an administrative CLI token
for the native client, broaden consent, or paste credentials into chat. Complete
the outstanding model-free safety probes first; do not sign incomplete evidence
to get around the current release-first HTTP gate.

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