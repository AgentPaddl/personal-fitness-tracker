# Architecture

## Purpose and current status

This repository contains a private, non-commercial personal fitness and nutrition tracker. The implemented product is an iOS app, an Azure Functions backend, and a Personal AI Gateway using the GitHub Copilot SDK. Phase 10 records a production deployment and real-device verification; this is historical deployment evidence, not a fresh runtime verification. The paid API decision below governs preparation for external users. See the [operations runbook](operations-runbook.md) for the existing deployment and its operational caveats.

## Current monorepo layout

| Path | Current responsibility | Status |
| --- | --- | --- |
| `ios/` | SwiftUI client and local SwiftData persistence | Working application, incl. text/photo/camera food analysis |
| `backend/` | Azure Functions Python 3.13 application API | Working `GET /api/health`, `GET /api/readiness`, `POST /api/food-analysis` (text + image) |
| `ai-gateway/` | Provider-independent server-side AI boundary | Working FastAPI app with `GitHubCopilotProvider`; deployment recorded in Phase 10 |
| `docs/` | Architecture and migration documentation | Active documentation |
| `.github/` | Repository-wide agent/Copilot guidance | Active guidance |

The iOS application owns the user experience and local records for workouts, exercise performance, activities, weight, goals, nutrition entries/presets, and backup-related flows. SwiftData is the local persistence layer. Existing behavior and stored user data are compatibility constraints.

The backend implements health, readiness, and text/image/refinement food analysis. Production authentication depends on Entra Easy Auth ahead of the Function and on application checks of injected identity headers. A Function's anonymous authorization level is not evidence that this platform boundary can be bypassed, nor is the presence of an identity header a sufficient per-user authorization policy.

## Previous provider decision (implemented baseline)

- **Production provider:** the official GitHub Copilot SDK.
- **Runtime:** the Copilot CLI running in headless/server mode, invoked internally by the gateway's Copilot adapter.
- `trsdn/github_copilot_openai_api_wrapper` is **not** part of the production architecture. It was an early exploration option only and must not be reintroduced without a new explicit decision recorded here.
- AI provider access remains behind the gateway's provider-neutral `StructuredGenerationProvider` abstraction, so the domain backend and iOS client never depend on Copilot-specific transport details.

## Paid API migration decision (2026-09-17)

Status: the original decision authorized preparation only. The separately
authorized first local adapter package is recorded below; contract acceptance,
resource creation, deployment, and paid model calls remain unauthorized.
This decision supersedes the previous Copilot target for the future external-user
path, not the description of the currently implemented adapter above.

- Keep the gateway and public application API during the provider replacement.
- Prefer EU processing; suitable international providers remain eligible. Assess
  quality, latency, cost, and privacy administration together, without claiming
  measured quality or latency before a benchmark.
- Block external AI use until independent funding, privacy foundations, verified
  identities, and enforceable usage limits are in place.
- Never route external users to Copilot, including old endpoints and rollback.
  Rollback must use a known API-only artifact or disable AI.
- Preserve local records and existing public request/response contracts. Targeted
  meal memory may disclose selected relevant meals, never a complete user record.

### First local package implemented (2026-09-17)

