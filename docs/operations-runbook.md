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

The legacy `gpt-4.1-mini-2025-04-14` pilot profile remains available explicitly;
the [GPT-5.4-mini implementation below](#gpt-54-mini-local-profile-implementation-2026-09-18)
adds a separate pinned profile, never automatic substitution. The legacy profile
reserves **1047576 input tokens**, its full documented
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

### GPT-5.4-mini candidate review (2026-09-18)

This is a preparation record, not an activation or model-change approval. At
baseline commit `0cfb53a`, `Coordinator.bound` and `Coordinator.settle` still pin
`gpt-4.1-mini-2025-04-14` and its input bound. Changing a route or price entry
alone cannot admit GPT-5.4-mini. The Azure adapter still rejects production calls
and reports negative readiness. No provider call or cloud write is part of this
review.

The target topology is variant B: a publicly reachable HTTPS gateway callable
only by the authorized backend, not directly by iOS. The existing service token
and request-bound HMAC remain required; they do not yet implement backend workload
identity verification. Before activation, add exact backend identity/role
authorization, early authentication and bounded ingress, and verify that no
alternate ingress bypasses them. Public reachability is not anonymous access.
The existing Table network restriction is not silently waived by this topology;
its resolution remains a separate release gate.

#### Verified model and deployment evidence

Read-only checks used the separately authenticated private subscription after
rechecking its subscription/tenant IDs and Enabled state. ARM API `2024-10-01`:
`locations/{region}/models`, `locations/{region}/usages`, and
`modelCapacities?modelFormat=OpenAI&modelName=gpt-5.4-mini&modelVersion=2026-03-17`
under `/subscriptions/{subscription}/providers/Microsoft.CognitiveServices/`.
No credentials or personal request data were queried. Results on 2026-09-18:

| Property | Evidence and interpretation |
| --- | --- |
| Candidate | Azure OpenAI `gpt-5.4-mini`, version `2026-03-17`; expected snapshot identifier `gpt-5.4-mini-2026-03-17`. Actual response identifier still requires verification, not a wildcard match. |
| Deployment | EU `DataZoneStandard`, Sweden Central proposed; on-demand standard token billing, not Global, Priority, Batch or PTU. EU processing follows the EU Data Boundary, including possible EFTA locations, not Sweden-only residency. |
| Lifecycle | Sweden Central catalog: `GenerallyAvailable`; inference/SKU deprecation `2027-09-21`. Microsoft's retirement schedule agrees. Recheck before activation and review replacement planning by 2027-06-21. |
| Quota | `OpenAI.DataZoneStandard.gpt-5.4-mini`: limit 200, current 0, unit thousands of TPM, in each of Sweden Central, Germany West Central, France Central and West Europe. Thus 200,000 TPM unallocated per checked region, not a summed capacity promise. |
| Capacity | Version-specific DataZoneStandard `availableCapacity=200` in those same four regions; all queried lists had null continuation links. This is a point-in-time report, not a reservation or successful deployment. GPT-4.1-mini DataZone quota remains explicitly 0 in each region. |
| Rate units | Catalog reports 1 request/minute and 1,000 TPM per capacity unit. A later allocation of 20 units would imply 20 RPM/20,000 TPM, subject to revalidation; neither allocation nor monthly budget is created by quota availability. |
| Interfaces | Microsoft lists text/image input, text output, structured outputs, system/developer messages, Chat Completions and Responses. Retain `/openai/v1/chat/completions` with deployment name and `response_format=json_schema`, `strict=true`; no Responses migration or new adapter is needed for this use case. |
| Limits | Microsoft and OpenAI list 400,000 context, maximum 272,000 input and 128,000 output tokens. Input and output share context; reasoning is part of output. These are model limits, not recommended pilot caps. |

The Microsoft reasoning-model feature matrix explicitly includes this version;
the generic structured-output guide's older model list does not yet list it.
Live compatibility of this exact schema/image/request combination remains a
benchmark gate. OpenAI lists reasoning efforts `none` (default), `low`, `medium`,
`high`, `xhigh`. Propose explicit `none` initially, not an assumed Azure default;
reject an unsupported setting rather than silently substituting another effort.
`max_completion_tokens=2000` would cap visible text, formatting and reasoning
combined. It does not promise 2,000 visible tokens or a complete estimate. A
reasoning-heavy or truncated response can be billed without a usable result.
Do not copy the generic vision guide's `max_tokens` or retry recommendations.

#### Price snapshot and monthly scenarios

Azure Retail Prices API, retrieved 2026-09-18, `productName=Azure OpenAI GPT5`,
`armRegionName=swedencentral`, `type=Consumption`, `currencyCode=USD`, unit `1M`,
`effectiveStartDate=2026-03-01T00:00:00Z`:

| SKU | USD / million tokens | Meter ID |
| --- | ---: | --- |
| `5.4 mini Inp Dz` | 0.825 | `fc81bb98-83fa-569b-a361-70d5904b285d` |
| `5.4 mini cd Inp Dz` | 0.0825 | `41b51273-5b41-5b0b-ba4b-3900379c9800` |
| `5.4 mini Opt Dz` | 4.95 | `3167a76c-f4a1-53f1-8784-362e76c0787e` |

Reproduce with GET `https://prices.azure.com/api/retail/prices`, `currencyCode='USD'`,
filter on the product/region and these exact SKU names; follow `NextPageLink` if
present (null here). Empty earlier filters were not zero prices. The web price
table rounds input/cache to 0.83/0.09; calculations use the precise meters above.
No mini-specific long-context band was found in the checked regular meters;
do not import GPT-5.4 full-model premiums or prices. Revalidate all applicable
bands/tier before a funded run. This snapshot is not an installed or approved
`PriceTable.version`; a future explicit version must bind deployment, model,
billing tier and these rates. No cache discount is assumed for admission.

For input I, cached subset C and total billable output O:
`cost_usd = ((I-C)*0.825 + C*0.0825 + O*4.95)/1000000`.
Reasoning tokens are already in O, never added a second time. Image tokens are
input tokens, not base64 characters or an image-generation fee. This profile
uses no tools, paid cache-storage feature or additional model-service meter.

**Scenarios, not measured consumption:** 4,000 total billable input tokens and
1,000 total billable output tokens per request, no cached tokens. Cost per request
is `0.00330 + 0.00495 = USD 0.00825`.

| Requests per person/month | People | Total requests | Total input / output tokens | USD per person | USD both people |
| ---: | ---: | ---: | --- | ---: | ---: |
| 300 | 2 | 600 | 2,400,000 / 600,000 | 2.475 | 4.95 |
| 600 | 2 | 1,200 | 4,800,000 / 1,200,000 | 4.95 | 9.90 |

Independent sensitivities relative to that baseline, not forecasts or guarantees:

| Additional assumption | USD/month, 600 base requests | USD/month, 1,200 base requests |
| --- | ---: | ---: |
| 3,000 extra billable image-input tokens on every base request | 6.435 | 12.87 |
| 1,000 extra reasoning/output tokens on every base request (2,000 output total) | 7.92 | 15.84 |
| 20% extra correction requests, each assumed 4,000 input + 1,000 output | 5.94 | 11.88 |

Do not add image or reasoning tokens again when already included in the baseline.
The 3,000 and 20% examples are sensitivity assumptions, not observed image costs
or correction frequency. Corrections are separate billable operations and can
resend a larger current estimate; they do not resend the photo. If monthly
request counts already include corrections, do not apply another multiplier.
Three successful correction rounds can make four calls per initial analysis;
failures/new explicit operations also consume the server's request and cost caps.
Each extra 1,000 input tokens adds USD 0.000825; 1,000 output adds USD 0.00495.
The previous USD 10 total monthly proposal has virtually no headroom at 1,200
baseline calls, before reservation headroom, images or corrections. A budget is
not a promise to serve the proposed call count. All figures exclude hosting,
storage, tax and FX; the subscription is billed in EUR under its actual contract.

#### Safer reservation without an invented small bound

The smallest initial implementation can use this model's documented **272,000
maximum input**, covering text, final schema, framing and images collectively,
plus the enforced total output cap. With the reviewed standard rates and 2,000
output tokens: `(272000*0.825 + 2000*4.95)/1000000 = USD 0.2343`, or 234,300,000
nano-USD. At 4,000 output it is USD 0.2442, requiring separate cap approval.
This is a conditional model-token bound for the attested snapshot/tier, not a
universal billing guarantee, prepayment or currently implemented policy.
It is lower than the prior GPT-4.1-mini reserve of USD 0.46445344 at 2,000 output.
Blindly carrying over its 1,047,576 input cap at the new rates would reserve
USD 0.8741502. Neither that old limit nor its image rules belong in this profile.

A substantially tighter per-request bound remains **unproven**. Prepare one
immutable final request before admission, including the transformed strict
schema. Count text with a reviewed model tokenizer or proved byte bound, include
all framing/schema overhead, and add a version/detail-specific image bound based
on validated pixels. The current 64 KiB pre-transformation cap, one-image/3 MiB/
4,096-pixel safety limits and average token estimates do not prove that sum.
OpenAI's current image guide lists 32-pixel patches, multiplier 1.2 and a
2,500-patch/2,048-pixel limit for GPT-5.4-mini `high` (`auto` maps to `high`),
with possible one-token rounding variation. Azure's generic vision guide instead
describes older tile behavior; Azure equivalence is not established by these
reads. Do not certify a 3,000-token Azure image ceiling from that example.

Use the full model-input bound or reject if any accounting term is unproved;
pin an explicit reviewed detail level instead of relying on `auto`. A 10,000-input/
2,000-output calculation would be USD 0.01815, but **must not become the reserve**
until that input bound is proved and enforced. Sample maxima, a percentile plus
margin, post-call overrun detection, and a later benchmark cannot prove a universal
pre-dispatch bound. Preserve atomic reservation, full unknown-outcome retention,
single dispatch and failure counting. Binding model/tier/price version and the
actual input/output bounds to the operation lets settlement detect violations;
it cannot undo provider spend that already occurred.

#### Smallest implementation and benchmark decision

**Suitable for a model-profile implementation and a separately approved limited
benchmark, not yet for activation.** Nutrition quality, label accuracy, latency,
usage completeness and real Azure response identity remain unmeasured. No
alternative provider or speculative adapter is justified at this stage.

1. Add one explicit reviewed model profile to the existing Azure path, consumed
  by both `Coordinator.bound` and `Coordinator.settle`: snapshot identity,
  272,000 input maximum, enforced pilot output cap and standard billing tier.
  Include the profile in the policy digest/attestation; unknown model/profile
  denies admission. Reuse `PriceTable`'s three-rate arithmetic with a new explicit
  version. Never accept arbitrary configured model names merely to remove the
  old hard-coded check. Carry forward the existing ledger on a policy change.
2. Add server-side, profile-bound `reasoning_effort` and image `detail` to the
  existing adapter/configuration. Start with explicit `none`, a reviewed `high`
  detail, and the existing 2,000 completion cap; these settings need Azure
  validation. Explicitly pin/attest the ordinary service tier before dispatch;
  reject unexpected tier metadata rather than price Priority at Standard rates.
  Keep system/user messages, strict schema and local business
  validation, `store=false`, `stream=false`, `n=1`, no tools, no retries or
  fallback. Keep both production guards and negative readiness unchanged.
  Raising the software's 32,768 ceiling to the model's 128,000 is unnecessary.
3. Extend existing mock tests for this exact profile, outgoing parameters, price
  and returned-model mismatch, input/output violations, cached/reasoning usage,
  billed truncation/refusal and unknown outcomes. Store/check the effective
  per-operation cap, not only the broader policy cap, before introducing tighter
  request-specific reserves. No iOS/public contract or new provider is needed.
4. Implement variant B authorization as a separate release prerequisite:
  backend Managed Identity token acquisition for the gateway audience; strict
  signature/issuer/tenant/audience/lifetime verification, exact backend
  principal/client and app-role authorization; retain independent HMAC and
  service token. Verify header provenance and all revisions/alternate ingress.
  Entra authentication alone accepts too broad a caller set. Bound bodies before
  JSON/image work and bound scaling/logs; model budgets are not hosting-cost caps.

Next package: the model profile, explicit parameters and offline regression tests
only. After that, seek separate resource/funding approval for **one pass of the
existing 18 synthetic/staged benchmark cases**, one candidate, at most 18 attempts,
no paid warmups/repairs/retries. With the full input reserve and 2,000 output cap,
`18*0.2343 = USD 4.2174`; propose a separate USD 5 model-only ceiling, not approval.
Unknown operations keep reserve/slots and may stop the run before 18 attempts.
The historical 54-repeat candidate / 162-call comparison and its USD 1.53 bound
do not apply; 54 attempts at this conservative reserve would be USD 12.6522.
Measure usage (including reasoning/cache), cost per usable result, truncations,
schema/label/correction accuracy and cold/warm latency against the existing
rubric. One pass is screening, not proof of the earlier 95%/p95 release targets.
Stop for unsupported parameters, identity/rate mismatch or bound violation; do
not silently raise caps or switch models. If screening fails, first assess the
smallest change within this profile; only then review another Azure model with
fresh quota/capability/pricing evidence, without prebuilding another adapter.

Sources checked 2026-09-18: [Azure reasoning and limits](https://learn.microsoft.com/en-us/azure/foundry/openai/how-to/reasoning),
[retirement schedule](https://learn.microsoft.com/en-us/azure/foundry/openai/concepts/model-retirement-schedule),
[deployment types](https://learn.microsoft.com/en-us/azure/foundry/foundry-models/concepts/deployment-types),
[structured outputs](https://learn.microsoft.com/en-us/azure/foundry/openai/how-to/structured-outputs),
[Azure vision](https://learn.microsoft.com/en-us/azure/foundry/openai/how-to/gpt-with-vision),
[Azure pricing](https://azure.microsoft.com/en-us/pricing/details/cognitive-services/openai-service/),
[Retail API](https://prices.azure.com/api/retail/prices),
[OpenAI model details](https://developers.openai.com/api/docs/models/gpt-5.4-mini),
[OpenAI image accounting](https://developers.openai.com/api/docs/guides/images-vision),
[gateway Entra authorization](https://learn.microsoft.com/en-us/azure/container-apps/authentication-entra#daemon-client-application-service-to-service-calls).
Validation: 46 existing targeted offline adapter/pilot tests passed, covering
production denial, strict single-call transport, disabled retries, output caps,
unknown/model/price handling and cache/reasoning accounting. These exercise the
current baseline with mocks, not a GPT-5.4-mini deployment or a live token bound.

### GPT-5.4-mini local profile implementation (2026-09-18)

The subsequently authorized code package implements the reviewed profile; it does
not activate the pilot or amend the historical review's evidence/assumptions.
No cloud resources, paid calls or production configuration were changed.
The adapter still requires `APP_ENV=development` or `test` on every call and its
readiness remains false. Public/backend/iOS contracts remain provider-neutral.

Configuration has **no automatic profile selection**. Use the following shapes
only after the relevant approval; `benchmark-deployment` is a placeholder, not
an existing resource. All routes must name explicitly bound deployments, and all
profile and price deployment keys must agree exactly:

```json
{"food_text_v1":"benchmark-deployment","food_image_v1":"benchmark-deployment"}
```

The above is `AZURE_OPENAI_MODEL_ROUTES_JSON`. Set `AZURE_OPENAI_PROFILES_JSON` to:

```json
{"benchmark-deployment":"gpt-5.4-mini-2026-03-17-dz-v1"}
```

And `AZURE_OPENAI_PRICES_JSON` to:

```json
{
  "version": "azure-sweden-dz-2026-09-18-v1",
  "currency": "USD",
  "deployments": {
    "benchmark-deployment": {
      "model": "gpt-5.4-mini-2026-03-17",
      "input_per_million": "0.825",
      "cached_input_per_million": "0.0825",
      "output_per_million": "4.95"
    }
  }
}
```

`GPT_54_MINI` in `app/providers/pricing.py` is the immutable reviewed definition:
model/version `gpt-5.4-mini` / `2026-03-17`, SKU `DataZoneStandard`, region
`swedencentral`. The response must name exactly `gpt-5.4-mini-2026-03-17` and tier
`default`; absent/other identities deny the result and close the pilot ledger
for investigation. This expectation is not live Azure verification. A different
Azure response identifier requires review, not an alias/wildcard workaround.
The profile pins `reasoning_effort=none`, image `detail=high` and
`service_tier=default`; incompatible/unknown profile overrides and changed rates
or price versions fail closed. Capability/configuration errors get no retry.

Final source cross-check (2026-09-18): Microsoft's [reasoning matrix](https://learn.microsoft.com/en-us/azure/foundry/openai/how-to/reasoning)
names this exact mini snapshot and Chat Completions/output-cap support; its
`none` footnote names the GPT-5.4 family, not a separate mini-specific default.
The [Azure Chat reference](https://learn.microsoft.com/en-us/rest/api/microsoft-foundry/azureopenai/chat)
documents lowercase `none`, `image_url.detail=high` and total
`max_completion_tokens`. Microsoft's [processing-tier guide](https://learn.microsoft.com/en-us/azure/foundry/openai/concepts/priority-processing)
explicitly documents `service_tier=default` for standard pricing in Chat
Completions and `default` in standard-tier responses. Priority is not supported
for EU DataZone; no priority capability is assumed here. These are documented
contracts, not proof of this exact request on a Sweden deployment; older Azure
examples also contain null tier metadata. Missing tier still stops the run.
`deployment_verified_until` is an operator attestation deadline, not an ARM
lookup: before setting it, independently verify the resource ID/endpoint,
deployment name, model/version, region, SKU, default tier, upgrade policy and
current prices. The policy digest binds the configured expectations, not proof
that Azure currently matches them. Disable admission on deployment changes.

Use `AI_PROVIDER_MAX_OUTPUT_TOKENS=2000` and policy `max_output_tokens=2000` for
the manifest. Smaller explicit caps are allowed; larger profile configuration
is rejected. The SDK receives `max_completion_tokens`, capped by both adapter
and request. It includes reasoning/formatting/visible output, not 2,000 visible
tokens plus hidden tokens. No `max_tokens`, sampling controls, tools or repairs
are introduced. Both original business constraints and strict transport schema
are checked; a billed refusal/truncation, including reasoning-only exhaustion,
never becomes a usable estimate.

Admission computes `(272000*max(0.825,0.0825) + 2000*4.95)/1000000`, then rounds
up to nano-USD: **234300000 = USD 0.2343**. It is not a flat fee. Actual cost uses
noncached input, cached input and total completion exactly once. Raw JSON integer
checks precede SDK coercion; missing/invalid counts never release reserve as zero.
Successful valid output may still have unknown cost. Refused/truncated results
with valid matching usage are charged; unknown outcomes keep reserve/slots.

The operation atomically stores deployment, returned-model expectation, profile,
price version, service tier and effective input/output caps. The single-use permit
binds the request to deployment/profile/price/output cap as well. Settlement checks
the operation's cap, not just the potentially larger current policy ceiling;
reported violations block further admission and cannot undo existing spend.
The policy digest now includes full profile parameters and configured adapter
cap, including an empty profile map for the legacy path. Existing ledgers therefore
require stopped admission and audited carry-forward even when retaining GPT-4.1;
do not reset, silently migrate, or discard unknown operations.

For the benchmark, `AI_PILOT_POLICY_JSON` must additionally include a `benchmark`
object with `run_id`, `manifest_sha256` (SHA-256 of `canonical(manifest)`),
`max_attempts: 18`, `max_reserved_usd: "4.2174"` and an approved Unix-seconds
`expires_at`. These fields are part of the policy digest. The shared ledger holds
the run's permanent `attempts` and cumulative admitted `reserved` counters;
reservation updates them atomically with the operation and all period limits.
Neither settlement, day/month rollover, a new Coordinator nor tombstone cleanup
replenishes them. Unknown attempts stay counted and reserved. Missing/malformed
run state or a changed run/manifest fails closed; never initialize a replacement
ledger to continue a partially consumed run. Ordinary non-benchmark policies
remain supported, but are not authorization for this 18-attempt benchmark.

#### Offline preparation and isolated real-run prerequisites

The [versioned manifest](../ai-gateway/tests/fixtures/gpt54-mini-benchmark.v1.json)
fixes 6 text, 6 public-photo, 4 refinement and 2 rendered-label cases, references,
tolerances and result fields. Refinements use a fixed baseline, never a paid setup
call. All eight image assets are now local and hash-bound; the offline test checks
their full decode, format, dimensions and missing EXIF and uses their real bytes.
See [sources, attribution, transformations and nutrition uncertainty](../ai-gateway/tests/fixtures/gpt54-mini-assets/README.md).
The six photo inputs derive from three public photos, not six independent meals.
Their weights/recipes are unknown, so they have **no numeric nutrition ground
truth**. Numerical scoring is restricted to declared text/refinement/label
references. Assets and labels were visually inspected, not evaluated by a model.
Freeze final manifest/prompt/schema hashes and obtain owner approval before funding.

Offline check, from `ai-gateway/`, with the existing test environment:

```sh
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -B -m pytest -q -p no:cacheprovider tests/test_pilot.py -k benchmark_manifest
```

This always uses SDK MockTransport and MemoryCAS, synthetic identities/keys and
verified HMACs; it has no live switch. It proves 18 distinct single dispatches,
duplicate rejection, rejection of a 19th attempt, and summed reserves of
`18*0.2343 = USD 4.2174`. It does not prove Azure availability, Table isolation,
real identity authorization, photo quality, nutrition quality or latency.

A later genuine benchmark must use a **separately authorized, isolated nonproduction
environment**, not relabel a production service as development. The existing
supported service topology preserves the regular authenticated backend -> gateway
-> Coordinator -> adapter path. The local-only runner below is implemented but
not cloud-approved and cannot be enabled through test dependency overrides:

1. Obtain resource/funding/privacy approval and review endpoint, exact deployed
   version, Sweden Central DataZoneStandard, ordinary tier, all rates and expiring
   `deployment_verified_until` attestation. Configure real identities separately
   from synthetic case content. Live compatibility confirmation consumes one of
   the 18 attempts, not an additional paid smoke call.
2. Use isolated nonproduction backend/gateway instances with `AI_PILOT_ENABLED=true`,
   backend Easy Auth and allowlist, service token plus request-bound HMAC, separate
   signing/fingerprint keys, no development auth bypass. Use real Managed Identity
   Table access and an approved, durably initialized ledger. The current Table
   client uses Managed Identity, not local developer/key authentication; a laptop
   alone is not a documented real-run setup. Do not replace it with MemoryCAS.
3. Restrict benchmark ingress to the authorized backend and runner with no public
   end-user exposure. Variant B public ingress still needs its backend workload
   identity/role and early bounded-ingress gates; this package does not implement
   them. Preserve Table network restrictions and bound independent hosting costs.
   Do not override production guards, readiness or auth dependencies. A separate
   nonproduction process may invoke the normal request path while `/readyz` remains
   negative; if the host/runner requires positive readiness, that setup is blocked,
   not a reason to return true or disable its checks.
4. Approve the run manifest with one durable UUIDv7 operation per case, one pass,
   no replacement IDs after failures, no automatic retry/repair/warmup/LLM judge.
  Set the permanent `benchmark` limits above, person and global day/month
  request limits to at most 18, concurrency 1, and both model-budget ceilings
  to at most USD 4.2174. Stop at expiry; calendar rollover does not renew the run.
  Never restart with a fresh ledger/manifest. Minute limits may be lower and must
   respect the actual deployment quota. Never use two users' separate limits to
   double the global 18-attempt allowance. No automatic replenishment after cheap
   successes; counts cap attempts independently of reconciled cost.
5. Stop on identity/tier/price/usage-bound violations or unknown outcomes for review;
   do not release retained reservations to finish the matrix. Review the manifest's
   quality scores and schema/label/correction criteria manually, 17 estimation
   cases plus P5 separately. Report cold/warm elapsed time, input/cache/total output/
   reasoning, usage completeness, actual known cost and retained reserve separately;
   include failures in spend and cost per usable estimate. Unknown is never zero.
   No result or measured-quality claim is supplied by this offline package.

#### Minimal resource proposal for approval (2026-09-18)

Operational-budget update: the subsequently authorized local workflow uses a
EUR 10 aggregate stop threshold with accepted delayed-billing overrun risk, not
the historical separate financial allowances below. The technical USD 4.2174
model reserve and 18-attempt cap remain unchanged. Current approval reserves
tax/FX and EUR 2 for finite Table operations, retention and cleanup; see the
[current procedure](../infra/benchmark/README.md). Live results and resource
closure evidence belong in the external run report, never in application logs.
The proposal and original authorization status below are historical preparation.
The [completed screening review](benchmark-review-2026-09-18.md) records the
offline T5 dispatch proof, T2 arithmetic finding and unchanged cumulative limits.

**Implemented locally, not authorized for cloud execution:** this one-owner
screening CLI uses normal Microsoft Entra login, the existing use-case request
builder/Coordinator/adapter and real Azure Table transactions. See the
[exact setup, run, review and cleanup procedure](../infra/benchmark/README.md).
It needs no hosted backend, Functions, Container Apps, ACR, Foundry project,
Application Insights, Log Analytics or VM. It is not a deployed API/end-to-end
Easy Auth benchmark. Production, iOS, build numbers and readiness remain unchanged.
If the full authenticated HTTP chain must be measured, retain the service topology
above and approve its additional hosting separately; do not claim the CLI tests it.

Microsoft documents [developer-account AzureCliCredential authentication](https://learn.microsoft.com/en-us/azure/developer/python/sdk/authentication/local-development-dev-accounts),
[Entra bearer-token providers for the Azure OpenAI v1 endpoint](https://learn.microsoft.com/en-us/azure/ai-foundry/openai/how-to/switching-endpoints)
and [user/MI Table access with table-scoped RBAC](https://learn.microsoft.com/en-us/azure/storage/tables/authorize-access-azure-active-directory).
The new local runner uses an explicitly bound AzureCliCredential with a token
callback, without stored application credentials. The ordinary server settings
still require their existing credentials, and `AzureTableStore.connect` retains
ManagedIdentityCredential. The runner constructs its separate checked Entra client;
it does not override server dependencies or impersonate Easy Auth. Do not paste an
access token into the API-key setting, use connection strings/SAS, fake Easy Auth
headers, set auth bypass flags, or use MemoryCAS against a paid provider.

Proposed inventory (names are suggestions; availability and policy unchecked):

| Resource | Proposed configuration |
| --- | --- |
| Resource group | `rg-pft-mini-bench-<run_id>`, Sweden Central, isolated from all app/production resources; purpose/run/manifest/expiry tags |
| Azure OpenAI account | One `Microsoft.CognitiveServices/accounts`, kind `OpenAI`, S0, unique custom subdomain, local/key authentication disabled |
| Model deployment | One deployment `mini-bench`, `gpt-5.4-mini` version `2026-03-17`, `DataZoneStandard`, ordinary/default tier, no PTU reservation; pin version and disable automatic upgrade where supported |
| Deployment quota | Propose capacity 10 units, subject to current ARM model metadata, minimum/increment rules and subscription quota; record the actual TPM/RPM conversion. It is a throughput allocation, not a spend cap; do not silently increase or switch SKU/region/model |
| Ledger storage | One StorageV2 `Standard_LRS` account with a unique name, Sweden Central, one `MiniBenchmark` Azure Storage Table, TLS 1.2+, HTTPS only, Shared Key and public blob access disabled, Microsoft-managed encryption |
| Data permissions | The approved Entra operator gets `Cognitive Services OpenAI User` at this account, `Storage Table Data Contributor` at this table, and resource-group Reader for attestation; no new subscription-wide role. Provisioning permissions are separate. Review inherited privileges; an owner can override client-side controls |
| Network | Both data endpoints default-deny; allow only the operator's current single public IPv4 address, no trusted-service blanket bypass. No inbound laptop listener or public application API |

The network option needs **explicit approval as an isolated benchmark exception**
to any private-only requirement. [Storage IP rules](https://learn.microsoft.com/en-us/azure/storage/common/storage-network-security-ip-address-range)
and [Azure OpenAI network ACLs](https://learn.microsoft.com/en-us/azure/ai-services/cognitive-services-virtual-networks)
support this, but it is still a public service endpoint with restricted ingress,
not Private Link. Use an individual-address rule, not a `/32` range; stop on an
egress-IP change, never broaden the rule automatically. If private-only access is
mandatory, stop this proposal and separately cost a VNet, Table/OpenAI private
endpoints, DNS and a VPN/existing private route or temporary MI compute. Those
resources are not implicitly approved here.

Implemented: pinned dataset/asset verification, real-resource/price attestation,
checked Entra identity/token callbacks, atomic initialization of 18 immutable
case/UUIDv7 mappings, exclusive durable claims, lifetime Coordinator limits,
exclusive fsynced local results and structured human-review sidecars. A restarted
or competing runner cannot take over a `busy` case, and all earlier result hashes
must still be present. Unknowns and errors halt the run. No reset, replacement-ID,
automatic retry or tombstone cleanup is exposed by the runner. Normal server
authentication, production denial and negative readiness are unchanged.

Remaining live gates: owner topology/cost/privacy approval; completed immutable
approval JSON and real Entra login; actual ARM/quota/network/RBAC validation;
the separately enabled real Table suite (no model calls); one-time approved
ledger initialization; then separate authorization for the first paid manifest
case, including live model/tier/usage confirmation within the 18-attempt limit.
Offline tests do not establish live Azure availability or nutrition quality.

All existing admission rules still apply: one approved operator, global/person
limits at most 18, concurrency 1, output cap 2,000, lifetime reserve at most
USD 4.2174, no retries, repairs, replacement cases, warmups or LLM judge. Schedule
serially within the attested RPM/TPM; a 429 is not permission for a replacement
attempt. The first real manifest case is also the compatibility check and consumes
one of the 18 attempts. Approve an admission window of at most 24 hours and an
expiring deployment attestation; never extend it automatically. If compatibility
or cost metadata fails, stop without trying to finish all 18.

**Costs, separately approved:**

| Category | Planning amount and limit |
| --- | --- |
| One-time model reserve | USD **4.2174** = 18 x 0.2343 under the pinned rates/input/output bounds, not expected actual consumption or an Azure invoice spending limit. Actual valid usage is settled once; reasoning is part of output and images part of input |
| Table Standard LRS retail example | EUR 0.0386/GB-month and EUR 0.0003/10K for each read/write/batch-write/delete/list/scan meter. A deliberately generous 1 GB-month plus 10K of each operation category is **EUR 0.0404** |
| Account-encrypted LRS alternative meters | EUR 0.0502/GB-month; read 0.0056, write 0.0279, batch 0.0837, delete 0, list/scan 0.1005 each per 10K. The same generous example is **EUR 0.3684**. Confirm which encryption-meter SKU applies before approval; encryption at rest is required in either case |
| Other charges | Storage transactions for preflight/initialization/reconciliation, retained ledger capacity and outbound network transfer; no hosted compute, registry, VPN/private endpoint or log-ingestion resource in this option. Do not assume free bandwidth tiers or omit retained storage |
| Proposed ancillary envelope | **EUR 1** for this run and at least 31 days of tiny ledger retention after closure, subject to final SKU/network quote. This is an operator planning allowance, not an Azure hard stop; Cost Management alerts are delayed and not enforcement |

Storage figures were read from the public Azure Retail Prices API on 2026-09-18:
`currencyCode='EUR'`, region `swedencentral`, service `Storage`, product `Tables`,
Consumption, Standard LRS / Account Encrypted LRS (complete response, no next page).
Standard capacity meter `93e9cbca-b51e-5af9-bea0-269793096797`, read meter
`12da282f-7e96-49e2-983a-9a65da2a4866`, batch meter
`b9e5e77c-a0b3-4a2c-9b8b-57fa54f31c52`; effective 2021-06-08.
Revalidate at approval. Public retail examples are not the subscription's invoice
quote. USD model amounts and EUR infrastructure amounts must not be added without
the applicable billing exchange rate; tax, FX and contractual adjustments are
separate. No model quality/latency or measured cost claim is made.

**Cleanup:** close admission on completion, any stop condition or expiry; remove
inference permission and delete the model deployment/account after collecting
nonsecret attestation evidence. Retain the ledger, run identity, consumed attempt
totals and unknown reservations for reconciliation. Restrict the retained account
to the approved owner/reviewer; this local topology uses the same principal for
running and review. Do not blanket-delete the RG
while it contains unresolved operations. At the approved retention boundary,
reconcile or explicitly approve archival/destruction with a permanently closed
run record; if unknowns remain, extend retention/cost approval, not the attempt
budget. Only then remove the Table/storage, remaining RBAC/network rules and RG.
Destroy local temporary auth material through normal logout/credential handling;
never print it. Keep licensed public fixtures and nonsecret review documentation.

Approval must cover the local-only auth/topology exception, IP restriction, exact
resources/roles, final attestation, 18-attempt manifest and expiry, USD model and
EUR ancillary envelopes, and retention/cleanup. Local implementation and offline
validation are complete; cloud provisioning and the paid run require explicit
authorization. **No resources or paid calls were created by this preparation.**

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

### iOS operation lifecycle

`FoodAnalysisOperation` creates one UUIDv7 before authentication/first dispatch for
text, image and refinement actions, using a UTC millisecond timestamp and Swift's
system random generator for the remaining bits. `X-Operation-Id` carries its canonical
lowercase UUID. The operation holds immutable input, encoded body and content type in
memory. Explicit transport retries reuse the entire snapshot, including JPEG bytes
and the multipart boundary; images are not reprocessed for retries. The separate
local request token rejects late responses and is not the operation ID.
The server fingerprints normalized JSON (including the image base64), not multipart
framing. Different boundaries with identical image bytes and normalized fields are
therefore valid for the same operation; retaining the boundary is a stricter client
snapshot guarantee, not a server requirement. This was checked offline through the
real backend parser, gateway serialization and fingerprint function with mock transport.

`FoodAnalysisViewModel` and the existing stable `FoodAnalysisReviewSession` own these
operations. A changed submitted input or a new refinement round creates a new ID;
an identical retry keeps its ID even after token renewal. Each explicit attempt
acquires a token again. Entra supplies the actual selected account identifier together
with that token; a transient binding blocks an existing operation if interactive
sign-in switches accounts. This is only a client guard, not authorization: the server
still scopes operations to verified identity. Legacy token-only test/custom providers
cannot supply this account guard. No bearer token is retained in an operation.

No timeout, connection loss, HTTP 401, cancellation or foreground transition causes
an automatic retry. Unknown outcomes remain unknown even when a later retry fails
before dispatch (for example, at login). The UI separates resending the same request
from an explicitly confirmed **new calculation** that may consume provider resources
and incur provider costs again. There is no user purchase/billing system; the UI does
not claim a user was charged. A new calculation never promises to recover a lost
result. It does not replace an expired, rejected or
consumed ID automatically. The server owns age validation; its configured window is
not available to iOS, so the client does not invent a local expiry or refresh the UUID
timestamp. `operation_required` covers invalid/expired IDs and suggests checking the
device clock. Conflict and consumed responses disable identical retries; consumed
does not reveal whether the server is still running, finished or uncertain. All
public pilot codes use fixed, provider-neutral messages, never raw backend text.

Lifecycle boundaries are deliberately transient:

- Becoming inactive, moving to the **background**, or temporarily hiding a view does
  not cancel the operation or close the review: MSAL may use an external sign-in
  app/browser and must be allowed to return. The same in-memory task can finish after
  its token callback; foregrounding starts no additional request or retry. iOS may
  suspend/terminate the process, so background completion is not guaranteed.
- Explicit local cancellation cancels the task and invalidates its response token.
  This does not prove that no model call occurred. Input/snapshot remain available
  while their owner lives. A token callback after explicit cancellation cannot dispatch.
- Actually dismissing/cancelling the review sheet closes its session, cancels pending
  refinement and releases its snapshot;
  late responses cannot update the draft or save anything. The initial screen keeps
  the possible unknown outcome while its view model lives. A successfully received
  initial analysis is not resent by a second tap. A temporarily hidden review retains
  the same session, refinement count and persistence coordinator when shown again.
  A closed session is terminal, not reopened/reset; only a separate explicit new
  analysis creates a fresh review session.
- Process termination, app restart or destruction of the view model loses IDs,
  snapshots and unsaved review state. Startup never restores/sends unfinished work.
  There is **no cross-restart retry/idempotency guarantee** and no result retrieval.
  Re-entering content starts a new explicit operation and may incur additional cost;
  the app cannot recognize its relationship to a lost operation after restart.
  No new disk storage of meal content, images, operation IDs or fingerprints was
  introduced just to implement idempotency.

Only successful refinements consume one of the existing three rounds; each new
round has a fresh ID and sends the current visible estimate/correction, never the
image. The review session and its `FoodEntryPersistenceCoordinator` remain stable.
Only **Uebernehmen** persists, at most once; retries, cancellation and sheet dismissal
never save. Existing SwiftData and backup formats are unchanged.

The header remains compatible with the existing private API, but that path does
**not** enforce pilot idempotency. Its manual retry may execute again despite using
the same ID; the UI makes no free-retry guarantee and warns before resending. These
client changes do not activate the pilot, remove any production guard or demonstrate
live Azure billing/isolation. Offline package tests cover UUID format, byte-identical
retries/token renewal, account changes, double submission, new inputs/rounds,
uncertainty, cancellation, late responses and existing confirmation behavior.

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

Before any external release: validate the implemented transient iOS operation and
replacement-confirmation flow end to end, including its explicit restart limits;
claim-chain and Table integration evidence; privately funded
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
