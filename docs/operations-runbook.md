# Operations runbook

Practical, sanitized procedures for operating the deployed production stack. No
secret values appear anywhere in this document — only resource names, setting
*names*, and commands with placeholders for anything sensitive.

## Paid API migration boundary (2026-09-17)

The procedures below describe the existing Copilot deployment. The
[paid API migration decision](architecture.md#paid-api-migration-decision-2026-09-17)
governs preparation for external users; no deployment or credential change is
authorized by that decision. The first local Azure adapter package now rejects
production selection and does not claim readiness; it changes no deployed
configuration. Its configuration and offline tests are documented in the
[gateway README](../ai-gateway/README.md#local-azure-api-adapter-2026-09-17).

Before external AI use, replace the Copilot runtime and close its old endpoint,
revision and credential paths, with independently funded API access, privacy
foundations, verified allowed identities and distributed usage controls in place.
The generic previous-revision rollback procedures in sections 2 and 4 must **not**
be used to route external users back to Copilot. For that rollout, prepare and
verify a known API-only rollback artifact that retains the admission controls,
or disable AI. Keep public contracts and local device data intact.

## Protected two-person pilot (local implementation)

Status: **not activated, not production-ready**. `AI_PILOT_ENABLED` defaults to
`false`; the existing private path is unchanged, not approved for external users.
In pilot mode the backend requires verified claims even in development, and the
gateway requires both the existing service token and a valid backend assertion.
Only Azure may be selected. The Azure adapter's existing per-call production
guard and negative readiness remain active without modification. Nothing here
authorizes a cloud resource, deployment, funded request or real-user test.

### Identity and trust ownership

Easy Auth must validate access-token signature, lifetime, issuer and audience,
require authentication with an API-appropriate 401, and remove caller-supplied
`X-MS-*` identity headers. Restrict tenant and allowed client applications in its
platform policy too. No direct Function-host/alternate ingress may bypass that
boundary. `EASY_AUTH_ENABLED=true` is an operator assertion, **not proof** that
Azure is enforcing those controls. These deployment properties are unverified.

The application cannot distinguish a forged full principal header from a real
platform header on an ingress that bypasses Easy Auth. Its parser is authorization
after platform authentication, not independent JWT verification. Enabling the flag
on a directly reachable local/custom Function host is therefore unsafe. Activation
requires live negative tests with forged headers, missing/invalid access tokens and
every alternate ingress, proving rejection before the handler. Synthetic header
fixtures exercise the parser only and must never be cited as proof of provenance.

The backend additionally checks `auth_typ=aad`, UUID `tid` and `oid`, an exact
tenant-specific `iss`, exact `aud`, the configured `azp`/`appid` client (both must
agree when present), and membership of the required delegated `scp`. It accepts
the standard mapped tenant/object/scope claim names and rejects duplicates,
missing or conflicting claims. `X-MS-CLIENT-PRINCIPAL-ID` must agree with `oid`.
No email, display name, ID token decoding or freely supplied user ID authorizes
a caller. Both backend and Coordinator enforce a nonempty allowlist with at most
two `(tid, oid)` pairs. App-only tokens without the delegated scope are rejected.

Before deployment, verify the actual Easy Auth header mapping and presence of
every required claim, including audience/issuer, without logging the claims.
Microsoft notes that claim mapping can depend on token-store configuration;
assess its retention before enabling it, do not silently add token persistence.
The implementation fails closed if claims are absent; tests do not prove the
platform supplied them. See [identity headers](https://learn.microsoft.com/en-us/azure/app-service/configure-authentication-user-identities)
and [tenant/audience/client authorization](https://learn.microsoft.com/en-us/azure/app-service/configure-authentication-provider-aad).

Backend-to-gateway: an HMAC-SHA256 assertion in `X-Pilot-Authorization` binds
`tid`, `oid`, `X-Operation-Id`, a canonical JSON body digest, issue time and a
fixed gateway audience. The gateway accepts at most 60 seconds of age and five
seconds of future skew, verifies the body before normalization, and rechecks the
allowlist before reservation. The backend generates this header; it never
forwards a client's alleged assertion, identity or bearer token. A captured
assertion cannot authorize changed content and a replay consumes the same
operation. HTTPS, private/restricted ingress and protection of both server-side
secrets remain required. Possession of the signing key compromises this trust
boundary; it is not intended to protect against a compromised backend.

### Explicit configuration

Pilot settings are read from the **process environment**. Export them or use the
approved platform secret/configuration mechanism; merely writing a `.env` file
does not activate them. Do not paste real keys or identities into tracked files.
Unknown boolean values fail closed. Required values have no budget/person defaults.

| Location | Settings and meaning |
| --- | --- |
| Both services | `AI_PILOT_ENABLED=true` only after separate approval; `AI_PILOT_ALLOWLIST_JSON` as an array of one or two objects with UUID `tid`/`oid`; `AI_PILOT_SIGNING_KEY` as the same high-entropy secret of at least 32 bytes; existing `GATEWAY_SERVICE_TOKEN`. |
| Backend | `EASY_AUTH_ENABLED=true`, `AI_PILOT_TENANT_ID`, `AI_PILOT_ISSUER`, `AI_PILOT_AUDIENCE`, `AI_PILOT_CLIENT_ID`, `AI_PILOT_SCOPE`, all exact values from the reviewed Entra configuration. |
| Gateway | Existing explicit Azure endpoint/key/routes/prices/output cap, `AI_PILOT_FINGERPRINT_KEY` as a separate high-entropy secret of at least 32 bytes, `AI_PILOT_POLICY_JSON`, `AI_PILOT_TABLE_ENDPOINT`, `AI_PILOT_TABLE_NAME`. |

`AI_PILOT_POLICY_JSON` has these required fields (extra fields are rejected):

| Field | Constraint/semantics |
| --- | --- |
| `version` | Explicit policy identifier. |
| `person`, `total` | Each contains positive integer `minute`, `day`, `month`, `concurrent` (1-20), and positive Decimal USD `daily_usd`, `monthly_usd`. No example amount is an approved budget. |
| `operation_max_age_seconds` | 60-86400; maximum UUIDv7 age accepted at initial reservation. Up to 30 seconds future skew is accepted. |
| `retention_seconds` | Exactly 2678400 (31 days); exceeds the operation acceptance window and covers any calendar month. |
| `max_text_schema_bytes` | 1-65536 bytes for canonical generated messages plus schema, including static instructions and refinement. |
| `max_image_bytes`, `max_image_dimension` | At most 3145728 bytes and 4096 pixels per side; at most one image. Existing MIME/content checks remain independent. |
| `max_output_tokens` | 1-32768, at least the configured adapter cap; the request must carry an explicit cap no larger than this. |
| `deployment_verified_until` | Unix seconds; expiration of an externally reviewed deployment/model/rate attestation. Not an automatic cloud capability probe. |

All instances must use one table, partition `pilot-v1`, fingerprint key, allowlist,
routes, price table and policy. Their combined HMAC is persisted in the ledger;
mismatch blocks admission, including key/policy changes and stale replicas.
Do not create a new partition or empty ledger to work around limits. Policy/key
migration needs stopped admission and an audited carry-forward of current counts,
reserved cost, active operations and tombstones. It is deliberately not automatic.

### Cost bound and accounting

Only the explicitly reviewed `gpt-4.1-mini-2025-04-14` profile is supported for
pilot cost admission today. Reserve **1047576 input tokens**, its full documented
context maximum, plus the enforced request output cap. This includes image/schema
input conservatively instead of inferring image cost from file bytes or assuming
an average prompt. Use the larger configured input/cached-input rate, no cache
discount, and the output rate. Reserves/charges round upward to integer nano-USD;
budget ceilings round downward, never increasing the configured approval.
This is intentionally expensive admission and may deny a small budget even for a
small request. No optimized tokenizer/image bound is claimed. Reference:
[model context/output limits](https://developers.openai.com/api/docs/models/gpt-4.1-mini).

Before activation, verify that the actual Azure deployment is that exact model,
uses the reviewed billing SKU/region, and that the price table covers all applicable
rate bands. Configuration alone does not establish these facts. Unknown models,
missing prices, expired attestation, missing caps and excessive inputs deny dispatch.
No tools, model substitution, paid counting calls or automatic provider retries.

Reconciliation uses actual valid usage and the versioned price table: noncached
input plus cached input plus completion tokens. Reasoning is a subset of completion,
not an additional charge. Missing usage/cache details or unmatched prices retains
the full reserve, never zero. Request counts never refund failures. Charges attach
to their original UTC admission day/month, including calls crossing midnight.
Current minute/day/month buckets are retained; expired buckets cannot debit a new
period. Reported bound/model violations close the ledger for investigation; they
cannot undo a charge already made. Provider billing remains authoritative, and
hosting/storage/tax/FX charges are outside these model-token budgets.

### Atomicity, operations and failures

The gateway Coordinator is the **only** reservation and dispatch authority. The
backend signs and forwards but never debits budgets. The use case invokes the
Coordinator before the provider; the Azure adapter additionally consumes a
request-bound, expiring, single-use in-process permit in pilot mode. A direct
gateway call with only a service token, or a direct adapter call without a permit,
cannot skip the controls. An assertion sent to a non-pilot gateway is rejected,
preventing a backend/gateway mode mismatch from silently entering the private path.

One Azure Table transaction creates the `pending` operation and replaces the
shared ledger using `If-Match`/ETag. All person/global period counts, cost and
active-operation slots change atomically in that same partition. A second
conditional write records `unknown` **before** a permit exists. Only confirmed
CAS conflicts may retry reservation (at most three times); timeouts/unclear write
acknowledgements never dispatch. Table SDK retries are disabled. No in-memory
store or automatic empty-ledger fallback exists in runtime code. This relies on
[Azure Table entity-group transactions](https://learn.microsoft.com/en-us/rest/api/storageservices/performing-entity-group-transactions),
not read consistency across independent updates. Synchronized clocks are required;
a clock behind the last admission or cleanup timestamp fails closed. Minute limits use fixed
UTC minute buckets, not a sliding 60-second window.

`X-Operation-Id` is additive and optional on the existing private API; in pilot
mode it must be a current UUIDv7. The UUID timestamp is part of the key and cannot
be refreshed without creating a **new** operation. Scope the key to verified
identity and HMAC the normalized JSON request, including its base64 image string,
not multipart boundaries. Different content returns `409 operation_conflict`;
any existing `pending`, `unknown`, `succeeded` or `failed` operation returns
`409 operation_consumed` and never dispatches again. No estimate is stored, so
even a succeeded operation has **no result retrieval/replay**. Lost responses do
not authorize replacement calls. New explicit user actions require new, separately
budgeted IDs. `X-Request-Id` remains diagnostic only, not an idempotency key.

UUIDv7 is required because its immutable timestamp permits rejecting the same old
ID after its tombstone is erased. Arbitrary UUIDv4 keys cannot provide that bounded
retention guarantee without a separate persistent expiry mechanism. The client
timestamp is untrusted: it controls only the age check, never identity, permission,
reservation time or UTC budget period. Altering the timestamp creates a new key and
still requires authorization and a full fresh reservation. Acceptance is inclusive
from server time minus `operation_max_age_seconds` through server time plus 30 seconds.
The signed assertion has its separate, shorter 60-second age/five-second future window.

Future iOS contract (not implemented in this package): mint one UUIDv7 with a current
UTC millisecond timestamp and cryptographically random remaining bits per logical
analysis action. Retain it together with the immutable submitted payload and account
across timeout, app restart and manual transport retry; do not regenerate it per HTTP
attempt or refresh its timestamp. Preserve the same image bytes/base64 and normalized
fields. Editing content, accepting a new refinement step, or changing account creates
a separate explicitly confirmed action. Use a distinct diagnostic request ID.
Do not automatically replace an expired/rejected/consumed operation with a new ID.
An uncertain response has no result-replay endpoint: present the uncertainty and
require explicit user confirmation before a new potentially chargeable analysis.

Crash after reservation leaves `pending` and its full reserve/slot. Crash after
the second write leaves `unknown`, whether the remote model received anything or
not. Timeouts, cancellation and ambiguous failures keep full reserves and slots;
no automatic lease takeover. A valid response or a known billed failure is settled
atomically with its costs and releases the slot; missing usage on an otherwise
valid response still retains full cost. An uncertain settlement write can lose the
response but never authorizes another dispatch. `succeeded` means provider
generation completed, not that iOS received/saved an estimate; authoritative
use-case business validation can still reject it. A retained slot may deliberately
stop this small pilot until an operator investigates.

Public codes use the existing error envelope: 403 `pilot_forbidden`, 400
`operation_required`, 409 conflict/consumed, 429 `pilot_limit`, 413 `pilot_input`,
503 `pilot_unavailable`. Backend messages are allowlisted, not copied from raw
upstream exceptions. There is no automatic client retry instruction or Retry-After
for uncertain pilot operations.

### Table setup and retention

No resource is created by application startup. A later approved operator must
provide an existing Azure Storage Table (not Cosmos Table), restricted network
access and system-assigned managed identity with least-privilege Table data access.
`AzureTableStore.connect` accepts only Azure HTTPS Table account endpoints and
uses `ManagedIdentityCredential`, not ambient developer/CLI credentials. Provisioning,
RBAC/network validation and actual transaction tests remain separate steps.

Initialize only an empty approved pilot ledger, once, through the conditional
create operation `store.commit([("ledger", coordinator.initial_ledger(), None)])`.
An existing ledger must never be overwritten/reset. No production initialization
was run. After an ambiguous initialization response, inspect the existing row
under controlled administration instead of replacing it. A missing/deleted ledger
blocks all model calls even if some operation rows remain.

Store only HMAC person/operation keys and fingerprints, state/timestamps, policy
digest and aggregate counts/costs. No meal text, image, estimate or bearer token.
Fingerprints and derived identifiers remain pseudonymous personal data; access,
backups and diagnostics require retention controls. Neither fingerprints nor
assertions/identities/operations may be logged. The existing content-free request
logs and normalized error codes remain; SDK payload logging stays disabled.

Schedule `AzureTableStore.cleanup(now, 2678400)` at least hourly through a separately
approved maintenance task; it is not automatically scheduled by this package.
It conditionally deletes at most 50 expired operation rows per invocation with a
15-second deadline. Repeat scheduled invocations to clear backlog and alert on any
failure or record older than 31 days plus the maintenance interval. Old UUIDv7 IDs
are rejected by age even after their row is deleted, preventing redispatch after
cleanup. Do not accept arbitrary UUIDs or extend the acceptance window past retention.

Before querying or deleting rows, cleanup conditionally persists its server-time
high-water mark in the shared ledger. A failed/uncertain ledger write stops deletion;
a backward admission clock then fails closed even after tombstones have disappeared.
Do not reset that mark or restore an older ledger to recover availability after a
clock jump. Correct the clock and use audited reconciliation. This ordering is covered
by an offline regression that previously reproduced a second dispatch after deletion
and a large server-clock rollback.

Expired `pending`/`unknown` rows cause the ledger to be persistently **blocked before
deletion** and their active identifier to be removed, preserving privacy without
silently reopening admission. No automated unblock exists. Reconcile unknown charges
and verify no calls remain in flight before an audited operator recovery; never set
unknown spend to zero. Coordinate policy/key changes, shutdown and maintenance.
For decommissioning, stop admission, retain necessary non-content billing totals
under a separately reviewed policy, and erase keys/allowlists/backup copies according
to that policy. No indefinite duplicate guarantee beyond supported IDs is claimed.

### Evidence and remaining activation work

Offline tests use a shared CAS **model** across Coordinator instances, Table
transaction-call assertions, real Table SDK batch serialization on a no-network
transport, and the real OpenAI SDK on mock HTTP transport. They
cover simultaneous operations, budgets, failures after each write, missing usage,
scope/allowlist rejection, signed-body tampering, direct gateway/adapter calls and
backend text/image/refinement contracts. They do not prove actual Azure isolation,
network/RBAC correctness, identity-header provenance or production billing bounds.

`tests/test_pilot_table_integration.py` is a **real service**, separately authorized
test, skipped unless `RUN_AZURE_TABLE_INTEGRATION_TESTS=1`. It requires explicit
`PILOT_TEST_TABLE_ENDPOINT`/`PILOT_TEST_TABLE_NAME` and a managed-identity execution
environment, writes only synthetic records in a unique test partition of that
existing table, tests two clients racing, and removes its records afterward.
Do not set the flag during ordinary tests. No real Table test was run here; multi-
process interruption/network-fault testing and billing reconciliation remain gates.

Before any external release: stable iOS UUIDv7 operations preserved across retries
of the same logical action (not yet implemented); review/confirmation before creating
a replacement operation; claim-chain and Table integration evidence; privately funded
account/privacy approvals; budget approval and verified deployment/rates; API-only
production artifact and rollback with old Copilot routes/credentials closed. Removing
the Azure production guard requires a separate approved change. Do not disable the
pilot flag as an external-user rollback to the existing Copilot path.

## 1. Deployment architecture (as actually deployed)

```text
iPhone (Trainingsplan app)
    |  MSAL / Entra ID sign-in (public client, no secret)
    v
Azure App Service Authentication / Easy Auth
    |  (rejects unauthenticated/unauthorized requests before Function code runs)
    v
Azure Function App: fitness-tracker-api-bk  (Flex Consumption, Linux, Python 3.13)
    |  HTTPS, X-Service-Token: GATEWAY_SERVICE_TOKEN
    v
Azure Container Apps: fitness-tracker-gateway
  (environment: fitness-tracker-gateway-env, external HTTPS ingress)
    |  COPILOT_GITHUB_TOKEN
    v
GitHub Copilot SDK (Copilot CLI, headless/server mode)
```

Real Azure resources currently in use (resource group `fitness-tracker-rg`, region **Germany West Central**):

| Resource | Name | Purpose |
| --- | --- | --- |
| Function App | `fitness-tracker-api-bk` | Public backend API, Easy Auth boundary |
| Function App user-assigned identity | `fitness-tracker-api-bk-uami` | Reserved for future managed-identity needs (no longer used by the removed Azure OpenAI integration) |
| Storage account | `fitnesstrackerrga2b3` | Function App storage |
| App Service Plan | `ASP-fitnesstrackerrg-afbd` | Function App hosting plan |
| Application Insights | `fitness-tracker-api-bk` (component) | Backend telemetry, workspace-linked (see §5) |
| Container Apps Environment | `fitness-tracker-gateway-env` | Hosts the gateway Container App |
| Container App | `fitness-tracker-gateway` | Personal AI Gateway (FastAPI, real `GitHubCopilotProvider`) |
| Container Registry | `fitnesstrackeracr` | Gateway image storage (Basic SKU, admin user disabled, pulled via the Container App's system-assigned managed identity + `AcrPull` role) |
| Log Analytics workspace | `fitness-tracker-gateway-logs` | Shared workspace for the gateway environment and (as of Phase 11 Step 2) the backend's Application Insights component |

Easy Auth identity providers in use: **Microsoft Entra ID** only, with the backend API app registration as the trusted audience and the iOS app's client ID as the sole allowed application (`defaultAuthorizationPolicy.allowedApplications`).

## 2. `COPILOT_GITHUB_TOKEN` rotation

**Where it's stored:** a Container Apps *secret* named `copilot-github-token` on the `fitness-tracker-gateway` Container App, referenced by the `COPILOT_GITHUB_TOKEN` environment variable. It is a **fine-grained GitHub personal access token tied to the operator's own GitHub account and Copilot subscription/seat** — a long-lived user credential for unattended SDK use, not a GitHub App server-to-server installation token (that mechanism was explicitly evaluated and rejected for this deployment: it targets organization-attributed billing, expires hourly, and would require building token-minting/refresh infrastructure this repo doesn't have — see `ai-gateway/README.md` and the Phase 10 authentication analysis).

**Rotation sequence:**
1. Generate a new fine-grained PAT on GitHub tied to the same account/Copilot subscription, with a fresh expiry. Never paste it into chat/AI tooling — type it directly into a terminal you control.
2. Update the Container App secret:
   ```
   az containerapp secret set \
     --name fitness-tracker-gateway -g fitness-tracker-rg \
     --secrets copilot-github-token=<NEW_TOKEN_VALUE>
   ```
3. **A new revision is created automatically** — updating a secret referenced by an active revision's environment triggers a new revision rollout on `fitness-tracker-gateway` (Container Apps' standard behavior for secret changes referenced via `secretRef`).
4. Wait for the new revision to reach `Provisioned`/`Healthy`:
   ```
   az containerapp revision list -g fitness-tracker-rg -n fitness-tracker-gateway \
     --query "[].{name:name, active:properties.active, healthState:properties.healthState, trafficWeight:properties.trafficWeight}" -o table
   ```
5. Verify readiness against the **new** revision:
   ```
   curl -sS -w "\nHTTP_STATUS=%{http_code}\n" https://fitness-tracker-gateway.<env-domain>/readyz
   ```
   Expect `{"status":"ready"}` / `200`. This exercises real Copilot auth without a billed call.
6. Revoke the **old** PAT on GitHub only after the new revision is confirmed healthy and `/readyz` passes.

**Rollback if the new token fails:** Container Apps keeps prior revisions. Reactivate the last known-good revision immediately:
```
az containerapp revision activate -g fitness-tracker-rg -n fitness-tracker-gateway --revision <PREVIOUS_REVISION_NAME>
```
Then investigate the new token (permission scope, expiry, org policy) before retrying. The old PAT should not be revoked until a working replacement is confirmed — keep both valid during the transition window.

## 3. `GATEWAY_SERVICE_TOKEN` rotation

**Where both copies live:**
- Container Apps secret `gateway-service-token` on `fitness-tracker-gateway`, referenced by the `GATEWAY_SERVICE_TOKEN` environment variable.
- Function App setting `GATEWAY_SERVICE_TOKEN` on `fitness-tracker-api-bk` (must hold the *identical* value).

**Safe, zero-downtime rotation using `GATEWAY_SERVICE_TOKEN_PREVIOUS`:**

The gateway's config (`app/config.py`) supports a `GATEWAY_SERVICE_TOKEN_PREVIOUS` value so it accepts *either* the current or previous token during a rotation window — this is what avoids downtime.

1. Generate a new high-entropy token locally (e.g. `openssl rand -base64 32`), never printed/logged.
2. On the **gateway**, set the *current* value as `GATEWAY_SERVICE_TOKEN_PREVIOUS` and the *new* value as `GATEWAY_SERVICE_TOKEN` in the same update (both as Container Apps secrets):
   ```
   az containerapp secret set -g fitness-tracker-rg -n fitness-tracker-gateway \
     --secrets gateway-service-token=<NEW_VALUE> gateway-service-token-previous=<OLD_VALUE>
   ```
   Ensure the Container App's env vars include `GATEWAY_SERVICE_TOKEN_PREVIOUS=secretref:gateway-service-token-previous` (add it once if not already present).
3. Wait for the new gateway revision to become healthy (same check as §2 step 4).
4. Update the **backend** Function App setting to the new value:
   ```
   az functionapp config appsettings set -g fitness-tracker-rg -n fitness-tracker-api-bk \
     --settings "GATEWAY_SERVICE_TOKEN=<NEW_VALUE>"
   ```
   During the window between steps 2 and 4, the gateway accepts both old and new tokens, so in-flight backend requests using the old value never fail.
5. Verify backend→gateway connectivity end-to-end:
   ```
   curl -sS -w "\nHTTP_STATUS=%{http_code}\n" https://fitness-tracker-api-bk-ckewh6fhd0gmfkcd.germanywestcentral-01.azurewebsites.net/api/readiness
   ```
   (Requires an authenticated Easy Auth session/token — see the real-device smoke test procedure for the only currently-available authenticated verification path.) A real device food-analysis request is the most reliable end-to-end check.
6. Once confirmed, remove `GATEWAY_SERVICE_TOKEN_PREVIOUS` from the gateway (delete the secret and its env var reference) to close the rotation window.

## 4. Deployment / recovery

**Gateway image build & deploy:**
```
cd ai-gateway
az acr build --registry fitnesstrackeracr --image fitness-tracker-gateway:<TAG> --file Dockerfile .
az containerapp update -g fitness-tracker-rg -n fitness-tracker-gateway \
  --image fitnesstrackeracr.azurecr.io/fitness-tracker-gateway:<TAG>
```
`az containerapp update` with a new image creates a new revision automatically.

**Backend deploy:**
```
cd backend
func azure functionapp publish fitness-tracker-api-bk --python
```
Respects `.funcignore` (excludes `local.settings.json`, `.venv`, `tests/`). Does not touch App Settings or Easy Auth config.

**Health/readiness checks:**
| Target | Command | Expected |
| --- | --- | --- |
| Gateway liveness | `curl https://fitness-tracker-gateway.<domain>/healthz` | `200 {"status":"ok"}` |
| Gateway readiness | `curl https://fitness-tracker-gateway.<domain>/readyz` | `200 {"status":"ready"}` |
| Backend health | `curl https://fitness-tracker-api-bk-.../api/health` | `401` without a valid Easy Auth session (expected — platform-level auth, not a failure); real verification requires an authenticated caller (real device or MSAL device-code flow using the iOS app's own client ID). **Not yet explicitly HTTP-smoke-tested** — what's actually proven is that all three routes (`health`, `readiness`, `food-analysis`) are deployed, and a real production `/api/food-analysis` call succeeded end-to-end (which only happens after Easy Auth, so it implies the auth boundary works, but `/api/health`/`/api/readiness` themselves have not been individually exercised with an authenticated call) |
| Backend readiness | `curl https://fitness-tracker-api-bk-.../api/readiness` | Same caveat as above — not yet individually smoke-tested |

**Container Apps revision rollback:**
```
az containerapp revision list -g fitness-tracker-rg -n fitness-tracker-gateway -o table
az containerapp revision activate -g fitness-tracker-rg -n fitness-tracker-gateway --revision <REVISION_NAME>
```
Stateless gateway — no data-loss risk in rollback.

**Backend rollback:** re-run `func azure functionapp publish` with a previously known-good working tree checked out (e.g. `git checkout <previous-commit> -- backend/` then republish), since Flex Consumption does not support the classic publishing-profile/slot-based rollback commands.

## 5. Monitoring

- Application Insights component `fitness-tracker-api-bk` is **workspace-linked** to Log Analytics workspace `fitness-tracker-gateway-logs` (fixed in Phase 11 Step 2 — it was previously orphaned with no workspace link, so telemetry silently had nowhere to land).
- Because it's workspace-based, **query the newer schema table names**, not the classic ones:
  | Classic name | Workspace-based name |
  | --- | --- |
  | `requests` | `AppRequests` |
  | `traces` | `AppTraces` |
  | `dependencies` | `AppDependencies` |
  | `exceptions` | `AppExceptions` |
  Example: `az monitor log-analytics query -w <workspace-customer-id> --analytics-query "AppRequests | where TimeGenerated > ago(1h)"`.
- Gateway logs: `az containerapp logs show -g fitness-tracker-rg -n fitness-tracker-gateway --tail 50`.
- **Never** enable request/response body logging, and never log image bytes, food descriptions, authorization headers, or tokens — both the backend and gateway are designed to log only path/use-case/status/latency/error-category (see `backend/AGENTS.md` and `ai-gateway` code comments). Any future logging change must preserve this.

## 6. Known deferred hardening

- **Current state:** the gateway uses **external HTTPS ingress** protected by `GATEWAY_SERVICE_TOKEN` (a shared-secret header check), not a private VNet/internal-ingress topology.
- **Why this is acceptable for now:** this is a private, single-user personal app with no public documentation of the gateway's URL, HTTPS-only transport, and a required service token on every `/v1/*` call. A full private-networking topology (VNet integration on the Function App + an internal Container Apps Environment) was evaluated during Phase 10 planning and found to add substantial first-deployment complexity (new VNet/subnets, DNS resolution, an environment type that's fixed at creation and not cheaply convertible later) without a proportional security benefit at this usage scale and threat model.
- **Deferred, not rejected:** IP allow-listing (restricting the gateway's ingress to the Function App's outbound IPs) was intentionally deferred because Flex Consumption's outbound IP addresses are not yet confirmed stable enough to commit to an allow-list without further verification. Full private VNet integration remains a valid future upgrade if the app's usage or threat model changes (e.g. if it's ever exposed beyond a single user).