The local Azure v1 adapter now supports text, inline images and strict JSON output
behind `StructuredGenerationProvider`, with configurable deployment routes/output
caps, zero SDK retries, no repairs/fallback, and internal usage/elapsed-time/model
metadata plus versioned Decimal price estimates. Unknown usage or unmatched
prices remain unknown. Original JSON Schema and authoritative use-case validation
both apply; public schemas and iOS/persistence are unchanged. See
[local configuration and limits](../ai-gateway/README.md#local-azure-api-adapter-2026-09-17).

`AI_PROVIDER=azure_openai` is explicitly local-only and rejected in production.
The adapter also checks the process environment on every `generate()`: direct
or reused adapters cannot dispatch unless `APP_ENV` is explicitly `development`
or `test`. Production and missing/unknown environments fail closed independently
of readiness; HTTP and direct-call mock tests assert zero provider calls.
Its readiness remains false, without a provider call, until a later package can
verify deployed capabilities. Copilot code, dependencies and the existing
production artifact path are intentionally retained, with no fallback from the
new adapter. Distributed budgets/idempotency, input-token admission and durable
accounting are not implemented by this package. No paid benchmark was run.

Validation uses the actual pinned SDK against mock HTTP transport, including
text/JPEG/PNG/refinement, strict/original schema checks, failures, unknown usage,
pricing, no retries, confidential log markers and gateway/backend public mapping.
The existing Gateway and Backend regression suites are also required. No cloud,
contract, secret, device-data, deployment, iOS or build-number change accompanies
this package.

### Subsequent local pilot controls (2026-09-17)

The local implementation now adds strict Easy Auth claim/allowlist checks in the
backend, request-bound backend assertions, and one gateway Coordinator backed
by Azure Table ETag transactions. The Coordinator reserves person/global counts,
concurrency and worst-case token cost together with an operation tombstone before
granting a single adapter dispatch. It retains reservations for unknown outcomes;
it does not store estimates or provide result replay. Operations use UUIDv7 with
a bounded acceptance window to make metadata deletion compatible with rejecting
old IDs. See the [pilot runbook](operations-runbook.md#protected-two-person-pilot-local-implementation)
for exact configuration, retention, trust assumptions and test limitations.

This supersedes earlier statements that distributed controls are unimplemented
only as a description of local code. No Table resource/ledger, deployed Easy Auth
claim chain, real identities or cost policy has been configured or approved.
The Azure production guard remains unchanged; the existing private Copilot path
is not reclassified as external-ready. Stable iOS operations, API-only packaging,
external privacy/funding approval and real integration tests remain release gates.

### Rechecked implementation baseline (before local package)

Repository: `personal-fitness-tracker`, branch `main`, HEAD
`7f1439f01e182f81598098751b6d24cf76083932`; clean before this documentation change.
Repository and component instructions were reread. Findings below are from source
inspection on 2026-09-17, not a new cloud inventory, deployment attestation, test
run, or provider benchmark. Older phase descriptions below are historical.

| Controlling source | Verified behavior and migration consequence |
| --- | --- |
| [Provider contract](../ai-gateway/app/providers/base.py) | Generic messages, purpose, schema, attachments, and timeout; result contains only `data`. No usage, output-token limit, or cost metadata yet. Preserve domain independence. |
| [Food analysis use case](../ai-gateway/app/use_cases/food_analysis.py) | Builds untrusted text/image/refinement input, calls the provider once explicitly under `asyncio.wait_for`, then authoritatively validates `FoodAnalysisEstimate`. Refinement has no photo reinspection. No saved-meal context is implemented. |
| [Gateway schema](../ai-gateway/app/schemas/food_analysis.py) and [public schema/mapping](../backend/schemas.py) | Bounded estimates, strict image decoding/content checks, JPEG/PNG and 3 MiB limit. Public requests reject extra fields; response mapping reconstructs only `estimate`. Defaulted lists and numeric/string bounds are not automatically a provider-compatible strict schema. |
| [Copilot adapter](../ai-gateway/app/providers/github_copilot.py) | Long-lived client, new session per request, only the terminal structured-result tool exposed, explicit model routing. No application retries or usage accounting; session disconnect is not separately time-bounded. Internal SDK/CLI dispatch count was not audited. |
| [Settings](../ai-gateway/app/config.py), [factory](../ai-gateway/app/dependencies.py), [requirements](../ai-gateway/requirements.txt), [Dockerfile](../ai-gateway/Dockerfile) | Only `fake`/`copilot`; fake prohibited in production. Copilot credentials and SDK 1.0.11 remain in the production path; the image downloads the CLI runtime. A provider flag alone does not remove the dependency. |
| [Backend security](../backend/security.py), [gateway security](../ai-gateway/app/security.py) | Backend checks Easy Auth enabled plus nonempty principal ID, not a verified user allowlist. Gateway validates a shared service token, not end-user identity. Trust requires platform validation and removal of caller-supplied identity headers. |
| [Concurrency limiter](../ai-gateway/app/concurrency.py) | Process-local counter and lock only; not a cross-worker daily/monthly limit, budget, or idempotency store. |
| [Backend handler](../backend/api/food_analysis.py) and [gateway client](../backend/gateway_client.py) | One explicit synchronous HTTP POST per request, service token and correlation ID, normalized errors, client closed in `finally`. No identity/operation reservation forwarded. Transport timeouts are not a propagated wall-clock deadline. |
| [iOS service](../ios/FoodAnalysisKit/Sources/FoodAnalysisKit/FoodAnalysisService.swift) and [review session](../ios/FoodAnalysisKit/Sources/FoodAnalysisKit/FoodAnalysisReviewSession.swift) | Public endpoint and estimate contract remain provider-neutral. The 110-second client timeout and local per-attempt UUID are not server idempotency or proof of end-to-end cancellation. |

The existing timeout hierarchy recommends 90 seconds at the provider, 100 at the
backend, and 110 on iOS. These are not all default field values and do not account
for every preparation, cold-start, transport, and cleanup phase. Existing body
size checks also do not prove that the hosting worker never buffers an oversized
HTTP body. Both risks need boundary-specific checks before external use.

### Provider selection

**Local API-only migration package from `63c81e2`:** the separate
[pilot infrastructure and activation plan](../infra/pilot/README.md) now contains
the API-only image, exact managed-workload authorization, signed/expiring release
gate, separate ARM resources/budgets and opt-in iOS configuration. It is not
deployed or activated. Existing production and its legacy artifact are unchanged.
No compatible API-only rollback has yet passed live acceptance; rollback is AI
off with manual entry preserved. Later implementation notes below describe the
previous state where these items were still unimplemented.

**Current pilot decision from `19ee4c4`: GPT-5.4-mini is the selected candidate.**
The completed [screening review](benchmark-review-2026-09-18.md) distinguishes
T2 arithmetic failure, P3 partial coverage, T6 refusal, passed examples and
unassessed risks; it establishes neither general photo accuracy nor injection
safety. The following dated candidate/benchmark proposals are historical.
The EUR 10 benchmark authorization does not fund an ongoing pilot.

Local preparation adds a single-call internal initial-text extraction contract
and Decimal scaling/summing, conditional on model-extracted gram quantities and
declared nutrients. It does not introduce a free-text parser or certify source
association/completeness. Images, refinements and public DTOs remain unchanged;
real extraction with the new contract remains a live acceptance blocker.
Refused/filtered responses stay errors through gateway, backend and iOS. A
reproduced stale-review path on failed replacement is closed, and the save entry
point guards the session before constructing a local entry. SwiftData is unchanged.

Stable iOS operation snapshots and distributed limits already exist locally and
are reused, not rebuilt. API-only packaging, strict backend workload authorization
for public-HTTPS variant B, a durable installed-app URL, private recurring funding,
privacy prerequisites and deployed/device acceptance remain outstanding. Production
denial/negative readiness stays in place. The [minimum pilot plan and cost proposal](operations-runbook.md#two-person-pilot-preparation-from-19ee4c4)
is local preparation only, with API-only rollback or AI off, never Copilot access.

**2026-09-18 update:** the verified private subscription reports zero
GPT-4.1-mini DataZone quota in all four checked EU regions. The next candidate is
Azure `gpt-5.4-mini`, version `2026-03-17`, EU `DataZoneStandard`, for the target
variant B gateway (public HTTPS with strict backend-only authorization). See the
[model review, costs and implementation gates](operations-runbook.md#gpt-54-mini-candidate-review-2026-09-18).
This supersedes the next-candidate recommendation below, not the implemented
model binding or production guard. No deployment or funded benchmark is approved;
the historical multi-provider benchmark budget below does not apply to this model.

**Local implementation (2026-09-18):** the explicit
`gpt-5.4-mini-2026-03-17-dz-v1` profile now binds Sweden Central DataZoneStandard,
the reviewed price version, `reasoning_effort=none`, image `detail=high`, ordinary
service tier and a maximum of 2,000 total completion tokens. The existing adapter,
Coordinator and public contracts are retained. Operations persist their effective
model/deployment/price/cap binding; SDK responses with a different model/tier are
rejected, and raw-JSON usage avoids coerced token counts. The model-input maximum
of 272,000 yields USD 0.2343 reserve, without claiming a tighter image bound.
The [18-case offline manifest](../ai-gateway/tests/fixtures/gpt54-mini-benchmark.v1.json)
and existing test suites exercise the path with mocks only. Six licensed public
photo derivatives and two synthetic labels are now frozen with hashes and
[provenance/uncertainty notes](../ai-gateway/tests/fixtures/gpt54-mini-assets/README.md).
Three source photos do not constitute six independent meals or weighed nutrition
ground truth. An Entra-only local runner, durable case mapping, restricted result
artifacts, ARM attestation, opt-in real Table tests and isolated ARM lifecycle
scripts are now implemented and offline-tested. Actual cloud authorization/ledger
validation and any paid run still require separate approval. The runner is not a
production provider activation or deployed HTTP-auth test; changing `APP_ENV` alone
cannot satisfy its resource/identity/dataset checks. See the [execution procedure](../infra/benchmark/README.md)
and [isolated benchmark gates](operations-runbook.md#gpt-54-mini-local-profile-implementation-2026-09-18)
and [minimal resource proposal](operations-runbook.md#minimal-resource-proposal-for-approval-2026-09-18).
Production denial, negative readiness, privacy/funding gates and variant B
backend-only authorization prerequisites are unchanged. No paid run is approved.

**Initial integration candidate (2026-09-17): Azure OpenAI, `gpt-4.1-mini` version
`2025-04-14`, EU `DataZoneStandard`.** This matches the EU-processing preference,
the existing Azure operating environment, and the current small text/image/JSON
workload. It does not require assuming approval for OpenAI's separate European
image-residency offering. Keep the gateway; consolidating it into Functions is
not part of this migration.

This is a provisional integration choice, not a measured quality/latency winner
or permission to use the existing subscription's funding. Its main disadvantage
is lifecycle: the model is already **Legacy**, with retirement on **2027-04-14**.
Legacy currently permits new deployments until deprecation; actual subscription
access, EU capacity, quota, and price must still be checked. Reassess by
2026-12-15 and complete a replacement benchmark well before retirement. No
automatic model, region, Global deployment, or provider substitution is allowed.

**Closest comparison and reasoned alternative: direct OpenAI
`gpt-4.1-mini-2025-04-14`.** It offers the same model family with less deployment
administration and slightly lower published token rates. It is suitable if the
owner accepts a documented international processing/transfer arrangement, or
obtains the required regional approvals. The two services' quality and latency
must still be measured separately. Paid Gemini `gemini-2.5-flash` is the third,
independent-model comparison; no Vertex AI or free-tier equivalence is assumed.

Published standard on-demand prices, USD per million tokens, checked 2026-09-17;
not account-specific quotes, tax-inclusive prices, Batch, or Priority rates:

| Service and pinned candidate | Input / cached input / output | Capabilities and availability | Operational tradeoff |
| --- | --- | --- | --- |
| Direct OpenAI `gpt-4.1-mini-2025-04-14` | 0.40 / 0.10 / 1.60 | Text and image input; text output; structured outputs. Listed model, no retirement entry found in the checked deprecation list. Account access/tier unverified. | Small adapter and no Azure model deployment, but separate account/billing/privacy administration. European photo processing has approval prerequisites. |
| Azure OpenAI `gpt-4.1-mini`, `2025-04-14`, EU DataZoneStandard | 0.44 / 0.11 / 1.76 | Text/image and structured outputs; GA v1 API supported. Legacy; retirement 2027-04-14. Region, subscription quota and deployability remain gates. | Explicit EU inference zone, existing Azure operations; resource/deployment setup and earlier model replacement work. |
| Gemini API Paid Services `gemini-2.5-flash` | 0.30 / 0.03 / 2.50 | Stable model, text/image input and structured text output. No shutdown date announced on checked schedule. Paid project/tier/quota unverified. | Lower input but higher output price; thinking is billable. No Developer API EU-processing setting established; service-specific subprocessor mapping unresolved. |

Prices alone do not establish the cheapest provider: image tokenization, prompt
length, output/thinking, refusals, and successful-result rate matter. Explicit
Gemini caching also has storage charges; do not enable it for this pilot. Do not
budget cache discounts, free tiers, trial credits, or negotiated rates.

### Standard contracts and privacy assessment

Standard DPAs exist for all three candidates, but the intended independently paid
account, contracting entity, terms incorporation, and acceptance evidence are
**not verified**. No terms were accepted during this preparation. A published
DPA is not the legal basis for processing health-related data and is not a
guarantee of compliance. Assess controller responsibilities, Article 6 and, where
applicable, Article 9 GDPR, notices/consent, deletion, and whether a DPIA is needed.
Do not assume a household exemption or equate GDPR health data with US HIPAA PHI.
Keep the service an ordinary nutrition estimate, not diagnosis or medical advice.

| Question | Direct OpenAI API | Azure OpenAI | Gemini API Paid Services |
| --- | --- | --- | --- |
| Standard DPA and actual service scope | Services Agreement effective 2026-01-01 explicitly covers APIs for business/developer customers and incorporates the DPA in section 5.3. DPA effective 2026-01-01; EEA/Swiss customers contract with OpenAI Ireland Ltd. Confirm the private developer account falls under this agreement, not merely consumer ChatGPT terms. | Foundry privacy documentation explicitly places Azure OpenAI / models sold by Azure under Microsoft DPA. Licensing portal lists May 2026 DPA. Full current contractual attachment and incorporation for the intended subscription remain to be obtained and reviewed. Not direct OpenAI's DPA. | Paid API terms effective 2026-03-23 incorporate Google Data Processing Terms, version 10 dated 2026-05-07. Google's service list explicitly names Gemini API Paid Services for personal data in submitted prompts/responses. Cloud Billing does not make it Vertex AI. |
| Training and secondary processing | API content is not used to train/improve models unless explicitly opted in. Leave sharing off. Account, billing, support, and system data have separate processing purposes. | Prompts/results are not provided to OpenAI and are not used to train base models or improve products without permission/instruction. Microsoft operates the service. | Paid prompts, images and responses are not used to improve Google products. Account/auth/billing/usage/operational data are subject to separate controller terms/privacy rules. EEA/UK/Swiss API clients must use paid services. |
| Default retention and review | Abuse logs normally up to 30 days, with legal/safety exceptions. `store=false` does not disable abuse logging or all caching. ZDR/MAM require approval; flagged images can still be retained for manual safety review. | Automated abuse review does not store reviewed prompts/results in that system. Flagged samples can undergo Microsoft human review in a separate resource-scoped store. Exact human-review retention duration was not established from the checked pages; obtain it before personal-data use. Modified monitoring is approval-based, not assumed. | Usage policy specifies 55-day abuse retention for prompts, context and output, with possible authorized human review. Paid/no-training is not zero retention. Confirm image/context treatment, deletion limitations and legal exceptions for the actual service. |
| EU processing and limits | `eu.api.openai.com` supports eligible regional storage/inference in **EEA + Switzerland**, not strictly EU. Non-US residency requires abuse-monitoring approval and a Modified Retention amendment; images require enhanced ZDR/MAM approval. Endpoint/model/organization eligibility remains unverified. System data, including structured-output schemas, are excluded from residency. | Select an EU resource and EU DataZoneStandard, not GlobalStandard. Inference can occur throughout the EU zone, not just Germany. Geography/zone controls do not establish EU-only account/support/telemetry/subprocessor processing. Avoid optional stateful features and review service exceptions. | Paid terms allow processing where Google/agents operate worldwide. No EU pinning for this Developer API was verified. A GCP region or a Vertex AI promise cannot be substituted for this service. |
| Subprocessors and transfers | Official list identifies API subprocessors including Cloudflare, Microsoft, CoreWeave, Oracle, Google and AWS across countries. DPA provides SCCs or Article 45 adequacy routes; select the mechanism for actual recipients. Regional TLS termination uses Cloudflare Regional Services. List changes/objections are covered by the DPA; archive the applicable list and subscribe later. No recipient-specific DPF assessment completed. | Microsoft's published EU model-clauses guidance includes Azure and SCCs through the DPA. The current service-specific subprocessor list/version was not obtained in this review; obtain it through the official contractual/Trust Center channel. EU DataZone does not remove that transfer assessment. | DPA Appendix 3A provides DPF for covered certified US entities and SCC fallback, depending on entities/roles. The DPA-linked subprocessor page, dated 2025-12-12, lists Workspace/RCS but no Gemini mapping. This is an unresolved service-chain question, not evidence of no subprocessors; do not borrow a Workspace/Vertex list. |

For the first adapter, use foreground stateless Chat Completions with static,
content-free JSON schema, inline image input, `store=false`, and no tools,
grounding, Files, Threads, background jobs, or persisted conversation objects.
For a later Gemini comparison use stateless `generateContent`, not Interactions,
with inline images and no Files, explicit cache resources, or Search/Maps tools.
These choices reduce optional state; they do not override provider retention.

Before any personal-data dispatch, retain an owner-reviewed record of the exact
service/account, DPA version and incorporation, subprocessors/countries,
applicable transfer mechanism and supplementary measures, content and metadata
retention/deletion, support access, settings, and any required approval. Resolve
service restrictions for this nutrition use case, including Gemini's age and
medical-use restrictions. Do not request negotiated terms as a prerequisite if
the documented standard terms suffice, but do not invent coverage where unclear.

### Implementation package plan

Package 1 has the local implementation recorded above; the following remains
the decision's package specification, not a claim that later packages are done.
Each later package needs separate implementation authorization. Keep public
`POST /api/food-analysis`, JSON/multipart bodies, estimate fields, and normalized
error envelopes stable. Internal gateway contracts may gain execution metadata;
provider names, model IDs, tokens, prices, and raw errors must not reach iOS.

**1. Azure adapter, strict schema, and internal usage, offline first.**

- Add a domain-neutral adapter under `ai-gateway/app/providers/` (proposed new
  `openai_api.py`) using an explicitly pinned official async OpenAI client and
  the Azure v1 endpoint/deployment. Extend the existing provider base request
  with a server-chosen output cap and the result with optional execution
  metadata. Wire settings and factory in the existing configuration modules;
  no endpoint/model defaults or silent fallback. Add direct API mode only when
  its comparison is authorized; do not build three adapter frameworks upfront.
- Translate a copy of the use case's JSON schema into the supported provider
  subset: all properties required, `additionalProperties=false` recursively,
  references handled, defaults and unsupported bounds removed only from the
  transport schema. Missing warnings/assumptions are not silently accepted from
  a strict provider result. Preserve all authoritative Pydantic business bounds
  and public defaults; reject refusal, truncation, non-object, extra/missing
  properties, and invalid nutrition values. No repair generation or coercive
  JSON extraction from prose.
- Set `max_completion_tokens=2000`, one completion, and `max_retries=0` explicitly.
  The OpenAI SDK otherwise retries selected errors twice. Keep an outer deadline
  and bounded client cleanup; no synchronous network work in the async adapter.
  Later Gemini uses `maxOutputTokens=2000`, one candidate and `thinkingBudget=0`;
  its output cap includes thinking, and truncation is failure, not cheap success.
- Internal metadata: provider/deployment, requested and returned model version,
  provider request/response ID, correlation ID, duration, completion status,
  input/cache/output/thinking counts when supplied, usage-known flag, and a
  versioned USD price estimate. Record usage before business validation rejects
  a paid result. Carry sanitized metadata on failure too; missing usage is
  unknown, never zero. Retain pessimistic reservations when uncertain.
- Normalize OpenAI/Azure cache counts as a subset of prompt tokens and reasoning
  as a subset of completion tokens. Gemini prompt counts include cached tokens;
  account for candidate and thought tokens without double counting total usage.
  Keep modality breakdown only when reported; do not fabricate an image-token
  split. Reconcile estimates against billing, not vice versa.
- Touch [base contract](../ai-gateway/app/providers/base.py),
  [config](../ai-gateway/app/config.py), [factory](../ai-gateway/app/dependencies.py),
  [use case](../ai-gateway/app/use_cases/food_analysis.py),
  [errors](../ai-gateway/app/errors.py), [requirements](../ai-gateway/requirements.txt)
  and adapter-focused tests. Reuse existing `test_config.py`,
  `test_dependencies.py`, `test_model_routing.py`, `test_use_case.py`, and
  `test_production_hardening.py`; add one mock adapter test module when needed.
  Mock text/image/refinement, exact request schema/caps, refusal/truncation,
  timeout, usage-on-invalid-output, no retries, and client close. No paid tests.

Acceptance: unchanged public fixture responses and normalized errors, one mocked
dispatch at most, schema bounds still enforced, and no content in logs. This
package alone is not deployable for external use; the external gate stays shut.

**2. API-only production packaging and rollback artifact.**

Remove Copilot from production factory/config, requirements and container runtime
download; remove or retire the adapter and Copilot-specific tests as a coherent
change, including opt-in live tests. Retain fake only for development/tests.
Update [gateway documentation](../ai-gateway/README.md) and the
[operations runbook](operations-runbook.md) in that implementation package.
An `AI_ENABLED=false` path must return a normalized unavailable response without
building a provider; liveness remains available, readiness must not claim AI is
ready. No key, quota exhaustion, invalid config, or provider failure may activate
Copilot or fake in production. Inspect the built artifact/dependencies and run
mock process/health/security checks. Prepare a known API-only rollback artifact
before any paid rollout, not a rollback to the current Copilot image.

**3. Verified identity and one distributed admission authority.**

- Extend [backend security](../backend/security.py) and
  [configuration](../backend/config.py) to derive a trusted immutable identity
  from validated Easy Auth claims and an explicit tenant/object-ID allowlist.
  Check tenant/issuer, API audience, allowed client application and delegated
  scope at the responsible platform/application boundary. An allowed app is
  not an allowed person; email/display name and user-supplied headers are not
  identity proof. Validate direct/bypass paths and guest identities deliberately.
- [Backend handler](../backend/api/food_analysis.py) and
  [gateway client](../backend/gateway_client.py) forward a minimal authenticated
  internal identity, operation ID and deadline, never the user's bearer token
  or profile. [Gateway security](../ai-gateway/app/security.py) and
  [routes](../ai-gateway/app/api/routes.py) reject missing/untrusted execution
  context. Evaluate ingress restrictions; an undisclosed URL is not protection.
- Place the single authoritative reserve/dispatch/reconcile controller in the
  gateway immediately before generation. Proposed shared persistence: Azure
  Table Storage, one pilot partition holding global/person counters and operation
  records, with atomic transactions/ETags. Backend must not independently debit
  the same call. A new store/resource or use of existing storage needs approval
  and least-privilege managed-identity access; none is created by this plan.
- Atomically reserve worst-case cost, request count and concurrency before any
  dispatch. Count initial analysis, correction, retry attempts and unknown paid
  outcomes. Enforce short-window, UTC daily/monthly, per-person and global limits;
  count reservations against money caps. Store failure, stale policy, pricing
  uncertainty or exhausted budget means no dispatch. Keep the process limiter
  only as secondary local protection. Provider budget alerts are not hard caps.
- Suggested owner-approval starting values: 2 attempts/minute, 10/day and
  100/month per person; globally 6/minute, 20/day, 150/month; concurrency 1/person
  and 2/global; USD 5/month model spend ceiling. Also require server-side input,
  output, image-dimension/byte and total-request caps. These are proposals, not
  enabled limits or an infrastructure-cost ceiling.

Test fake-store atomic conflicts, two workers/processes, two people, restart,
period rollover, concurrency release, stale leases, missing usage and unavailable
storage. Existing backend/gateway security and production-hardening tests are the
home for HTTP admission tests; add focused store tests when implemented. A real
storage integration check is a later approved gate, not part of this doc change.

**4. Logical operations, errors and end-to-end deadlines.**

- Use a stable client operation UUID across retries of the same logical action;
  a corrected/new request gets a new ID. Scope it to verified identity and bind
  it to a canonical payload HMAC including image digest, refinement and any
  future selected-meal context. Do not hash multipart boundary bytes. Keep HMACs
  in the protected ledger, not logs; they remain pseudonymous sensitive data.
- Persist reserved/dispatched/succeeded/failed/unknown states before advancing.
  Only the transaction winner may dispatch; duplicate keys with changed payload
  fail, and duplicates in progress/unknown never redispatch. After possible
  dispatch, lease expiry or client cancellation does not prove no charge.
  Conservatively lose a result/reservation rather than silently repeat a call.
  There is no exactly-once guarantee across the database/provider network hop.
- Initially store metadata, not meal results. A successful duplicate whose
  response was lost therefore cannot replay an estimate; return a normalized
  non-success and require explicit confirmation of a new, separately budgeted
  operation. Define supported retry and retention windows before implementation
  (proposal: retry at most 24 hours, ledger/tombstones 30 days); never promise
  indefinite deduplication after records are deleted. Encrypted short-lived
  result caching would be a separate retention decision, not implicit scope.
- The current public body has no operation field. Preserve it; agree an additive
  idempotency header and coordinated iOS transport update. This is a new admission
  requirement, not transparent compatibility for old clients. Keep external use
  closed until supported clients send it; legacy requests must fail in the
  existing error envelope, never enter an unmetered bypass. Do not disguise the
  operation ID as the existing correlation ID or local stale-response token.
- Reuse [iOS service](../ios/FoodAnalysisKit/Sources/FoodAnalysisKit/FoodAnalysisService.swift),
  [view model](../ios/FoodAnalysisKit/Sources/FoodAnalysisKit/FoodAnalysisViewModel.swift),
  [review session](../ios/FoodAnalysisKit/Sources/FoodAnalysisKit/FoodAnalysisReviewSession.swift)
  and their existing service/retry/review tests. Preserve review-before-save and
  [persistence coordinator](../ios/FoodAnalysisKit/Sources/FoodAnalysisKit/FoodEntryPersistenceCoordinator.swift)
  behavior. No SwiftData/bundle-ID/backup migration, reinstall or restore is
  required. Sign-in must not be represented as account-partitioning local data;
  do not add cross-user memory access on a shared local store.
- Propagate a server-owned remaining deadline through backend, gateway and
  provider, using monotonic elapsed time within each process. Include admission,
  serialization, network and cleanup margins under the existing client timeout;
  no queue or retries. The client timeout starts after token acquisition in the
  current service, so measure the full UI action separately. Cancellation aborts
  local work best-effort, not necessarily provider computation or billing.
- Extend existing error mapping without raw SDK details: provider 429 and local
  quota denial become bounded rate-limit responses, disabled/unavailable service
  stays 503, deadline 504, invalid/refused/truncated output a normalized failure.
  Preserve existing envelopes and distinguish retry eligibility in the client;
  never automatically retry ambiguous paid outcomes. Test the complete mocked
  backend/gateway path and ledger state after each failure phase.

**5. Controlled rollout, then only selected-meal memory.**

After owner/privacy/funding approval, run the synthetic benchmark below through
the same admission controls with a dedicated operator identity and budget. This
does not admit other users. Before external onboarding, verify effective claims,
allowlist, store atomicity, quotas, logs, deployed model/version/zone and artifact
identity. Close old endpoints/revision URLs and service-token paths, stop Copilot
revisions and remove their credential references/credentials under an approved
change. Confirm no old backend can still reach Copilot. Rollback permits only an
approved API-only artifact that retains the controls, or AI disabled; never simply
reactivate a historical revision. No cloud commands are authorized here.

Meal memory is a later feature, not an extra field silently added by the adapter:
select at most three relevant, user-confirmed meals locally, with explicit user
control/preview and a bounded field/token allowlist. Send only necessary meal
names, portions, confirmed values and relevant corrections as untrusted reference
context, not as truth about the current plate. No whole diary, workout/weight
history, health goals, identity, historical photos, or cross-user records. Bound
this context within the same input/cost limit; allow omission/deletion and keep
current instructions/corrections authoritative. The strict current public schema
has no such field: agree an additive/versioned contract before implementation,
not a diary dump inside `food_description`. No cloud diary or embedding store is
a prerequisite for provider replacement.

### Synthetic benchmark specification

Preparation only: no private descriptions/photos/records, paid generations,
LLM judges, generated fixture purchases, or provider uploads were performed.
Create fixtures locally during an authorized implementation package: fabricated
German text, staged food without people/background identifiers, and locally
rendered labels. Use documented recipe weights and fixed nutrition references;
invented images alone do not establish true nutrition. Keep fixture provenance,
prompt/schema version, model settings, and reference tolerances in the existing
test structure rather than adding a parallel benchmark application.

| Cases | Count | Fixed input and expected behavior |
| --- | --- | --- |
| T1-T2 | 2 | Weighed single food and simple mixed recipe; declared portions and offline reference arithmetic preserved. |
| T3-T4 | 2 | Missing portion and contradictory/ambiguous description; explicit assumptions/uncertainty, no invented exact serving. |
| T5-T6 | 2 | German units/decimal comma and instruction-like text embedded in food input; correct interpretation, schema/instruction boundary preserved. |
| P1-P2 | 2 | Staged single food and weighed mixed plate; plausible reference range, no precision beyond visible evidence. |
| P3-P4 | 2 | Poor light/occlusion and no portion scale; warnings and lower confidence, no unsupported certainty. |
| P5-P6 | 2 | Non-food control and image containing instruction-like label text; no fabricated confident meal or obedience to image instructions. |
| R1-R2 | 2 | Fixed baseline estimate plus portion/ingredient correction; update only justified values, current correction wins. |
| R3-R4 | 2 | Image-origin estimate corrected without image, and contradictory/repeated correction at iteration 3; never claim reinspection or compound a correction twice. |
| L1-L2 | 2 | Locally rendered per-100-g and per-portion labels with known consumed weights; correct unit/portion arithmetic, identify ambiguity. |

18 cases x 3 repeats x 3 providers = **162 maximum billable attempts**, 54 per
provider. Refinement uses fixed baseline fixtures, not additional setup calls.
Failures/refusals count; no retries, repairs, extra warmups or replacement cases.
Randomize/interleave provider order. Record cold/warm state without paid warmup,
queue/admission/provider/total duration, schema validity, warnings, refusal,
truncation, usage completeness and price version. p50/p95 are descriptive at
this sample size, not production latency guarantees. Synthetic/staged coverage
does not establish performance on every real user's food.

Keep future meal-memory tests **offline/mock-only and outside these 162 calls**:
relevant selected meal, irrelevant candidate omitted, current correction
overriding memory, excessive context rejected, another user's record excluded,
and instruction-like saved text treated as data. Real memory-quality evaluation
needs its own approved contract, case extension and recomputed budget.

Proposed acceptance and ranking, agreed before any run:

- Hard gates: privacy/service coverage and funding approved for the run; zero
  content leakage, unauthorized dispatch, duplicate dispatch in supported retry
  windows, automatic retries or provider/model fallback. Any failure blocks
  release, regardless of average score.
- At least 95% usable, schema-valid estimates across the 51 food-estimation
  attempts per provider; refusals/timeouts/truncation on these tasks count as
  failures. The three P5 non-food attempts are separate controls: require a
  correct abstention or explicit no-food result without fabricated nutrition,
  not a successful meal estimate. Include their spend in total costs but not
  their responses in the usable-estimate denominator. All three repeats of both
  label cases must preserve units and be within 5% of reference calories and
  within the larger of 1 g or 5% for each macro. Portion corrections within 5%
  of reference arithmetic. No false photo reinspection. Human reviewers check
  these explicitly; all estimates accepted by the application must validate.
- For weighed recipe/photo cases, preregister plausible ranges (initial target
  calories within 25%, macros within the larger of 5 g or 30%). Uncertain cases
  are graded for honest assumptions, not made-up ground truth. Score portion
  handling, nutrition plausibility, correction adherence and uncertainty from
  0 to 4: 0 unusable, 1 major unsupported claims, 2 partial with material errors,
  3 meets the preregistered case criteria, 4 also communicates all relevant
  limitations clearly. Exclude inapplicable dimensions before the run; require
  mean at least 3/4 and no critical failure.
- Usability target: end-to-end p95 at most 30 seconds warm, and no attempt beyond
  the enforced server deadline. Report cold-start results separately; don't
  discard their failures. Revise a failed target explicitly, not after silently
  removing slow results.
- Among candidates passing all gates, weight quality 50%, latency 20%, cost 15%,
  privacy administration 15%. Normalize quality from the rubric; latency against
  the agreed 30-second target; cost by spend per usable result (zero usable
  results disqualifies). Score privacy administration 0-4 from documented service
  coverage, outstanding approvals, transfer/retention work and renewal burden.
  Record the human rationale, not a legal-compliance score. If close, prefer the
  EU-processing candidate; do not buy a cheaper failure rate.

**Enforceable cost assumptions:** at most 10,000 billable input tokens per call,
including all instructions, schema, text and image charges; at most 2,000 output
tokens including any thinking; one candidate; no tools, paid cache storage,
Batch, retries or separate setup generations. Prove each fixture's input upper
bound before dispatch using provider-specific token/image accounting and fixed
dimensions. A 3 MiB image limit is not a token limit. Unknown tokenization or a
required paid counting call blocks the run until the calculation is revised.

| Provider | Per-call maximum under these caps (USD) | 54-attempt maximum (USD) |
| --- | --- | --- |
| Direct OpenAI | 0.00720 | 0.38880 |
| Azure EU DataZone | 0.00792 | 0.42768 |
| Gemini Paid, thinking disabled | 0.00800 | 0.43200 |
| Total for the fixed matrix | | **1.24848** |

Calculation: `attempts * (input_tokens * input_rate + output_tokens * output_rate)
/ 1,000,000`, without cache discounts. Applying the highest input rate (0.44)
and highest output rate (2.50) to all 162 attempts gives **USD 1.52280**, rounded
up to **USD 1.53** as the conservative cross-provider model-cost bound. Propose a
separately authorized **USD 5 benchmark budget**, with atomic worst-case reserve
before every call and at most 162 attempts; that budget does not authorize extra
calls. Abort on price/model change or usage exceeding the asserted caps.

These are conditional model-service bounds, not a universal billing guarantee.
They exclude Azure hosting/storage/telemetry, tax, currency conversion and any
new metered service. Approve an independent infrastructure budget and account
payment method; inspect billing reconciliation after the run. Unknown outcomes
keep their maximum reservation rather than making room for replacement calls.

### Owner decisions and release gates

The owner must select the privately controlled paid account/subscription and
contracting party, confirm funding independent of Copilot/employer benefits,
approve the benchmark and monthly model budgets plus infrastructure budget, and
name the initial allowed identities. No account creation, login, billing change,
contract acceptance, resource provisioning or deployment is part of this record.

Before external use, all of the following must be evidenced, not just configured
in a draft: applicable standard terms/DPA and legal basis; recipient/transfer and
retention review; approved region/service/model and lifecycle follow-up; securely
stored credentials/least privilege; verified identities and allowlist; shared
fail-closed limits and reservations; supported-client idempotency; bounded
payloads/deadlines with retries disabled; content-free logging and retention;
benchmark acceptance; API-only/AI-disabled rollback with old Copilot paths closed.
Usage metadata is not automatically anonymous: restrict access and define
retention for pseudonymous identifiers and operation records. Ordinary logs must
not contain prompts, images, meal values, raw SDK errors, HMACs or bearer tokens.

Open points at this decision date: no funded target account or quota verified;
no contracts accepted; Microsoft DPA attachment/service-specific subprocessors
and human-review retention still need review; OpenAI target-account/residency
eligibility unverified; Gemini service-specific subprocessor chain unresolved;
no measured quality/latency; no distributed store or client operation protocol
implemented. The additive header/admission policy needs explicit agreement.
The new adapter rejects production selection, but does not install distributed
controls or close the old Copilot paths. External AI use remains unauthorized.

### Official source register

Accessed 2026-09-17. These are public provider statements, not proof of the
target account's agreement, approval, quota or deployed settings. Recheck before
funding/deployment and on lifecycle or contractual changes.

- OpenAI: [model and price](https://developers.openai.com/api/docs/models/gpt-4.1-mini),
  [deprecations](https://developers.openai.com/api/docs/deprecations),
  [Services Agreement](https://openai.com/policies/services-agreement/),
  [DPA](https://openai.com/policies/data-processing-addendum/),
  [subprocessors](https://openai.com/policies/sub-processor-list/),
  [data controls and residency](https://developers.openai.com/api/docs/guides/your-data),
  [Chat Completions caps/usage](https://developers.openai.com/api/reference/resources/chat/subresources/completions/methods/create),
  [SDK retry defaults](https://github.com/openai/openai-python#retries).
- Azure: [standard prices](https://azure.microsoft.com/en-us/pricing/details/azure-openai/),
  [retirement schedule](https://learn.microsoft.com/en-us/azure/foundry/openai/concepts/model-retirement-schedule),
  [lifecycle definitions](https://learn.microsoft.com/en-us/azure/foundry/openai/concepts/model-retirements),
  [structured outputs and Azure schema subset](https://learn.microsoft.com/en-us/azure/foundry/openai/how-to/structured-outputs),
  [service privacy/DPA scope](https://learn.microsoft.com/en-us/azure/foundry/responsible-ai/openai/data-privacy),
  [abuse monitoring](https://learn.microsoft.com/en-us/azure/foundry/openai/concepts/abuse-monitoring),
  [Microsoft DPA versions](https://www.microsoft.com/licensing/docs/view/Microsoft-Products-and-Services-Data-Protection-Addendum-DPA),
  [SCC scope](https://learn.microsoft.com/en-us/compliance/regulatory/offering-eu-model-clauses).
- Google: [model](https://ai.google.dev/gemini-api/docs/models/gemini-2.5-flash),
  [paid prices](https://ai.google.dev/gemini-api/docs/pricing?hl=en),
  [deprecations](https://ai.google.dev/gemini-api/docs/deprecations?hl=en),
  [paid service terms](https://ai.google.dev/gemini-api/terms),
  [processor terms and transfer appendix](https://business.safety.google/processorterms/),
  [DPA service list](https://business.safety.google/services/),
  [DPA-linked subprocessor information](https://business.safety.google/subprocessors/),
  [55-day abuse policy](https://ai.google.dev/gemini-api/docs/usage-policies),
  [thinking/output limits](https://ai.google.dev/gemini-api/docs/generate-content/thinking?hl=en),
  [GenerateContent schema/usage reference](https://ai.google.dev/api/generate-content?hl=en).

## Implemented V2 architecture (before paid API migration)

```text
iOS client
    |
    | authenticated, versioned fitness/nutrition contracts
    v
Fitness API / domain backend
    |
    | authenticated, provider-neutral AI requests
    v
Personal AI Gateway
    |
    | StructuredGenerationProvider (provider-neutral adapter interface)
    +--> GitHubCopilotProvider (real; official GitHub Copilot SDK)
    |       Copilot CLI in headless/server mode
    +--> FakeProvider (deterministic, used for local development and tests)
    +--> Future provider adapter(s)
```

### iOS client

- Owns SwiftUI presentation, user interaction, and local SwiftData persistence.
- Calls only our authenticated Fitness API; it never calls model providers or the Copilot wrapper directly.
- Contains no GitHub/Copilot credentials, provider tokens, provider base URLs, or provider-specific model routing.
- Presents AI-produced values as estimates and supports review/confirmation before persistence where appropriate.
- Evolves persisted models without destructive migration or loss of existing personal data.

### Fitness API / domain backend

- Owns fitness/nutrition domain rules, application authorization, and application-facing API contracts.
- Validates requests and decides when an approved workflow needs AI assistance.
- Translates use cases into provider-neutral gateway requests; provider transport does not enter domain logic.
- Returns stable, versioned response and error contracts to the iOS client.
- Does not expose sensitive personal endpoints anonymously.

### Personal AI Gateway — Phase 2 foundation implemented

- Provides our authenticated, server-side AI API to the domain backend (FastAPI app under `ai-gateway/`).
- Owns AI schema validation, provider/model routing, timeouts, limits, and normalized errors.
- Uses replaceable provider adapters behind the `StructuredGenerationProvider` interface. `FakeProvider` serves local development/tests; `GitHubCopilotProvider` is the implemented production baseline recorded in Phase 10. The paid API decision above replaces that future target, not the running implementation through documentation alone.
- Keeps provider-specific transport details behind the adapter boundary; the public gateway API never exposes provider or model identifiers.
- Is not a public proxy. Any future Copilot CLI process must never be exposed directly to the public internet and should be reachable only through controlled server-side networking.

### Provider adapters

- Convert gateway contracts to and from provider-specific formats.
- Contain provider authentication and transport behavior, not fitness/nutrition domain rules.
- Allow provider replacement without changing the iOS contract or core domain logic.
- Treat malformed or schema-invalid provider output as an explicit failure, not trusted application data.

## AI contracts and use cases

Prefer explicit, versioned JSON schemas. Structured contracts should distinguish model estimates from user-confirmed facts and include enough metadata for validation and review without leaking provider internals.

Planned use cases are:

1. Analyze food text into structured nutrition estimates.
2. Analyze food images plus optional context into structured nutrition estimates.
3. Add activity and training assistance.
4. Support other personal AI services through separate application-level contracts.

Text/image analysis and text-only refinement are implemented. Activity/training and other AI services remain roadmap items. Persistence of AI output is an explicit domain action after user review or confirmation.

## Security and privacy assumptions

- Fitness, nutrition, images, prompts, and derived responses are sensitive personal data.
- Provider and wrapper credentials exist only in server-side environment variables or a managed secret store. They never ship in the iOS app, source control, logs, or client-visible responses.
- `.env`, `local.settings.json`, `.venv`, Xcode user data, caches, and build artifacts remain untracked.
- Authentication and authorization are required before exposing personal-data or AI endpoints beyond a trusted local environment.
- Apply least-privilege networking: client traffic terminates at our API, gateway access is limited to authorized backend callers, and the wrapper is internal-only.
- Minimize data sent to providers and define consent, retention, deletion, and export behavior before sending real personal data. Avoid raw sensitive-payload logging by default.
- Apply request size/rate limits, timeouts, output schema validation, and safe error handling at server boundaries.
- AI output is an estimate and is not authoritative health or medical advice.

## Historical phased roadmap

The following entries record decisions and verification at each phase, including
then-current deployment/configuration gaps. They are not a fresh status report
or authorization to reuse Copilot for external users. The dated paid API decision
above takes precedence for that migration and its rollback policy.

### Phase 0 — baseline (current)

- Preserve the working SwiftUI/SwiftData app and Azure Functions health endpoint.
- Establish repository, security, agent, and architecture guidance.
- Keep the AI gateway as documentation/configuration scaffolding only.

### Phase 1 — contracts and security design

- Define authentication/authorization and trust boundaries.
- Define versioned domain and gateway JSON schemas, including estimate/confirmation semantics.
- Decide privacy, consent, retention, deletion, observability, and deployment controls.
- Add contract tests before provider integration.

### Phase 2 — provider-neutral gateway foundation (implemented, reviewed, and hardened)

- Implemented the gateway core (FastAPI), configuration, request/response schemas with numeric bounds, normalized errors, and a domain-blind `StructuredGenerationProvider` adapter interface. Concrete providers only ever see generic generation messages, an opaque `model_purpose` routing key, a JSON output schema, optional attachments, and a timeout — never domain task names like "food_analysis_text". All food-specific orchestration (instructions, schema, interpretation) lives in `FoodAnalysisUseCase`.
- Implemented the deterministic, schema-driven `FakeProvider` (derives values purely from the requested JSON schema, with no food-specific knowledge) and the first `FoodAnalysisUseCase`; tests use the fake provider and do not require real credentials.
- Server-side model routing: `FOOD_TEXT_MODEL_PURPOSE` selects a routing key independently of the public contract; changing it never changes the request/response shape and it is never exposed to clients.
- Modularized the Azure Functions backend into blueprints, added an internal `GatewayClient` with distinct timeout/connectivity/upstream-error handling, and a food-analysis backend route that works locally against the gateway's `FakeProvider` path.
- The backend owns its own public request/response contract (`backend/schemas.py`) and explicitly maps the gateway's internal response onto it; unknown fields (provider, model, usage, debug/execution metadata) can never reach the client because only declared fields are ever read and re-serialized.
- Authentication fails closed by default everywhere: the gateway's dev auth bypass requires both `APP_ENV=development` and `GATEWAY_DEV_AUTH_BYPASS=true`; the backend's food-analysis route requires `APP_ENV=development`. Neither is enabled by default. `GET /health` (backend) and `GET /healthz` (gateway) remain anonymous and configuration-independent.
- `AI_PROVIDER=fake` is rejected outright when `APP_ENV=production`, so the fake provider can never silently become a production default; today this means the gateway has no valid production configuration until a real provider adapter exists, which is intentional.
- A final catch-all exception boundary (gateway `app/main.py`, use case `_generate_with_timeout`) normalizes any unexpected/provider exception so raw internals never reach a client.
- Readiness (`GET /readyz`) delegates to a provider's own cheap `check_ready()` check, letting a future real adapter report connectivity without performing a billed generation call.

### Phase 3 — Copilot SDK adapter (implemented for local use)

- Implemented `GitHubCopilotProvider`, wrapping the official GitHub Copilot SDK for Python (`github-copilot-sdk`), which drives the Copilot CLI in headless/server mode. It remains domain-blind: it understands only generic messages, an opaque `model_purpose` routing key, a JSON output schema, and a timeout.
- Structured output uses a terminal tool (`submit_structured_result`, `Tool(is_terminal=True)`) whose parameter schema is supplied by the calling use case; the provider never hard-codes a domain schema, and the use case still authoritatively re-validates whatever the tool call returns.
- Server-side model routing (`COPILOT_MODEL_ROUTES_JSON`) maps each model-routing purpose to a concrete Copilot model id with no default and no silent substitution; `GET /readyz` validates the configured model is actually available via the SDK's `list_models()`/`get_auth_status()` without a billed generation call.
- Local-development authentication uses the Copilot CLI's own documented mechanisms (locally logged-in session via `copilot`/`/login`, or an optional explicit token) — never a hard-coded credential. The production authentication mechanism for a deployed gateway is intentionally not decided yet.
- One long-lived `CopilotClient` (and its underlying CLI process) is reused across requests; only a lightweight SDK session is created and disconnected per request.
- Normalizes provider authentication failure, rate limiting, model unavailability, timeouts, invalid structured output, and unexpected SDK/runtime failures to the gateway's existing error model; a catch-all boundary ensures no raw SDK exception, prompt, or GitHub-specific metadata reaches the public API.
- Unit tests mock the SDK client boundary and require no credentials; an opt-in integration/smoke test (`RUN_COPILOT_INTEGRATION_TESTS=1`) exercises the real CLI and is never run in normal CI/local test runs. `trsdn/github_copilot_openai_api_wrapper` is not part of this plan.
- Remaining for production: Azure Container Apps packaging, a chosen production auth mechanism (server-to-server token vs. another documented option), secret storage, and network isolation for the CLI process.

### Phase 4 — food analysis workflow (text and image analysis; both merged to `main`)

- Implemented the iOS text food-analysis flow: `NutritionView` lets the user type a natural-language description, calls the backend's `POST /api/food-analysis` via a local Swift package (`ios/FoodAnalysisKit`), and presents an editable review sheet (`FoodAnalysisReviewView`) before any persistence.
- The app only ever talks to our own backend's public JSON contract; it has no knowledge of the Personal AI Gateway, GitHub Copilot, model ids, or provider routing.
- `FoodEntry` (existing SwiftData model) is created only after explicit user confirmation of the reviewed values; cancelling/dismissing the review never persists anything. No SwiftData schema change was made.
- **Image analysis (merged):** extends the same flow with photo input, reusing the identical review/persistence UI and the same structured estimate contract.
  - iOS: `PhotosPicker` or camera capture (`UIImagePickerController` bridge) selection, client-side preprocessing (`FoodImagePreprocessor`: EXIF-orientation-corrected resize to a max 1280px side via ImageIO's thumbnail API, deterministic quality/dimension fallback to fit a 3 MiB limit, re-encoded as JPEG, which also strips EXIF/GPS since the source's properties are never copied to the re-encoded output), then upload via `FoodAnalysisService.analyzeImage`.
  - Backend: `POST /api/food-analysis` now also accepts `multipart/form-data` (`image` file field, required; optional `food_description` text field), validated for MIME type (`image/jpeg`, `image/png` only), non-empty payload, and a 3 MiB size cap (chosen to fit the configured vision model's advertised max prompt image size), then forwarded to the gateway as an inline base64 payload over the existing internal JSON contract.
  - Gateway: `FoodAnalysisRequest` now accepts `food_description`, `image`, or both (at least one required); `FoodAnalysisUseCase` builds a generic `Attachment` and routes image requests to a separate, vision-specific model purpose (`FOOD_IMAGE_MODEL_PURPOSE`, default `food_image_v1`) rather than the text purpose, so an image call is never silently sent to a non-vision model.
  - `GitHubCopilotProvider` translates the generic attachment into the SDK's inline `BlobAttachment` (base64, no temporary files) and rejects unsupported attachment kinds/empty payloads before ever creating a session. `check_ready()` additionally verifies, via the SDK's own `list_models()` capability data, that any route required for image analysis actually supports vision (`gpt-5-mini` verified vision-capable via a real Copilot session on 2026-08-29).
  - The output schema, bounds, and review/persistence flow are unchanged from text analysis; no new SwiftData model or migration was introduced.
- Verify privacy controls, failure handling, and observability without sensitive-payload logging.

### Phase 5 — expansion and provider portability (future, not started)

- Add activity/training assistance and other personal AI services as separate domain contracts.
- Add or switch providers through adapters and server-side routing without iOS provider changes.
- Revisit schemas, privacy controls, and data migrations incrementally with each use case.

### Phase 6 — production hardening (`feature/v2-production-hardening`, not yet merged; no real Azure deployment performed)

Adds no new AI capability; hardens the existing text/image food-analysis system for reliable ongoing personal use.

- **Authentication**: the accepted production design is Microsoft Entra ID via MSAL on the iOS native client, then Azure App Service Authentication / Easy Auth on the public backend. The backend does not accept a static shared secret from the app; it only trusts Azure-injected Easy Auth identity headers when `EASY_AUTH_ENABLED=true` and `APP_ENV != development`. A separate server-to-server secret still remains for backend -> gateway (`GATEWAY_SERVICE_TOKEN`, `X-Service-Token`), because the gateway is never a public client-facing API. No GitHub/Copilot credential ever exists in the iOS app or is committed to git.
- **iOS auth**: a real production app must acquire a short-lived Entra access token via MSAL or a supported equivalent, send it as `Authorization: Bearer <token>`, and rely on the backend's App Service Authentication to validate it before the app reaches backend business logic. Phase 6 originally kept a placeholder `EntraAuthService` with no secret material and no app-side static API key; Phase 7 (`feature/v2-entra-msal-integration`) replaced it with a real MSAL-backed implementation - see that phase's entry below for the current architecture.
- **Gateway deployment**: a `Dockerfile` (Python 3.13, Copilot CLI runtime pre-fetched at build time, `COPILOT_GITHUB_TOKEN`-based auth since the interactive `/login` flow has no headless equivalent) targets Azure Container Apps but has not been built/deployed here (no Docker available in the authoring environment) - see `ai-gateway/README.md`'s deployment section for the full runtime/memory/networking requirements.
- **Networking**: production `AI_GATEWAY_BASE_URL` must be an explicit, non-`localhost`, `https://` URL (`backend/config.py` fails closed otherwise). Intended topology: `iPhone native client -> Microsoft Entra ID via MSAL -> Azure Functions with App Service Authentication / Easy Auth -> private/restricted gateway -> Copilot CLI runtime (never exposed)`. Only the backend is a public endpoint.
- **Timeout hierarchy**: gateway `AI_PROVIDER_TIMEOUT_SECONDS` (90s recommended) < backend `AI_GATEWAY_TIMEOUT_SECONDS` (100s) < iOS `FoodAnalysisService.timeoutInterval` (110s, raised from 30s) - see `backend/AGENTS.md`'s table.
- **Retry UX**: no automatic/silent retries of an AI request. An explicit "Erneut versuchen" button appears only for retry-eligible failures (connectivity, backend-unavailable, rate-limited, timeout); input/configuration failures are not offered a retry action, since retrying the identical request would just fail the same way.
- **Long-running UX**: the existing spinner is preserved; after 5s it switches to a neutral "Das Essen wird analysiert …" with no fake percentage progress.
- **Observability**: a request-correlation ID (`X-Request-Id`) is minted by the backend (or reused if the caller already sent one), forwarded to the gateway, echoed in response headers, and included in every error envelope's `request_id` field. Structured, content-free logging (path/use-case/status/latency/error-category) at both layers - never the food description, image bytes, raw model response, or credentials.
- **Readiness**: `GET /api/readiness` (new, distinct from `GET /api/health`) checks the gateway is actually reachable; `GET /healthz`/`GET /readyz` (gateway) semantics are unchanged (health = process alive, readiness = real Copilot auth/vision-capable model routing verified without a billed call).
- **Concurrency**: `AI_PROVIDER_MAX_CONCURRENCY` (default 2) is a fail-fast in-memory limiter (`app/concurrency.py`), never an unbounded queue - a request beyond the limit gets an immediate `503 service_saturated`.
- **Preserved unchanged**: the 3 MiB image limit, JPEG/PNG content validation (full decode + decompression-bomb handling), client-side metadata stripping, `food_text_v1`/`food_image_v1` routing, provider domain-neutrality, `submit_structured_result`-only tool exposure, the exactly-once persistence flow, and all existing SwiftData models/schemas (no changes).

#### Personal production checklist

- [x] Gateway container built and deployed (Azure Container Apps)
- [x] Backend (Azure Functions) deployed
- [x] Azure App Service Authentication / Easy Auth enabled on the public backend, with Entra ID trust configured and `EASY_AUTH_ENABLED=true`
- [x] `GATEWAY_SERVICE_TOKEN` configured identically on both backend and gateway
- [x] Production `AI_GATEWAY_BASE_URL` (explicit HTTPS, non-localhost) configured on the backend
- [ ] Gateway ingress restricted to the backend only (currently external HTTPS + service token; IP allow-list/private networking intentionally deferred — see `docs/operations-runbook.md` §6)
- [x] `COPILOT_GITHUB_TOKEN` (a fine-grained GitHub personal access token for unattended SDK use, not a server-to-server installation token — see `docs/operations-runbook.md` §2) configured as a gateway secret
- [x] `COPILOT_MODEL_ROUTES_JSON` configured for both `food_text_v1` and `food_image_v1`, verified vision-capable via `GET /readyz`
- [x] Gateway `GET /healthz` and `GET /readyz` both return healthy/ready (explicitly HTTP-smoke-tested, `200` on both)
- [ ] Backend `GET /api/health` and `GET /api/readiness` explicitly authenticated-smoke-tested (not yet done individually; what's proven instead: all three backend routes are deployed, and a real production `POST /api/food-analysis` call succeeded end-to-end, which implies the Easy Auth boundary and backend→gateway connectivity both work)
- [ ] iOS **durable** production build configuration (the real-device smoke test used the Xcode Scheme's `API_BASE_URL` environment variable, which does not survive archiving/TestFlight — see Phase 8's note; a compiled-in production backend URL mechanism is still pending) with a real Entra ID access-token provider (MSAL, already implemented) that sends `Authorization: Bearer <token>`
- [x] Real iPhone smoke test against the deployed stack (text and image, save flow) completed

### Phase 7 — Entra ID / MSAL integration (`feature/v2-entra-msal-integration`, not yet merged; no real Azure/Entra deployment or registration performed)

Replaces the Phase 6 placeholder `EntraAuthService` with a real MSAL-backed implementation and prepares (but does not execute) the exact external Entra/Azure configuration the backend's Easy Auth boundary already assumes.

- **Dependency**: [MSAL for iOS/macOS](https://github.com/AzureAD/microsoft-authentication-library-for-objc) added via Swift Package Manager, pinned to an exact version (`XCRemoteSwiftPackageReference` requirement `exactVersion` `2.15.0`; also recorded in the committed `Package.resolved`, so both mechanisms agree unambiguously) for reproducible builds. Native/public-client flow only - no client secret ever exists in the iOS app.
- **Architecture**: a new local Swift package `ios/EntraAuthKit/` holds the MSAL-*independent* account-selection and silent-first/interactive-fallback orchestration (`EntraAuthService`, `EntraTokenAcquiring` protocol, `EntraAccountStoring`, `EntraTokenError`, `EntraConfiguration`) behind the same pattern as `ios/FoodAnalysisKit/` - testable via `swift test` with no MSAL dependency, no network, and no Microsoft/Azure endpoint ever contacted. The only file that imports MSAL is `ios/Trainingsplan/Entra/MSALEntraTokenAcquirer.swift` in the app target; `ios/Trainingsplan/EntraAuthService.swift` (`EntraAuthServiceFactory`) is the small app-target factory that wires the two together.
- **Account-selection policy** (single-user app, never picks an account arbitrarily): a previously-selected MSAL account identifier is remembered in `UserDefaults` (`EntraAccountStoring` - an opaque, non-secret identifier, never a token). Resolution deliberately goes through MSAL's `allAccounts()` rather than `accountForIdentifier` for both the remembered-identifier check and cached-account enumeration, since `accountForIdentifier` throws indistinguishably for "not found" and genuine cache/keychain failures in the integrated MSAL version - `allAccounts()` lets a real lookup error (throws) be told apart from a clean "not present" answer. The full `allAccounts()` result is evaluated before any account is discarded (`EntraCachedAccountNormalization`, unit-tested): an identifier-less cached account is never silently dropped (which could otherwise turn two accounts into what looks like one, or turn a single identifier-less account into what looks like none) - it fails closed with `EntraTokenError.unsupportedCachedAccountState` instead. With no remembered identifier and no identifier-less accounts, MSAL's cached-account count decides: zero accounts goes straight to interactive sign-in; exactly one is selected and remembered; more than one throws a normalized `multipleAccountsRequireSelection` error rather than choosing arbitrarily. If a previously-remembered identifier no longer resolves (e.g. removed via Settings), it is cleared and resolution falls through to the same decision, rather than either failing outright or blindly going interactive.
- **Account/cache lookup failures are errors, not login triggers**: a genuine MSAL cache/keychain query failure (as opposed to a truly empty cache) is normalized to `EntraTokenError.accountLookupFailed` and propagated as an authentication failure - it is never silently treated as "no account exists" and never triggers an interactive login on its own.
- **Token flow**: once an account is resolved (see above), acquisition is silent-first (MSAL's own keychain-backed cache, no manual token persistence by this app at all) - only if MSAL reports `interactionRequired` does the flow fall back to interactive sign-in. Interactive presentation is controlled entirely by MSAL and may use system web authentication or a configured broker app (e.g. Microsoft Authenticator/Company Portal, if installed) depending on device state and MSAL's own configuration - this is never hardcoded to a single specific presentation mechanism here. A user cancelling interactive sign-in surfaces as `FoodAnalysisError.authenticationRequired` (generic German message, no raw MSAL error ever shown).
- **Redirect URI**: MSAL's documented default iOS/macOS format, `msauth.<bundle-id>://auth` (here: `msauth.com.benedikt.Trainingsplan://auth`), registered in `Trainingsplan-Info.plist`'s `CFBundleURLTypes`/`CFBundleURLSchemes` and handled via `TrainingsplanApp`'s `.onOpenURL` (SwiftUI app lifecycle) forwarding to `MSALPublicClientApplication.handleMSALResponse`.
- **Fail-closed configuration**: `EntraConfiguration.load(bundle:)` requires all four non-secret values (`EntraTenantID`, `EntraClientID`, `EntraAPIScope`, `EntraRedirectURI`) to be present and non-blank. In `DEBUG` builds, missing configuration returns `nil` (no `Authorization` header - unchanged local-development behavior). In `Release` builds, missing or MSAL-rejected configuration returns `FailClosedAccessTokenProvider`, so every request throws `authenticationRequired` rather than silently sending an unauthenticated request.
- **Backend boundary unchanged**: `backend/security.py::caller_is_authenticated` already implements exactly the intended Easy Auth boundary (development bypass, otherwise trust `X-MS-CLIENT-PRINCIPAL-ID` only when `EASY_AUTH_ENABLED=true`) and already has a regression test proving a spoofed `X-MS-CLIENT-PRINCIPAL-ID` header is rejected when Easy Auth is disabled (`test_food_analysis_denied_with_spoofed_principal_header_when_easy_auth_disabled`). No backend/gateway contract change was needed or made for this phase.
- **Single-user restriction recommendation**: this is a private single-user app. Prefer Azure/Entra-side restriction over a custom iOS/backend allowlist:
  1. **App assignment (recommended)**: on the backend/API app registration's Enterprise Application, set "Assignment required?" = Yes and assign only the one intended Entra account. Azure AD then rejects sign-in/token issuance for any other account before it ever reaches this app - no application code involved.
  2. **Tenant restriction**: since this is a single-tenant work/school scenario (`https://login.microsoftonline.com/<tenantId>` authority, not `common`/`organizations`/`consumers`), only accounts in the owning tenant can sign in at all; this is already implied by using a tenant-specific authority rather than a multi-tenant one.
  3. **Backend-side claim check (optional, defense-in-depth only)**: if desired in addition to (1), the backend could compare the Easy-Auth-injected principal's object id (`X-MS-CLIENT-PRINCIPAL-ID`, not `-NAME`, since a UPN/email can change) against a single configurable `ALLOWED_USER_OBJECT_ID` environment variable (never hardcoded/committed) and reject any other value. Not implemented in this phase since (1) is the documented, App-Service-enforced mechanism and doesn't require trusting application code to do it correctly.
  - Multiple cached MSAL accounts on-device (e.g. a stale/second sign-in) require deterministic selection (see the account-selection policy above) rather than either an arbitrary choice or a custom allowlist; this is an iOS-local disambiguation concern, separate from and in addition to the Entra/Azure-side restrictions above.
  - No real tenant ID, client ID, UPN, email, or object ID is hardcoded or committed anywhere in this repository.

#### Entra/Azure external setup checklist (not executed - portal/CLI steps only)

**Backend/API app registration** (Microsoft Entra admin center → App registrations → New registration):
1. Register an app representing the backend API (e.g. "Fitness Tracker API").
2. Expose an API (App registration → "Expose an API"): set the Application ID URI (default suggested form `api://<backend-app-client-id>`), then add one delegated scope, e.g. `FoodAnalysis.Access` (admin and user consent description: access to the personal food-analysis API). The full scope string used by iOS/MSAL is `api://<backend-app-client-id>/FoodAnalysis.Access`.
3. Note the backend app's Application (client) ID and the tenant ID - both are public identifiers, safe to place in app/backend configuration later, never secrets.

**Native iOS app registration** (separate App registration):
1. Register a second app representing the iOS client (e.g. "Fitness Tracker iOS").
2. Authentication → platform: "iOS/macOS", enter the exact bundle ID (`com.benedikt.Trainingsplan`); Azure derives/confirms the redirect URI `msauth.com.benedikt.Trainingsplan://auth` for you - must match `Trainingsplan-Info.plist` exactly.
3. Ensure "Allow public client flows" is enabled and **no client secret is ever created** for this registration - a native/public client authenticates only via MSAL's interactive/silent flow, never a secret.
4. API permissions → add the backend API's delegated `FoodAnalysis.Access` scope (from the previous registration) and grant admin consent (single-user personal app, so this can be done once directly rather than per-user consent prompts, though per-user consent also works).
5. Fill in the app's real `EntraTenantID`, `EntraClientID` (the iOS app's own client ID, not the backend's), `EntraAPIScope` (`api://<backend-app-client-id>/FoodAnalysis.Access`), and `EntraRedirectURI` (`msauth.com.benedikt.Trainingsplan://auth`) into the shipped app's Info.plist/build configuration - never into source control as real values in a public repo; these are public identifiers, but still keep the actual values out of a shared/public git history per personal preference.

**Azure Functions Easy Auth** (Azure Portal → Function App → Authentication):
1. Add identity provider → Microsoft, select the backend API app registration from above (not a new one) as the identity provider so tokens issued for the API's scope are accepted.
2. Restrict access: "Require authentication" (reject unauthenticated requests before Functions code ever runs - this is what makes `X-MS-CLIENT-PRINCIPAL-ID` trustworthy at all).
3. Set the allowed token audience(s) to the backend API app's Application ID URI from step above.
4. Set `EASY_AUTH_ENABLED=true` on the Function App's own application settings only after the above is confirmed enforcing - this is the server-side-only flag `backend/security.py::is_easy_auth_enabled()` reads; it must never be set before Easy Auth is actually configured and enforcing.
5. **Verify spoofing is actually blocked** (do this against the real deployed Function App, not local `func start`, since Easy Auth is an Azure App Service platform feature with no local emulation): send a request directly to the deployed backend URL with a hand-crafted `X-MS-CLIENT-PRINCIPAL-ID` header and no real Azure-issued session/token. With "Require authentication" enforcing, Azure itself must reject this before the Function code runs (typically a redirect-to-login or 401, never a 200). If a request without a valid Azure-issued session ever reaches Function code with an attacker-supplied `X-MS-CLIENT-PRINCIPAL-ID` intact, Easy Auth is not actually enforcing and must not be relied upon - this application intentionally contains no code that tries to independently/cryptographically validate that header, since Azure's platform-level enforcement is the only trustworthy source for it.

### Manual end-to-end test plan (prepared, not yet executed)

`iPhone -> MSAL login -> Entra token -> Azure Functions Easy Auth -> backend -> gateway -> Copilot -> food estimate`, once the checklist above is complete and the gateway/backend are actually deployed:

1. **First interactive login**: fresh app install, no cached MSAL account. Trigger analysis; expect the Microsoft sign-in UI to appear, complete sign-in, expect a successful analysis.
2. **Second request, silent/cached auth**: immediately analyze again; expect no sign-in UI (silent token from MSAL's cache), successful analysis.
3. **Expired/refresh case**: force a token refresh scenario if feasible (e.g. wait out access token lifetime or revoke/reset session server-side) and confirm silent acquisition transparently refreshes without user-visible interaction; only if MSAL reports `interactionRequired` should sign-in UI reappear.
4. **Login cancellation**: trigger analysis, dismiss the Microsoft sign-in UI without completing it; expect the app returns to the food-analysis screen with the typed description/photo still present and a generic German error, not a crash or partial state.
5. **Anonymous request rejected**: call the deployed backend's `POST /api/food-analysis` directly (e.g. via `curl`) with no `Authorization` header at all; expect Azure Easy Auth to reject it before Function code runs.
6. **Invalid token rejected**: call the deployed backend with a malformed/expired/wrong-audience bearer token; expect rejection (via Easy Auth, not custom backend JWT validation).

### Phase 8 — configure real Entra values (`feature/v2-configure-real-entra-values`, not yet merged; no Azure deployment performed)

Configures the real (but still non-secret/public) Entra identifiers for the `Release` build configuration only, so a real-device build can exercise interactive/silent MSAL sign-in. Does not itself perform any Entra app registration, Easy Auth configuration, or Azure deployment - those remain the checklist above.

- **Mechanism**: `Trainingsplan-Info.plist` gained four keys (`EntraTenantID`, `EntraClientID`, `EntraAPIScope`, `EntraRedirectURI`) whose values are `$(ENTRA_TENANT_ID)`/`$(ENTRA_CLIENT_ID)`/`$(ENTRA_API_SCOPE)`/`$(ENTRA_REDIRECT_URI)` - Xcode's standard Info.plist build-setting variable substitution (the same mechanism used for e.g. `$(PRODUCT_NAME)` in a default Xcode-generated Info.plist), not the `INFOPLIST_KEY_*` auto-synthesis mechanism (confirmed by inspection that `INFOPLIST_KEY_*` only applies to Apple's own recognized Info.plist keys, not arbitrary custom ones - an incorrect first attempt at this that produced no entry at all in the built Info.plist). The four `ENTRA_*` build settings differ per configuration in `project.pbxproj`'s **target-level** `Debug`/`Release` blocks: blank in `Debug` (`EntraConfiguration.load(bundle:)`'s `nonBlankString` check treats a blank string as absent, so `DEBUG` builds keep resolving no configuration - unchanged local-development behavior, no `Authorization` header, no MSAL interaction) and set to the real values in `Release`.
- **Values configured** (all public identifiers, never secrets, no client secret added): tenant ID `3106a3eb-9742-46da-ab73-bfdaea9c3d52`, iOS client ID `ed51ac30-3a4c-4bf6-b0e7-151c7c7b3ed8`, backend delegated scope `api://8a31b030-58f4-4897-b76f-11fb33381d14/FoodAnalysis.Access`, redirect URI `msauth.com.benedikt.Trainingsplan://auth` (verified to still match `PRODUCT_BUNDLE_IDENTIFIER = com.benedikt.Trainingsplan` in both build configurations).
- **Backend URL for the real device test**: `APIConfiguration` deliberately has no compiled-in production default (see its fail-closed design above) - `API_BASE_URL` must still be set explicitly on the Xcode scheme for the immediate physical-iPhone smoke test below, to `https://fitness-tracker-api-bk-ckewh6fhd0gmfkcd.germanywestcentral-01.azurewebsites.net/api`. **Scope of this mechanism, precisely**: a scheme environment variable is only ever passed to the process by Xcode itself at the moment it launches a run it built and installed (Product > Run) - it is not written into the app bundle or the archive Xcode produces for distribution. It is therefore sufficient for a Release-configuration run launched directly from Xcode onto a physical device (the smoke test below), but it does **not** carry over to an Xcode Archive, and so is **not** sufficient for TestFlight, App Store, or any other normally-installed Release launch (ad-hoc/enterprise distribution, or an app opened by the user outside Xcode) - those all run with an empty environment as far as this variable is concerned, and `APIConfiguration.resolveBackendBaseURL()` would then fail closed with `.missingConfiguration` exactly as designed. Real production distribution still needs a durable, compiled-in Release backend URL configured through a mechanism that survives archiving - e.g. the same build-setting-to-Info.plist `$(VAR)` substitution used for the Entra values above (a new `API_BASE_URL`-equivalent Info.plist key read by `APIConfiguration`), or another equivalent compiled HTTPS configuration - which is not implemented in this phase and remains a prerequisite for any distribution beyond an Xcode-launched device run. None of this affects the Simulator's unset-`API_BASE_URL` localhost default, which is unrelated and unchanged.

#### Real iPhone smoke test - exact steps (prepared, NOT executed as part of this phase)

1. Build and run the `Trainingsplan` scheme in the `Release` configuration on a physical iPhone (not the Simulator), with `API_BASE_URL` set on the scheme to the real deployed Function App URL above.
2. In the app, trigger a food-analysis request (text and/or photo) via "KI-Analyse (Text & Foto)".
3. Confirm the MSAL interactive sign-in UI appears (system web/broker UI, controlled by MSAL - see Phase 7's note that this is never hardcoded to one specific presentation mechanism).
4. Sign in with the one Entra user assigned to this app (see the single-user app-assignment checklist item above).
5. Confirm (via Xcode console logging or backend logs, never by inspecting raw token contents in a shared context) that the token was requested for the `FoodAnalysis.Access` scope configured above.
6. Confirm the backend request succeeds end-to-end through Azure Easy Auth (a successful food estimate is returned, not a 401/redirect-to-login).
7. Trigger a second analysis in the same app session; confirm no sign-in UI reappears (silent/cached token acquisition via MSAL's own cache).
8. Trigger a third analysis and cancel the interactive sign-in UI if it reappears (e.g. after clearing the app's MSAL cache via device Settings, or on a fresh install); confirm the typed description/selected photo are still present afterward and a generic German error is shown, matching `FoodAnalysisError.authenticationRequired`'s existing behavior.

This test has not been executed as part of this phase; only the configuration and manual steps have been prepared.

### Phase 9 — real physical-iPhone Entra/MSAL smoke test (completed)

Diagnosed and fixed, via live device testing: a missing MSAL Keychain Sharing entitlement (`ios/Trainingsplan.entitlements`), a v1-vs-v2 Azure AD token/issuer mismatch, and an Azure Easy Auth `authsettingsV2` configuration drift (`openIdIssuer`, `allowedApplications`) — all confirmed fixed via direct `az rest` inspection and an independently verified minimal PATCH. Full MSAL sign-in, silent token reuse, and Easy Auth enforcement confirmed working on a real iPhone.

### Phase 10 — production deployment (completed)

Deployed the Personal AI Gateway to Azure Container Apps (`fitness-tracker-gateway`, environment `fitness-tracker-gateway-env`, external HTTPS ingress, `GATEWAY_SERVICE_TOKEN` + `COPILOT_GITHUB_TOKEN` as Container Apps secrets, image pulled from `fitnesstrackeracr` via the Container App's system-assigned managed identity, no ACR admin user) and redeployed the current backend code to `fitness-tracker-api-bk` with the required production App Settings. Verified end-to-end on a real iPhone, launched via Xcode with the backend URL supplied through the Scheme's `API_BASE_URL` environment variable (not yet a durable, archive-surviving configuration — see Phase 8's note on this same limitation and `docs/operations-runbook.md`): text analysis, silent MSAL token reuse, and image analysis all succeeded against the real GitHub Copilot SDK. See `docs/operations-runbook.md` for exact resource names and procedures.

### Phase 11 — cleanup and hardening (in progress)

Removed the unused legacy Azure OpenAI scaffold (App Settings and the `fitness-tracker-api-bk-openai-b0a0` resource — confirmed unreferenced by any current code). Fixed an orphaned Application Insights workspace link on the backend (`WorkspaceResourceId` was `null` despite `ingestionMode: LogAnalytics`), restoring telemetry visibility. Operational runbook documented in `docs/operations-runbook.md`.

## Change and validation policy

Changes should be small and reviewable, with explicit acceptance criteria. Build `ios/Trainingsplan.xcodeproj` after Swift changes, with DerivedData outside the repository. After backend changes, run relevant tests and verify the health endpoint. Any SwiftData schema change requires an explicit non-destructive migration plan that preserves existing user data.
