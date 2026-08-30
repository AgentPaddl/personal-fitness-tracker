# Operations runbook

Practical, sanitized procedures for operating the deployed production stack. No
secret values appear anywhere in this document — only resource names, setting
*names*, and commands with placeholders for anything sensitive.

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
