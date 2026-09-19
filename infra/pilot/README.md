# Private two-person pilot package

Prepared through `3d15cc4`; the separately authorized pilot is now **deployed with
AI disabled**, not accepted for ordinary use. See the current
[deployment and privacy record](DEPLOYMENT-2026-09-19.md). Historical local checks
and cost proposals below describe the pre-deployment package, not current approval.
The EUR 10 benchmark allowance does not fund this pilot. No benchmark resource,
ledger, operation, unknown hold, identity grant or cost headroom is reused.
The existing Dockerfile, Release URL, app identity and installed production are
unchanged. Manual entry, SwiftData and backup formats remain unchanged.

## Files and boundaries

- `ai-gateway/Dockerfile.api-only`: explicit source inventory, no Copilot SDK,
  CLI, fake adapter, benchmark tooling or PAT requirement. Its
  Dockerfile-specific ignore list excludes caches, local configuration and
  unrelated code from the build context without changing the legacy build.
  Python 3.13.15 / Alpine 3.24 is pinned by digest, using only stable repositories
  and binary Python wheels. Local Linux/amd64 build, inventory and Trivy scan
  completed (below). `pip` and its unused `ensurepip` bootstrap are removed after
  installation and `pip check`. Transitive dependencies
  are captured in the local SBOM, not all locked: archive the approved image by
  registry digest; a later rebuild needs a new scan and approval.
- `main.json`: resource-group ARM template adapted from the existing benchmark
  ARM conventions, not a deployment of that benchmark template. Dedicated
  `pft-pilot-*` group, Sweden Central, two user-assigned managed identities,
  Azure-managed networking without a customer VNet, identity-protected public
  service endpoints, Table-scoped gateway role, model-scoped inference role,
  secret-scoped read permissions, authenticated registry pull. No Contributor
  role for either workload. The backend has Blob Data Owner on its dedicated
  host-storage account, but no Table role. This is needed for Functions host
  containers/leases and deployment blobs; it grants no control-plane or model access.
- `budget.json`: subscription-scoped cost alert filtered to the pilot group.
  An optional infrastructure-group parameter can include an additional group if
  actual inventory later requires it. Variant B does not request that group or
  customer-VNet network resources. Only filter compatibility changed, not the
  budget amount, thresholds or authorization.
- `policy.proposed.json`: explicit proposal, intentionally invalid until the
  owner-approved pilot end date is supplied in `deployment_verified_until`.
  Missing, zero or invalid budgets fail closed. No price, policy, funding or
  privacy approval is automatically extended. Technical evidence can be renewed.
- `prepare.py`: offline backend ZIP packaging and conversion of actual public
  deployment outputs into iOS configuration and reviewable Graph request bodies.
  It never calls Azure or Graph and never overwrites an existing output file.

The Python provider abstraction/public DTOs and single Coordinator are retained.
One admitted operation has one SDK dispatch, `max_retries=0`, no fallback or repair,
2,000 completion tokens, and a USD 0.2343 full-input reserve under the current
reviewed price profile. Failed/unknown accounting is not free. Refusals do not
create a new saveable estimate. This does not establish extraction correctness.

## Local verification

Earlier baseline: the complete gateway/backend suites passed with external sockets blocked: **659
gateway tests, 179 backend tests, 14 live tests skipped**. The package adds signed
synthetic JWT, full JWT/HMAC ingress,
activation/expiry/configuration tampering, no-ledger-reset, one-dispatch SDK,
artifact inventory, ARM contract and iOS configuration regressions. Existing
FoodAnalysisKit (146) and EntraAuthKit (28) tests passed, as did the Debug app build
and unsigned Release builds for both Simulator and **generic/platform=iOS**, using
an external synthetic xcconfig. The device artifact is ARM64, unsigned, build 5.
This is a device-target build, not installed-device/MSAL/data acceptance. The
unconfigured pilot Release build failed at the intended build-time check. No
synthetic target URL was written into actual deployment configuration, installed
on a device or contacted. Pylance syntax/editor checks and diff whitespace checks
passed. Container inventory/import/fail-closed smoke passed with no network,
read-only filesystem, all capabilities dropped and no-new-privileges. No cloud
operation or model call was made; only public prices/docs/packages were downloaded.

Variant B follow-up, 2026-09-18: **195 targeted tests passed inside the reviewed
Linux/amd64 candidate**, covering JWT/HMAC rejection (including anonymous and missing
credentials), release controls, one-dispatch SDK behavior, budget/ledger limits
and native image validation. Test wheels were mounted read-only, not installed
in the runtime. **64 backend tests** passed for gateway identity, authorization,
configuration and health; **five local packaging/ARM contract tests** passed.
External connections were blocked. Unchanged iOS/build/full-suite checks above
were not repeated. A real Uvicorn start and local TLS trust/rejection plus both
sync/async ManagedIdentityCredential transports passed against synthetic loopback
servers in a network-isolated container; no real token or model was requested.

Pre-commit review corrected one obsolete evidence criterion: `table_rbac` now
requires `anonymous_access_denied`, not `external_network_denied`, because Variant
B permits public network reachability. Table-scoped RBAC, Shared-Key denial and
foreign-identity denial remain mandatory. Missing/false or old network evidence
is rejected. **28 targeted approval/renewal tests passed locally; 29 passed inside
the rebuilt image**, including disabled startup. Package layers were reused from
the reviewed build cache; the new scan confirms identical 29 OS/48 Python packages
and no reported vulnerabilities/secrets using the same local database. Unchanged
backend, iOS and ARM checks were not repeated. This correction grants no approval.

Both ARM envelopes and **24 resource declarations** pass exact API-version
schemas from Microsoft's public schema CDN/repository. The check exposed and
corrected the old literal fractional CPU value: `[json('0.25')]` preserves the
same 0.25 vCPU while satisfying ARM's expression schema. The specific
`authsettingsV2` schema branch passes; the generic `oneOf` is ambiguous with an
expression name. These are local schema checks, not ARM expression evaluation,
regional quota, effective RBAC or deployment validation. No authenticated Azure
operation, ARM-TTK installation or provider-side validation was performed.

### Runtime basis comparison

The previous runtime and exactly two maintained official Python 3.13 alternatives
were built/inspected/scanned with Trivy 0.74.0 on 2026-09-18. Alternatives used only
their stable distribution updates and the unchanged API requirements. All three
passed Python 3.13.15, CA-store, RSA/JWT, JPEG, SDK-import, UID 1000 and fail-closed
smoke checks. Candidate dependency installs used binary wheels only, not compilers.

| Runtime | OS packages | Critical / High / Medium / Low / Unknown package findings | Decision |
| --- | ---: | --- | --- |
| Existing pinned slim-trixie, including earlier security updates/SUID mitigation | 87 | 0 / 44 / 49 / 57 / 1; eight distinct High CVEs | Compatible Trixie fixes for the eight were unavailable; SUID removal mitigated only part of the exposure. |
| Official `python:3.13-slim-bookworm`, stable updates applied | 97 | 5 / 55 / 100 / 86 / 0 | Not selected: no concrete improvement over Trixie, additional flagged components, older LTS base. |
| Official `python:3.13-alpine3.24`, stable updates applied | 29 | 0 / 0 / 0 / 0 / 0 | Selected after the final-image tests above: removes vulnerable component paths and supplies stable fixes, not just a different scanner label. |

