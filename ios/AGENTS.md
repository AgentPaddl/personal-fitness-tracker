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

- `NutritionView` hosts a "KI-Analyse (Text)" section where the user types a natural-language food description and triggers analysis via `FoodAnalysisViewModel` (`FoodAnalysisViewModel.swift`), which calls `FoodAnalysisKit`'s `FoodAnalysisService` against the backend's `POST /api/food-analysis`.
- A successful analysis presents `FoodAnalysisReviewView` as a sheet with editable name/calories/protein/carbs/fat, pre-filled from the estimate. Confidence/warnings are shown as non-persisted review metadata only.
- SwiftData writes (`FoodEntry` insert + save) happen only when the user taps "Übernehmen"; cancelling/dismissing the sheet never touches `modelContext`.
- Image analysis is not implemented; this phase is text-only.
- Backend base URL: `FoodAnalysisKit.APIConfiguration.backendBaseURL`, overridable via the `API_BASE_URL` environment variable on the app's Xcode scheme (Run > Arguments > Environment Variables) - needed for a physical device, which cannot reach `localhost`. Defaults to `http://127.0.0.1:7071/api` (local Azure Functions Core Tools).

## Validation

- After any Swift or Xcode project change, build `ios/Trainingsplan.xcodeproj` using the existing `Trainingsplan` scheme and place DerivedData outside the repository.
- Run `swift test` in `ios/FoodAnalysisKit/` for the networking/validation logic; run relevant app-level checks manually when automated coverage is absent (e.g. no XCTest target exists for the `Trainingsplan` app target itself).
- Do not commit DerivedData, Xcode user data, generated archives, `.build/`, `.swiftpm/`, or other build output.
