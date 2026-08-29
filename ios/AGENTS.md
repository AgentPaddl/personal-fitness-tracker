# iOS agent instructions

These instructions apply to everything under `ios/`.

## Current component

- SwiftUI application in `ios/Trainingsplan/`.
- SwiftData models provide local persistence for fitness, workout, weight, goal, and nutrition data.
- The Xcode project is `ios/Trainingsplan.xcodeproj`.
- `ios/FoodAnalysisKit/` is a local Swift package (added as a package dependency of the `Trainingsplan` target) holding the food-analysis networking/DTO/validation logic, independently testable via `swift test` without Xcode, SwiftData, or a real backend.

## Change rules

- Preserve current screens, navigation, persistence, import/export, and other behavior unless a task explicitly changes them.
- Follow established SwiftUI and SwiftData patterns in the project. Prefer narrowly scoped changes over broad refactors.
- Treat model changes as data migrations. Do not delete or repurpose persisted fields or make destructive schema changes without an explicit migration plan, compatibility review, and task approval. Existing personal data must survive updates.
- Keep domain and presentation logic independent of any AI provider SDK or transport.
- Never add GitHub/Copilot credentials, OAuth tokens, provider secrets, wrapper URLs, or provider-specific model identifiers to the app or its bundled configuration.
- The app talks only to our own Azure Functions backend's public API (`POST /api/food-analysis` today). It must never know about the Personal AI Gateway, GitHub Copilot, model ids/routing, SDK details, or gateway internals.
- Send sensitive data only to our authenticated application API and only when required by an explicitly approved feature.
- AI-derived nutrition or activity values are estimates; present them for review/confirmation before persistence where appropriate. Persist only after explicit user confirmation, never automatically.

## Food analysis (text) flow

- `NutritionView` hosts a "KI-Analyse (Text)" section where the user types a natural-language food description and triggers analysis via `FoodAnalysisKit.FoodAnalysisViewModel`, which calls `FoodAnalysisService` against the backend's `POST /api/food-analysis`.
- A successful analysis presents `FoodAnalysisReviewView` (app target) as a sheet with editable name/calories/protein/carbs/fat, pre-filled from the estimate. Confidence/warnings are shown as non-persisted review metadata only.
- Confirmation is coordinated by `FoodAnalysisKit.FoodEntryPersistenceCoordinator`: it inserts then saves, rolls back (deletes) the inserted object if the save throws, and guarantees at most one committed save per presented review (a rapid duplicate tap on "Übernehmen" is a no-op once saving/committed). A failed save shows an inline error in the sheet (never console-only), never dismisses, and allows retry. Cancelling/dismissing the sheet never touches `modelContext`.
- Review values are validated (`FoodAnalysisReviewDraft.validated()`) before save: blank name, unparsable/negative/non-finite numbers, and out-of-bounds values (matching the backend's own 0...10000 kcal / 0...1000 g bounds) are all rejected. Calories are parsed as a decimal (comma or dot) and rounded to the nearest whole number.
- Image analysis is not implemented; this phase is text-only.

## Backend base URL configuration (fail-closed)

- Configured via `FoodAnalysisKit.APIConfiguration.resolveBackendBaseURL()`, which returns a `Result` and never silently substitutes a fallback host for an explicitly-set but invalid/insecure value.
- **Simulator**: leave `API_BASE_URL` unset to use the recognized local-development default `http://127.0.0.1:7071/api` (the Simulator shares the Mac's network namespace, so loopback reaches `func start` directly). This default only compiles in for Simulator builds (`#if targetEnvironment(simulator)`); a device build with no override fails closed with a clear configuration error instead of silently trying `127.0.0.1` (which would just be the device itself).
- **Physical device**: set `API_BASE_URL` explicitly on the app's Xcode scheme (Product > Scheme > Edit Scheme... > Run > Arguments > Environment Variables) to the Mac's reachable LAN address, e.g. `http://192.168.1.23:7071`. Plain `http://` is only accepted for loopback and private-LAN hosts (`10.x`, `172.16-31.x`, `192.168.x`); anything else must use `https://`.
- **Production-like/public endpoints**: must use `https://`.

## Local network / ATS configuration

- `ios/Trainingsplan-Info.plist` (merged into the generated Info.plist via the `INFOPLIST_FILE` build setting, kept outside the synchronized `Trainingsplan/` source folder to avoid a duplicate-resource build conflict) sets exactly one narrow key: `NSAppTransportSecurity.NSAllowsLocalNetworking = true`. This allows plain HTTP only to literal IP-address hosts and `.local` mDNS hostnames (needed for the physical-device LAN scenario above); it does **not** set `NSAllowsArbitraryLoads` and does not relax ATS for ordinary internet domains, which still require HTTPS.
- `127.0.0.1`/`localhost` only ever works from the Simulator (it shares the Mac's loopback); a physical device talking to `127.0.0.1` is talking to itself, not your Mac.

## Validation

- After any Swift or Xcode project change, build `ios/Trainingsplan.xcodeproj` using the existing `Trainingsplan` scheme and place DerivedData outside the repository.
- Run `swift test` in `ios/FoodAnalysisKit/` for the networking/validation/persistence-orchestration logic; run relevant app-level checks manually when automated coverage is absent (e.g. no XCTest target exists for the `Trainingsplan` app target itself - keep new business/networking logic in `FoodAnalysisKit` instead, where it's testable).
- Do not commit DerivedData, Xcode user data, generated archives, `.build/`, `.swiftpm/`, or other build output.