Base manifest digests:

- Existing Trixie: `sha256:9d2e5553305c7c7b0097999bb17187c69b921ccd6bc9d40e4bb5ebe652c00285`.
- Bookworm comparison: `sha256:ed86c82274b3c69b52fb5820f358f0bd7df0b603332063cb5c6e32bd220c3e6e`.
- **Selected Alpine**: `sha256:1a63a53928ce53d2b0baf08092a703f4840ac5dfbd61fd48802dbf48e08c801e`.

The [official Python image documentation](https://hub.docker.com/_/python) lists
all three maintained tags and warns about Alpine's musl/glibc differences.
[Bookworm LTS](https://www.debian.org/releases/bookworm/) runs to June 2028;
[Alpine 3.24 main](https://www.alpinelinux.org/releases/) is supported to June 2028,
while community support is shorter. Keep runtime dependencies in supported
repositories, rebuild/scan regularly and requalify after base or wheel changes.
`--only-binary=:all:` deliberately fails a future incompatible dependency build
instead of silently adding an ad hoc compiler toolchain. No sid/forky/edge
repository, distroless custom root filesystem or unsupported package deletion.

The final image retains the standard-library shared libraries, CA certificates,
timezone data and package metadata. `scanelf` is retained because `musl-utils`
depends on it; simulated package removal did not justify forcing deletion.
Unused pip/ensurepip are removed. Perl, systemd, libacl, libmount and GNU
mount/nsenter are no longer installed. BusyBox 1.37.0-r31 still supplies shell,
mount/umount/nsenter/tar/cp applets; these are not the vulnerable util-linux/GNU
implementations, and BusyBox itself is not claimed immune to future defects.
No SUID/SGID executable was found. The gateway runs as UID/GID 1000 with a nologin
account; no additional runtime privileges or host mounts are requested.

Final local image identifier:
`sha256:9f1fc72b16e75781cac527215f941dcc0d23527ad9642396473e726bc2777472`.
Trivy recognizes Alpine 3.24.2, scans **29 OS and 48 Python packages**, and reports
**no vulnerabilities or detected secrets** with `--ignorefile /dev/null` and
`--ignore-unfixed=false`. No finding/severity/package database was suppressed.
This is not proof that the image has no vulnerabilities or an authorization to
publish it. Trivy warns that 3.24 is missing from its EOL list and that third-party
SBOM data can be inaccurate: lifecycle was checked against Alpine's release page,
package inventory directly in the container, and util-linux fixes against the
[official stable security database](https://secdb.alpinelinux.org/v3.24/main.json).
Database completeness, source-built CPython/native wheel coverage and unknown
defects remain scanner limitations, not zero-risk claims.

Current evidence: `/tmp/pft-variant-b-commit-scan.json`,
`/tmp/pft-variant-b-commit-sbom.json`, `/tmp/pft-variant-b-config-scan.json`;
comparison scans `/tmp/pft-variant-b-{local,bookworm,alpine}-scan.json`.
The earlier `final-scan`/`final-sbom` files identify the pre-commit candidate,
before the evidence-criterion correction, not the final image identifier above.
The final Dockerfile scan has 26 passes and one LOW DS-0026 (no Docker HEALTHCHECK);
ACA's separate liveness probe remains in ARM and needs live acceptance. Earlier
Trixie scan reports remain historical, not the selected artifact.

### Eight prior High-CVE dispositions

The old Debian findings remain in their comparison report, not in the final image
scan. Trixie candidate availability was previously checked through Debian's stable
repositories and Security Tracker; none of these eight had a compatible candidate.
For the four util-linux findings, old group U was `bsdutils` 1:2.41.5-0+deb13u1;
`libblkid1`, `liblastlog2-2`, `libmount1`, `libsmartcols1`, `libuuid1`, `mount`,
`util-linux` 2.41.5-0+deb13u1; `login` 1:4.16.0-2+really2.41.5-0+deb13u1.
The final image contains only `libuuid` 2.42.3-r1 from that source family.

| CVE / source | Previous affected package/version | Attack prerequisites | Final measured disposition / fix status |
| --- | --- | --- | --- |
| [CVE-2026-76642](https://security-tracker.debian.org/tracker/CVE-2026-76642) | U, especially mount/libmount1 2.41.5-0+deb13u1 | Privileged mount, suitable user fstab entry, failed helper followed by privileged X-mount hooks | GNU mount/libmount absent; BusyBox mount is a different implementation, no SUID executable. Retained libuuid 2.42.3-r1 exceeds Alpine's 2.42.3-r0 fix. Upstream fix 2.41.6/2.42.3; no residual vulnerable component identified. |
| [CVE-2026-78408](https://security-tracker.debian.org/tracker/CVE-2026-78408) | U, util-linux 2.41.5-0+deb13u1 | Root/CAP_SYS_ADMIN nsenter --join-cgroup against an attacker-controlled target leaks privileged cgroup FD | util-linux nsenter absent; present BusyBox nsenter is not this implementation. Alpine explicitly fixes this CVE in 2.42.3-r1, matching retained libuuid. No privileged debugging permitted; no residual vulnerable component identified. |
| [CVE-2026-78409](https://security-tracker.debian.org/tracker/CVE-2026-78409) | U, mount/libmount1 2.41.5-0+deb13u1 | Linux >=6.15, privileged X-mount.subdir path, user fstab entry and attacker-controlled path components | GNU mount/libmount absent; retained libuuid exceeds stable fix 2.42.3-r0. Old Debian/upstream affected-version discrepancy remains a historical uncertainty, not a suppression rationale. No reliance on the local kernel for ACA safety. |
| [CVE-2026-78410](https://security-tracker.debian.org/tracker/CVE-2026-78410) | U, mount/libmount1 2.41.5-0+deb13u1 | Privileged restricted bind mount with replaceable source and X-mount owner/group/mode changes | GNU mount/libmount absent; no SUID, retained libuuid exceeds stable fix 2.42.3-r0. No host mounts or privileged operations added; no residual vulnerable component identified. |
| [CVE-2025-69720](https://security-tracker.debian.org/tracker/CVE-2025-69720) | libncursesw6/libtinfo6/ncurses-base/ncurses-bin 6.5+20250216-2 | infocmp analyze_string consumes crafted terminal description; no TTY required | infocmp absent; libncursesw/libpanelw/ncurses-terminfo-base 6.6_p20260516-r0 are newer than upstream fix 6.5-20251213. Stable package/version and file inventory verified; not a claim based on lack of terminal use. |
| [CVE-2026-16742](https://security-tracker.debian.org/tracker/CVE-2026-16742) | libsystemd0/libudev1 257.13-1~deb13u1 | Logged-in homed-managed user reaches vulnerable systemd-homed authentication | systemd libraries/daemon/helper absent, so known component prerequisite absent. Upstream fixes 258.10/259.8/260.4/261.2/262; no replacement installation needed. Does not assess the ACA host. |
| [CVE-2026-54369](https://security-tracker.debian.org/tracker/CVE-2026-54369) | libacl1 2.3.2-2+b1 | Privileged pathname ACL operation with attacker-replaceable path/symlink | libacl absent; former GNU cp/tar linkage gone, BusyBox tools remain. Upstream fix 2.4.0; absence, not a fabricated library patch. Avoid privileged operations on untrusted paths. |
| [CVE-2026-9538](https://security-tracker.debian.org/tracker/CVE-2026-9538) | perl-base 5.40.1-6+deb13u1 | Malicious tar header parsed through Archive::Tar exhausts memory | Perl and Archive/Tar.pm absent. Upstream Archive::Tar fix 3.10, Debian development perl 5.42.3-1; no parser installation needed. Reassess if Perl/archive tooling is added. |

Upstream references: util-linux [helper](https://github.com/util-linux/util-linux/security/advisories/GHSA-m25x-3hj9-m26f),
[nsenter](https://github.com/util-linux/util-linux/security/advisories/GHSA-55fx-f4gg-cfhj),
[subdir](https://github.com/util-linux/util-linux/security/advisories/GHSA-8f2p-47x3-43mv),
[bind source](https://github.com/util-linux/util-linux/security/advisories/GHSA-rh77-686x-2f2m);
[systemd](https://github.com/systemd/systemd/security/advisories/GHSA-jm29-p7hh-vjhv).
Stable package sources: [util-linux](https://pkgs.alpinelinux.org/package/v3.24/main/x86_64/util-linux),
[ncurses](https://pkgs.alpinelinux.org/package/v3.24/main/x86_64/ncurses).

Remaining concrete risks: public ingress can incur hosting costs before rejection;
stolen authorized credentials no longer encounter a VNet service firewall; native
decoder/crypto and musl behavior beyond the tested cases still need operational
monitoring and vendor updates. In local Docker, effective/permitted/inheritable
capabilities are zero, but the bounding set is nonzero and **NoNewPrivs=0**.
The ARM does not guarantee capability dropping/no-new-privileges. Require actual
platform identity/capability/mount evidence; local flags/kernel are not that proof.
No exploit PoCs, mount operations or privileged containers were used. Root was
used only inside disposable build/inventory containers, not runtime behavior tests.

Recommendation: **accept the local Alpine candidate, keep deployment/activation
blocked** pending separate owner funding/privacy approval and the live matrix.
No known CVE in these eight remains identified in the final components; that is
not a blanket future exception. Re-scan the exact registry digest and requalify
after dependency/base changes. Do not optimize for a zero-CVE count at the expense
of supported packages, preserved runtime behavior or an honest evidence boundary.

## Local preparation commands

These commands do not deploy. Run from the repository root, using the existing
gateway virtual environment. Store private inputs/output under ignored
`infra/pilot/local/`; do not put secrets in shell arguments or terminal output.

```sh
ai-gateway/.venv/bin/python -B infra/pilot/prepare.py backend-package --destination /tmp/pft-pilot-backend.zip
ai-gateway/.venv/bin/python -B infra/pilot/prepare.py ios --outputs infra/pilot/local/deployment-outputs.json --destination ios/Config/Pilot.local.xcconfig
ai-gateway/.venv/bin/python -B infra/pilot/prepare.py entra --outputs infra/pilot/local/deployment-outputs.json --gateway-service-principal GATEWAY_SERVICE_PRINCIPAL_OBJECT_ID --destination infra/pilot/local/entra-requests.json
```

The backend ZIP contains source plus API-only requirements for a reviewed remote
Linux/Python 3.13 build. It is **not** a prebuilt dependency package. Do not upload
the developer virtual environment. The resulting Linux package must be pinned,
hashed and inspected before deployment. Build the gateway on an authorized build
host with `docker build --platform linux/amd64 -f ai-gateway/Dockerfile.api-only
-t pft-api-only:local-review ai-gateway`, then pin the resulting registry digest,
not a mutable tag. The local image was built, not pushed or deployed.

Pilot iOS builds use the existing Release target with an explicit override:

```sh
DEVELOPER_DIR=/Applications/Xcode.app/Contents/Developer xcodebuild -project ios/Trainingsplan.xcodeproj -scheme Trainingsplan -configuration Release -xcconfig ios/Config/Pilot.xcconfig -destination 'generic/platform=iOS' -derivedDataPath /tmp/pft-pilot-derived -disableAutomaticPackageResolution -onlyUsePackageVersionsFromResolvedFile -skipPackageUpdates CODE_SIGNING_ALLOWED=NO build
```

Without generated deployment values this **must fail**. No replacement hostname
is invented. The build phase checks the final resolved values, Release mode,
bundle ID, signing team, redirect URI and unchanged build number 5. Ordinary
Debug/Release builds do not opt in and keep their existing configuration.
Use the same reviewed configuration for a later signed Archive. A scheme-only
environment variable is not an installed-app configuration.

## Deployment sequence, only after separate authorization

1. Obtain private subscription ownership, period funding, stop owner/end date,
   applicable privacy basis and separate bounded live-test authorization. Verify currency
   EUR for budget alerts; the ARM currency confirmation is an owner assertion,
   not a currency conversion. Reprice all SKUs and check regional capacity.
2. Create **new** single-tenant backend API, gateway API and native-client Entra
   registrations. Record their application IDs, object IDs and service-principal
   IDs distinctly. Configure both APIs to request v2 access tokens. The gateway
   exposes only application role `Gateway.Invoke`; optional access-token claim
   `idtyp` is required and service-principal `appRoleAssignmentRequired=true`.
   Only the actual backend managed-identity principal receives that role.
   Gateway validation checks RS256 signature from tenant-fixed JWKS, issuer,
   tenant, exact GUID audience, expiry/nbf/iat, v2/app type, exact oid/azp and
   role. Delegated/scp tokens and other workloads are rejected. No caller-supplied
   JWKS URL is used. Key rotation uses the bounded JWKS cache.
3. Prepare a new resource group named `pft-pilot-<private-name>` and a private
   parameter file. All required template parameters are explicit: pilot name;
  tenant/native/backend/gateway application IDs; one or two approved `{tid, oid}`
  entries (initial synthetic acceptance permits only the owner);
   the reviewed policy; all-in budget/currency/dates/email recipients; model
   capacity; four independent random secrets of at least 32 characters. Secret
   values must come from a secure operator context, never this repository.
   Bootstrap with `deployGateway=false`, `enableAI=false`. This creates only new
   pilot infrastructure, identities and the empty Table, not a working AI route.
    The current deployment record identifies completed provider validation, quota
    and live RBAC checks and remaining gaps. Do not treat successful JSON parsing
    as Azure validation or assume a previous deployment qualifies a new one.
4. Build/scan/pin the API-only artifact and Linux backend package. Push only to
   the new registry after approval. Apply the runtime template with
   `deployGateway=true`, exact image digest, **enableAI=false**. The API-only
   image serves liveness but denies readiness/analysis until its signed release
  checks pass. Apply `budget.json` to the actual pilot output group; leave the
  optional infrastructure group empty unless inventory identifies one requiring
  coverage. Storage/Key Vault/OpenAI endpoints are publicly reachable under
  Variant B, with Entra/RBAC authorization, not subnet allowlists. Verify effective
  grants, local-key/Shared-Key denial and anonymous rejection before publishing
  code or administering data; network reachability is not permission to access it.
5. Capture deployment outputs without secret settings, generate the Graph request
   bodies and review/apply them only to these **new** registrations. These bodies
   replace role/scope arrays; never apply them to an existing production app.
   Consent only the native client's delegated `FoodAnalysis.Access` scope. The
   backend's managed identity gets no user permissions or Graph permissions.
   Configure the gateway service principal and apply the generated role assignment
   using the actual backend identity output, not its name or the iOS client ID.
   Verify Easy Auth signature/lifetime validation, header stripping, exact
  issuer/audience/client and the approved allowlist on all backend ingress.
6. Initialize the new ledger **once**, using the gateway identity, while
   `AI_API_ONLY_ENABLED=false`, with the reviewed settings and policy:
   `python -m app.pilot_release initialize-ledger --confirm-new-pilot-ledger`.
   The command refuses benchmark policy/table names and an existing ledger;
   creation uses the existing CAS store. It never clears or replaces old state.
   Validate Table RBAC and concurrency with synthetic data under separate approval.
7. **Pre-activation qualification, AI off:** the existing API-only ingress now
  applies route/header/size bounds, exact workload JWT and service secret,
  bounded body decoding, request-bound HMAC and the configured user allowlist,
  then the activation grant. `/readyz` is workload-authenticated but has no
  analysis body/HMAC. Invalid authentication is denied even with AI off; a
  valid signed analysis receives503 before dependencies, ledger reservation or
  provider construction. No qualification endpoint or bypass is added.
  `qualify_auth.py` has separate `auth`, `boundaries` and `foreign` operator modes
  so already-passed live checks need not be repeated. It targets only the recorded
  private pilot and never sends an acceptance-manifest payload. Any token
  acquisition failure is not an authorization test, including AADSTS501051.
  The `foreign` mode obtains an actual Azure Storage audience token from the
  existing gateway UAMI, validates its diagnostic identity/expiry metadata, and
  requires a real gateway403 with otherwise correct service/HMAC headers. This
  combined wrong-principal/wrong-audience case does not isolate the principal or
  role check; unverified claim decoding is not signature verification. Preserve
  failed evidence, and do not sign a missing check. Jobs have no ingress/new roles and
  must be bounded, non-retrying and deleted after use.
  The actual native analysis mapping requires a personal login, not a reused CLI
  token. From the repository root, use the existing private CLI context:

  ```sh
  ai-gateway/.venv/bin/python -B infra/pilot/provision.py login-analysis-probe \
    --azure-config "$PFT_AZURE_CONFIG" --subscription "$PFT_SUBSCRIPTION" \
    --tenant "$PFT_TENANT" --name 20260919
  ```

  These variables must identify the previously verified private CLI context and
  the subscription/tenant in the private period record, never the default work
  account. Do not recreate the context or persist its tokens in the repository.
  This checks AI off before login and uses only nonmanifest analysis payloads.
  Tokens stay in memory; complete sign-in personally, never paste credentials
  into chat. A503 alone is not downstream-token proof; inspect the existing
  content-free gateway boundary logs as well. This command grants no activation.
  In a secure local/operator context, load the exact runtime configuration and
   keys. `python -m app.pilot_release digest` returns its SHA-256 binding, not its
   contents. Capture evidence as one JSON object with the six keys in
   `app.pilot_release.CHECKS`: identity, deployment, table_rbac, ledger, budget,
   privacy. Each record contains `configuration_sha256`, integer `checked_at`,
   and `checks` with **every named criterion true**. Preserve underlying sanitized
   test/inventory/owner records privately; these booleans are owner attestations,
   not proof manufactured by the software. Distinguish local tests from live
   observations. Never label a required live check passed from a mock alone.
  For a policy with `acceptance`, the privacy criteria are the explicitly
  synthetic `ACCEPTANCE_PRIVACY_CHECKS`, including metadata legal basis and a
  reviewed fixed manifest. These do not authorize ordinary health-data input.
   `python -m app.pilot_release approve --owner-approved --evidence EVIDENCE_JSON
   --destination NEW_APPROVAL_JSON` signs only complete, current, config-bound
  records. Set `deployment_verified_until` to the explicitly approved pilot end
  date, at most 31 days ahead, before ledger initialization. Put approval
   JSON and signature in their separate Key Vault secrets. The release key is
   distinct from service, request-signing and fingerprint keys.
8. **Controlled technical acceptance, not participant release:** only the
  separately authorized, bounded activation sets `enableAI=true` for
   this exact digest/config. Runtime checks every request and every production
   provider dispatch; readiness additionally checks the existing unblocked ledger
   with the exact policy digest. The Coordinator still performs the only budget
   reservation and single-use dispatch permit. Neither an environment rename,
   an activation flag alone nor a valid user token enables the old Azure path.
  Synthetic acceptance grants last at most one hour and never beyond the fixed
  acceptance/pilot expiry. Issuing the initial technical grant requires the
  completed pre-activation evidence, not evidence of revoking that same grant.
  Next prove acceptance and revocation with still-valid workload tokens using
  readiness and signed nonmanifest analysis probes, without a model call. The
  signed nonmanifest payload must fail before reservation while active and at
  the release gate after revocation. Record this second-stage evidence separately;
  `qualify_auth.py` mode `release` compares a prior token fingerprint when testing
  an off state. Distinct job executions can receive different MI tokens; never
  infer token identity from the client ID. Mode `cycle` keeps one token in RAM,
  proves readiness200/nonmanifest403, and accepts the operator job-stop SIGTERM
  for at most120seconds. The operator must first verify the new AI-off revision
  is **latestReadyRevision**, not merely the latest configured revision. The
  same process then requires readiness503/nonmanifest503 and unchanged ledger
  content/ETag. The job still has its180-second execution deadline and retry0.
  No model input, token persistence, application debug endpoint or runtime
  administrative permission is added. A completed cycle writes only its bounded
  checks to `qualification-release-v1/result` in the existing Table, create-only;
  `cycle_result` reads it; only after verified local receipt does `cycle_cleanup`
  ETag-delete that isolated record. It does not delete
  operations or reset the pilot ledger. Preserve a private receipt before claiming
  success; transient job console logs can disappear at stop/scale-down.
  Read and clean this model-free receipt before the first model case; its guard
  intentionally requires the original zero-attempt ledger.
  Never rewrite prior failed/absent checks as passed. Renew only inside the same
  authorized scope, without changing lifetime counters, budgets or unknown holds.
  Run at most ten existing-manifest model attempts only after safety acceptance,
  without retries, then disable AI/revoke the technical grant. Participant and
  health-data release, the second identity and device acceptance remain separate.
  Finish the live matrix below before the two-person pilot is generally usable.

The image marker is a packaging boundary, not a remote attestation service. An
operator able to replace code/secrets can defeat application controls. Image/RBAC
review and owner evidence are required. Signatures bind reviewed configuration;
they do not independently inspect Azure or establish truth of privacy approval.
Gateway admission has an 8-connection runtime cap, 10-second body deadline and
4 MiB + 64 KiB JSON bound before parsing; backend checks 3 MiB + 64 KiB before
multipart/JSON parsing and configures the Functions host body limit. Host-worker
buffering, edge header/connection bounds and real enforcement still require live
verification. An app-level check is not a complete internet DDoS cost cap.

## Bounded synthetic model execution

`qualify_models.py` is separate from the model-free authentication helper. One
explicitly selected case executes per bounded, manual, retry0 job using the
existing backend MI and gateway route. It validates the normalized manifest hash,
expected lifetime attempt count and full-reserve sum, with no blocked/active
ledger operation. A create-only intent in `qualification-model-v1` precedes HTTP
dispatch. Never delete that intent to repeat a failed or ambiguous case. The
gateway remains the authoritative CAS admission and provider-dispatch boundary.

The runner sends once with a110-second client timeout; it stores the synthetic
response and accounting receipt separately from the real operation ledger.
Console output contains only case/status/count metadata. A missing response,
unknown usage, active hold, blocked ledger or unexpected count stops progression
for operator review, without retry or counter reset. Retrieve synthetic results
through the existing administrative channel into protected local diagnostics;
do not emit raw results into application logs. Delete only isolated diagnostic
rows after confirmed private receipt, retaining intents until execution is closed.
Respect person/minute limits between separately authorized cases, the remaining
signed-grant lifetime and the original fixed pilot period. P5 is a non-food
abstention case, not a safety-filter test. Finish with AI disabled and no job.

The runner additionally requires at least65 seconds since the last committed
admission. This is a pre-dispatch gate, not a retry loop or proof that an image
fits the deployment's TPM limit. Safe gateway request IDs, normalized error codes
and numeric gateway Retry-After hints are captured in the protected receipt;
they are not Azure provider request IDs or provider rate-limit headers.

`complete_terminal_429` is an operator-only, hold-preserving correction, not a
runtime endpoint or automatic recovery rule. First disable gateway admission and
independently review the completed provider429 and exact operation receipt. Old
receipts without an error code need independent provider evidence; L1 was checked
against Azure model status metrics. Bind the reviewed receipt and full live ledger
by SHA256, then atomically compare-and-swap the ledger and exact operation ETags.
The helper requires a settled unknown operation, its full USD0.2343 charge, the
matching personal slot and at least120 seconds since completion. It removes only
that execution slot and records completion evidence on the retained operation.
Usage stays unknown; costs, bucket counts, lifetime reservations, fingerprint and
replay protection do not change. Timeouts, cancellations, mismatches and CAS
conflicts must not be treated as completed provider429 responses. A missing
administrative receipt requires readback before another mutation. This does not
resolve unknown billing or authorize a failed case to run again.

## Renewal, shutdown and rollback

- **Initial authorization** approves the exact artifact, configuration, two
  identities, fixed funding/limits, privacy basis and pilot end date. It requires
  all six evidence groups and explicit `approve --owner-approved`. It is not a
  recurring daily human approval. No actual owner authorization is supplied here.
- **24 hours** is the maximum age of the technical runtime evidence, not the
  pilot duration or an automatic daily budget reset. Signed `issued_at` and
  `expires_at` are bounded by the oldest technical check and the pilot end date.
  Run `renew --previous SIGNED_JSON --evidence FRESH_JSON --destination NEW_JSON`
  from a separately authorized operator workflow, e.g. every 12 hours. It requires
  freshly verified identity/deployment/Table/ledger records and a valid signed
  owner context; unchanged budget/privacy evidence hashes carry forward. Expired
  runtime evidence can be renewed inside the still-valid owner period, but cannot
  authorize requests during the gap. No ledger mutation or policy-digest change.
  Renewal cannot change image, keys, limits, identities, funding or pilot end date.
  Do not fabricate new `checked_at` timestamps over old probe results.
- The renewal command is offline and scriptable, not a deployed scheduler or
  cloud probe collector. The owner must bind it to real approved probes and
  publish the new approval/signature to Key Vault, then explicitly refresh/restart
  the revision that reads them as environment values. Verify new readiness before
  expiry; background secret refresh timing is not assumed. No extra paid service
  is added. Prove this automated operator workflow before continuous pilot use;
  a missed run fails closed instead of requiring a daily manual approval.
- Expired/missing approval, disabled flag, invalid budget, wrong ledger digest,
  unavailable Table or exhausted limits fail closed. No automatic retry/repair.
  Health is liveness only. Readiness is workload-authenticated and never performs
  model inference; it is not evidence of a successful model response.
- Set `enableAI=false` to stop new calls; first stop backend admission for an
  emergency shutdown, then deny gateway admission/revoke the role if necessary.
  Stop the renewal workflow and rotate/remove the release key for durable grant
  revocation; Entra role removal alone does not invalidate already-issued tokens.
  Refresh all active revisions and verify denial, do not rely on cached secrets.
  In-flight calls may have been billed: keep their operations/holds and reconcile.
  iOS manual entry remains available. Do not uninstall or delete its store.
- There is currently **no known compatible API-only rollback release**. Until one
  has passed this same matrix, rollback is AI off, never the Copilot image/route.
  Revoke old Copilot server access as a separately authorized migration step; the
  local package neither edits the existing deployment nor rotates its credentials.
- Before any policy/expiry/key change, stop admission, drain in-flight work and
  use the existing reviewed ledger carry-forward procedure. Policy expiry is part
  of the policy digest: updating it alone deliberately does **not** reset/renew the
  ledger. Preserve counts, spend, unknown holds and operation records. Do not run
  `initialize-ledger` again. A verified carry-forward and fresh signed evidence
  are required only when owner scope/policy changes, not for technical 24-hour
  evidence renewal. A new owner period never silently resets monthly spend.
- Arrange bounded metadata cleanup using the existing `AzureTableStore.cleanup`
  (31 days, no payloads, unknown expiry blocks the ledger). This package does not
  add a paid scheduler or silently delete unknown holds. Assign an operator cadence
  and verify deletion/backup retention before privacy sign-off.
- Update the same signed iOS app with the same bundle/team, after export/backup;
  no build number, SwiftData model or backup format is changed here. Existing
  production stays installed until explicit signed-device acceptance.

## Content-free diagnosis

The API-only ingress emits server-generated request ID, UTC time, fixed boundary
(`shape`, `workload`, `body`, `assertion`, `release`, `ledger`, `domain`, `internal`), HTTP status and
latency. No user path/query/header, identity, food, image, output or exception text
is included. Limit: 60 events/minute/process plus a suppressed-count summary;
anonymous liveness is not logged. Domain/provider normalized metadata and the
existing payload-free operation ledger distinguish admission, timeout/refusal,
usage uncertainty and settlement. No stacktrace is propagated from ASGI failures.

Use ACA console/system **live streams**, revision/restart/replica/CPU/memory and
Functions platform metrics, authenticated readiness and metadata-only ledger
inspection to investigate. During activation and incidents, an authorized operator
captures only these streams into access-controlled local evidence (seven days),
then verifies deletion. No Log Analytics/Application Insights ingestion is
configured: cost is zero for those absent services, **not zero observability**.
Transient logs can disappear at scale-to-zero/restart; this package does not
promise unattended historical log search. A working incident capture/notification
procedure, with no payload tracing or SDK DEBUG logging, is a release gate. If
durable unattended telemetry is required, stop for a separately reviewed cost and
privacy decision instead of silently adding a paid service. Metadata is still
pseudonymous personal data; restrict access and retain only as approved.

## Live acceptance matrix

Live checks are authorized within the EUR 20 / 30-day plus EUR 5 setup scope.
Only the current deployment record claims completed live checks; local tests
are not substitutes. The second participant remains excluded.

| Boundary | Required acceptance |
| --- | --- |
| Backend/Easy Auth | Both allowlisted accounts; reject third account, wrong tenant/issuer/audience/client, expired/user-supplied platform headers, app-only tokens, alternate host and deployment ingress. Verify the actual injected claim mapping. |
| Gateway | Reject no token, native token, wrong workload oid/azp, missing/wrong role, v1 token, wrong audience/issuer/tenant, expired/future token, bad signature and rotation failures. Tamper service token, HMAC body, identity, operation, timestamp, duplicate headers and query/path. No provider dispatch on rejection. |
| Ingress/privacy | Oversized/chunked/slow body before domain parsing; Functions host and ACA edge bounds; concurrency/scale ceilings; no auth headers, user text/images/results, token URLs or SDK bodies in logs. No token cache persisted. |
| Table/RBAC | Gateway only its Table and model, backend only host blobs/shared secrets; anonymous and unauthorized identities denied despite public network reachability; CAS races across two processes; no shared-key access. Scope/connectivity/identity failure must deny dispatch, not switch stores. Inspect inherited roles and any user-delegation SAS authority. |
| Idempotency/accounting | Duplicate/changed/expired/unknown UUIDv7, racing calls and lost responses; one dispatch, no result replay; refusal, missing usage, reserve exhaustion, expiry, outage, stop/restart and carry-forward preserve spend and uncertainty. |
| Model quality | Original T2 plus independent gram/per-100-g/per-serving/total bases; missing macros not zero; consumed vs package quantity; raw/prepared conflict; packaging kcal independent of macros; fractions/refinement not scaled twice. Verify copied values, coverage and null/complete choices, not merely arithmetic. |
| Output/workflows | Real final extraction contract under 2,000 tokens, schema/truncation frequency and cost per usable answer; text, camera/library image, combined input and refinements; refusal produces no new saveable draft; late/closed responses cannot save. No hidden retries. |
| iPhone/MSAL | Installed launch, silent/interactive token acquisition, redirect, cancellation, account switch, background/network loss and explicit new-operation confirmation on both users' devices. No embedded server secrets. |
| Data/update/rollback | Export before signed update without uninstalling; compare old meals, workouts, weights and settings; import/export compatibility; save/cancel/error at most once; verify AI-off/manual entry and later compatible API-only rollback. |

## Privacy release criteria

Before either participant's nutrition/images leave a device: document controller
and processor responsibilities, health-data legal basis/consent and information,
Microsoft DPA/subprocessors/transfers, EU DataZone scope (not Sweden-only), provider
abuse-monitoring retention and exceptions, withdrawal/deletion, incident ownership,
access and backup policy. `store=false` is not zero provider retention. No real
participant data in test fixtures. Record 31-day pseudonymous accounting retention,
bounded diagnostic retention and verifiable deletion. No privacy approval is given
by this implementation or by signing an empty checklist.

## Complete monthly cost proposal

**Historical proposal, superseded by the one-time authorization in the current
deployment record.** EUR 50/month remains an old proposal, not an authorization,
hard cap or approved increase. The calculations
below replace the arbitrary USD 20 ACA and USD 5 network allowances. Prices were
checked against official public pricing and the unauthenticated Azure Retail
Prices API on **2026-09-18**, USD Consumption, Sweden Central unless noted.
They are list prices, not a subscription-specific EUR invoice quote. Offer/free
grant eligibility, tax, FX and regional capacity remain owner verification gates.

### Rates and required fixed resources

| Planned SKU / meter | Verified USD list rate | Source / representative meter ID |
| --- | --- | --- |
| Foundry Models / Azure OpenAI S0, GPT-5.4 mini 2026-03-17 DataZoneStandard | 0.825 input, 0.0825 cached input, 4.95 output per million tokens | Retail `fc81bb98-83fa-569b-a361-70d5904b285d`, `41b51273-5b41-5b0b-ba4b-3900379c9800`, `3167a76c-f4a1-53f1-8784-362e76c0787e`; no PTU reservation |
| ACA Consumption | 0.000024/vCPU-s active, 0.000003/GiB-s, 0.40/million requests | [ACA pricing](https://azure.microsoft.com/en-us/pricing/details/container-apps/); regional CPU meter `4ea1c35d-d999-57d0-88f2-e689d3475fcd` |
| Functions Flex Consumption FC1 on demand, 512 MiB | 0.000026/GB-s, 0.40/million executions | [Functions pricing](https://azure.microsoft.com/en-us/pricing/details/functions/); `a5521323-e093-53b5-b6bf-cabc4e098293`, `784e0fc6-81bd-55cc-9f0b-3d0f628a7392` (Retail execution unit is **10**, USD 0.000004, not one) |
| ACR Basic, <=10 GB included | 0.1666/day | Retail `5c9e7a65-5784-494c-9718-7749d4075dd9`; **4.998/30 days**, no ACR Tasks |
| StorageV2 Hot LRS blobs | 0.0184/GB-month; reads/other 0.004/10k, writes/list 0.05/10k | Regional Retail Hot LRS, storage meter `39d8c6c1-22c0-5719-9330-593a56b3a2e0` |
| Standard LRS Tables | 0.045/GB-month; operations 0.00036/10k | Regional Retail Tables (regional alias rows are not discarded by `isPrimaryMeterRegion`) |
| Key Vault Standard secrets | 0.03/10k operations | Regional Retail / [Key Vault pricing](https://azure.microsoft.com/en-us/pricing/details/key-vault/); no HSM/certificate SKU |
| Internet egress, Europe / Microsoft network | 0.087/GB after eligible first 100 GB/month | [Bandwidth pricing](https://azure.microsoft.com/en-us/pricing/details/bandwidth/); inbound and same-region transfer free |

Reproduce price queries through [Azure Retail Prices API](https://prices.azure.com/api/retail/prices):
`armRegionName eq 'swedencentral' and priceType eq 'Consumption'`, filter exact
product/SKU/meter/unit, and follow every `NextPageLink`. Model service is `Foundry
Models`, meter spelling `5.4 mini`. No free-labelled network offer is used to
discount a billable resource: the removed LB/IP quantities belong to the previous
customer-VNet topology, not the corrected ARM.

### Fixed-cost and variant B audit

**USD 4.998, rounded USD 5.00, is the planned fixed cost of the corrected ARM for
30 days.** The earlier USD 30.198 included USD 25.20 of customer-VNet managed LB/IP
charges. That configuration has now been removed under the explicit local-change
authorization. This is neither a claim that Azure has no underlying network
infrastructure nor that all hosting/network usage is free.

| Resource | SKU / quantity | Unit price and official source | Fixed USD | ARM definition in [main.json](main.json) |
| --- | --- | --- | ---: | --- |
| Image registry | ACR Basic, one | 0.1666/day; [Retail API](https://prices.azure.com/api/retail/prices), Sweden Central meter `5c9e7a65-5784-494c-9718-7749d4075dd9` | 4.998 | `Microsoft.ContainerRegistry/registries`, `sku.name=Basic` |
| Separately billed customer-VNet managed LB/public IPs | Zero requested | [Managed-resource billing](https://learn.microsoft.com/en-us/azure/container-apps/custom-virtual-networks#managed-resources) applies when supplying a customer VNet | 0.000 | No `vnetConfiguration`, custom subnet or infrastructure resource-group property |
| Dedicated-profile management, NAT, Private Link, paid DNS/telemetry | Zero requested | [ACA billing](https://learn.microsoft.com/en-us/azure/container-apps/billing); only Consumption profile, none of these features | 0.000 | No corresponding profile/resource/feature declarations |
| **Total** | | | **4.998** | Rounded once: **5.00** |

[Microsoft's managed-resources specification](https://learn.microsoft.com/en-us/azure/container-apps/custom-virtual-networks#managed-resources)
explicitly introduces the managed resource group and LB/IP charges **when providing
your own VNet**. [Default networking](https://learn.microsoft.com/en-us/azure/container-apps/networking)
instead uses an Azure-managed network and internet-accessible dependencies.
[ACA billing](https://learn.microsoft.com/en-us/azure/container-apps/billing) and
the pricing page charge Consumption compute/requests, with additional networking
charges for customer-VNet configurations; neither specifies a separate Standard
LB/two-IP fixed SKU for this default-network deployment. No Dedicated profile,
private endpoint or separately billed optional networking feature is requested.
This documented distinction, not absence of explicit LB resources alone, supports
removing those charges. Verify actual inventory and billing after separately
authorized provisioning; local ARM cannot prove the eventual invoice or exclude
subscription policy additions. ACR Basic remains the chosen authenticated registry,
not a requirement of public HTTPS/JWT itself.

Corrected topology and dependency check:

- Gateway remains public HTTPS: `configuration.ingress.external=true`,
  `allowInsecure=false`, external environment. Backend uses its public ACA FQDN.
  No private route is required between backend and gateway. Anonymous health is
  deliberate; readiness and analysis require the exact backend workload identity.
- Removed the VNet, gateway/backend subnets, service endpoints, network variables,
  subnet dependencies, ACA `vnetConfiguration` and Functions
  `virtualNetworkSubnetId`. The backend already uses HTTPS to the actual public
  gateway FQDN and explicit managed-identity authentication; it has no private-IP
  or private-DNS dependency. Functions outbound VNet integration is optional for
  this public path, not an authentication prerequisite.
- Environment is **Workload profiles with a Consumption profile**, not the legacy
  Consumption-only environment. No Dedicated profile is present. Azure-managed
  networking is selected by omitting customer VNet configuration. Network type is
  not a migration toggle for an existing environment; this package provisions a
  new pilot and does not alter an existing deployment.
- Storage, Key Vault and OpenAI use **public endpoints without subnet firewalls**:
  `publicNetworkAccess=Enabled`, ACL `defaultAction=Allow`, `bypass=None`, empty
  IP/VNet rules. Removing the old default-deny rules is necessary once their
  allowed subnets are gone. The old Key Vault trusted-service bypass is removed.
  Public reachability does not disable Entra authentication or resource RBAC.
- Private Endpoints: **zero**. NAT Gateway: **zero**; managed egress/SNAT is not
  a billable customer NAT Gateway. Private/public DNS zones, resolver, DNS links,
  custom domains, VPN, Firewall and Application Gateway: **zero**. Platform
  FQDNs/default DNS are used. No customer VNet, NSG or UDR is defined.
- Strict gateway JWT validation (tenant-fixed RS256 keys, audience, issuer,
  lifetime, exact backend oid/azp and app role, no delegated token), service token
  and request-bound HMAC protect **gateway admission**. They do not authenticate
  direct Storage, Key Vault or model access. Those rely on separate managed
  identities/RBAC: gateway Table Data Contributor on its table, OpenAI User on
  its dedicated account, AcrPull and six secret-reader grants; backend Blob Data
  Owner on host storage and two secret-reader grants. Shared Key, anonymous blob
  access, registry admin and model local-key authentication are disabled.
  Shared-Key denial also blocks account/service SAS, but does **not** block an
  Entra-authorized user-delegation Blob SAS; inspect actual grants accordingly.
- Exact backend JWT identity/app role, HMAC/service token, request sizes/deadline,
  release signature, ledger CAS, one-dispatch permit and every budget/count limit
  are unchanged. Full-ingress tests reject anonymous/missing/wrong credentials
  before dispatch even under a valid release. Public access is not anonymous
  model access; direct model calls still need the scoped Entra role.

The authorized tradeoff is explicit: a stolen **authorized** credential can now
reach a public dependency from outside the former VNet. Identity/RBAC replaces
that network boundary, not credential-theft protection. Live effective and
inherited roles, service authorization, Easy Auth and ingress behavior still need
acceptance; local mocks cannot establish them. The budget template now permits a
single pilot-group filter, retaining optional coverage for an additional actual
managed group; its amount and notification thresholds are unchanged.

**Fixed total: USD 4.998/30 days**, including zero model calls or AI off while the
registry exists. A 31-day month adds USD 0.1666, giving USD 5.1646. Compute
deallocation alone does not stop registry charges. Usage-priced compute,
operations, storage and internet egress below remain additional costs.

### Normal-use scenarios and assumptions

Both rows count **total** calls across both people, including refinements. These
are unmeasured planning assumptions, not benchmark-derived container timings:

- Per model call: 4,000 uncached input-equivalent tokens including image tokens,
  1,000 output tokens = USD 0.00825. Final prompt/image/response sizes unmeasured.
- ACA 0.25 vCPU / 0.5 GiB, min0/max1: each isolated cold session costs 5 seconds
  startup + 30 seconds request + 300 seconds scale-down tail = **335 seconds**.
  Sixty technical readiness/renewal checks/month each add 5 + 3 + 300 = 308 seconds.
  Sum is `calls*335 + 60*308`; separated sessions are conservative compared with
  overlapping tails, but slower startup/inference/scale-down can exceed it.
  [ACA billing](https://learn.microsoft.com/en-us/azure/container-apps/billing):
  min0 scale-down tail uses active rates, not the discounted min-replica idle rate.
  The documented 300-second cooldown/stabilization is a planning value, not a
  measured deployment guarantee. Always-on external polling would change the bill.
- Functions: 0.5 GB * (35 seconds/call including gateway wake-up + 3 seconds/check),
  plus executions. No always-ready instance. Actual billed duration/memory needs
  acceptance; the 100-second timeout is not normal expected runtime.
- Blobs: 1 GB, 100k read/other and 1k write/list operations/month = USD 0.0634.
  Tables: 0.1 GB, 12 operations/call + 4/check + 1k cleanup operations. KV:
  6 reads/cold session + 8/check + 100 rotations/admin reads. Host leases, retries,
  contention and deployment churn must be metered; these counts are assumptions.
- Internet responses: 20 kB/call. Large images/bursts/exports change this; no image
  egress to the same region is additionally charged as Internet egress. No separate
  LB-processed-data charge for the removed customer-VNet topology. No paid
  telemetry service.

| USD net / 30-day month | 600 total calls | 1,200 total calls |
| --- | ---: | ---: |
| Fixed ACR for selected ARM | 4.9980 | 4.9980 |
| Model | 4.9500 | 9.9000 |
| ACA before grants | 1.6464 | 3.1541 |
| Functions before grants | 0.2756 | 0.5488 |
| Blobs + Tables + KV | 0.0807 | 0.0918 |
| Internet before grants | 0.0010 | 0.0021 |
| **Total before grants** | **11.95** | **18.69** |
| **Total with fully available eligible grants** | **10.03** | **14.99** |
| EUR illustrative, before grants (0.95 EUR/USD, 19% VAT) | **13.51** | **21.13** |
| EUR illustrative, with grants (same FX/VAT) | **11.34** | **16.95** |

ACA usage is respectively 54,870 / 105,120 vCPU-s and 109,740 / 210,240 GiB-s,
plus 660 / 1,260 requests. Eligible monthly grants: ACA 180k vCPU-s, 360k GiB-s,
2m requests; Flex 100k GB-s and 250k executions; Internet 100 GB. Both scenarios
fit **if** these shared subscription/offer grants are still fully available.
They do not remove ACR/model/storage/KV charges. Do not budget on grants until
eligibility and other consumption are verified. No cached-input saving assumed.

### Reserve, enforcement and abuse are different

Separately proposed **25% reserve on non-fixed, before-grant usage** is USD 1.74
or USD 3.42, not an expected charge or approved expenditure. Totals including that
reserve are USD **13.69 / 22.12**, illustrative EUR **15.48 / 25.01**. This simple
sensitivity buffer covers only modest token/runtime/operation variation, not FX,
an extra calendar day, arbitrary attacks or newly required services. The old claim
that this buffered 1,200-call scenario exceeds EUR 50 no longer applies to Variant
B. Nevertheless, EUR 50 is unapproved and 1,200 calls remain prohibited by the
unchanged policy; lower infrastructure cost is not authorization to increase it.

Technical policy is unchanged: 600/month global, 300/person; 40/day global,
20/person; USD 10/month global, 5/person; concurrency 2 global, 1/person.
Admission reserves the full possible input plus 2,000 output tokens: **USD 0.2343**
per call, not the USD 0.00825 average. Unknown/failed holds remain charged/reserved.
Thus **1,200 is a cost comparison, not currently admitted operation**; even changing
only the call limit would not ensure 1,200 completions under USD 10 because the
last requests need reserve headroom. No reuse of the closed benchmark allowance.

[Current Flex limits](https://learn.microsoft.com/en-us/azure/azure-functions/flex-consumption-plan)
(updated 2026-09-18) allow maximum instance count **1**, replacing the outdated 40
minimum. Template uses max1, 512 MiB, HTTP concurrency2, no always-ready; this is
the smallest supported maximum for this HTTP-only, two-user workload. Prove 512
MiB stability and two concurrent requests live; do not silently scale up. Separate
scaling groups/always-ready are not added. ACA is min0/max1, HTTP target2; platform
maintenance/revision replacement can transiently overlap replicas, so max1 is not
an absolute financial limit.

Abuse is not covered by normal model volume: unauthenticated traffic can keep
hosting active even while model admission is denied. At one continuously busy
instance each, ACA compute is USD **19.44/month**, Flex compute USD **33.696/month**
before executions, no grants, plus fixed USD 4.998 and up to the approved model
admission allowance. Requests, data, storage contention, revision overlap and
platform work can add more; no finite all-in attack bound is proven. Rate/body/
concurrency controls reduce exposure but are not an edge DDoS spending cap.

The pilot-group budget and subscription-level filter (including an additional
group only if actual inventory requires it) are delayed notifications, **not
technical enforcement**. Assign forecast review,
an incident/stop owner and explicit shutdown triggers before funding. Include
existing diagnostic policies, Entra licensing, retention and all managed resources
in the actual inventory. No extra Premium entitlement, paid operator host or log
ingestion is assumed; if required, it blocks release pending a priced decision.

### Separate one-time setup and acceptance

Local build/scan/unsigned device build uses the existing computer and installed
tools; no Azure execution charge occurred. Engineer time, electricity and existing
Apple membership are not priced as zero business cost or newly purchased here.
ARM/Entra setup has no separate request SKU assumed, but created resources start
billing immediately, including while AI is disabled.

A **historical, unapproved proposal, now superseded by at most ten attempts**, was
at most 40 new live model attempts
over two setup days: expected model spend USD 0.33 at the token assumption, or
conservative aggregate full-input reservation **USD 9.372**. Add two days of fixed
resources **USD 0.3332** and normal host execution about USD 0.13 (40 cold calls,
four technical checks), plus actual data/secret/storage operations. This is not
a hard all-in setup cap; specify actual attempts, time window and stop conditions
in the approval. Do not double-count those fixed days if already inside the
monthly scenario. Runs beyond the window, archive distribution and retention
require an explicit decision; no new numeric funding is approved by this text.
Live acceptance must be bounded first, then supply genuine acceptance evidence
before normal use. Never pre-attest an unrun model/device check to bypass that gate.