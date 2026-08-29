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

## Food analysis (text + image) flow

- `NutritionView` hosts a "KI-Analyse (Text & Foto)" section where the user types a natural-language food description and/or picks a photo, then triggers analysis via `FoodAnalysisKit.FoodAnalysisViewModel`, which calls `FoodAnalysisService` against the backend's `POST /api/food-analysis`. Both may be sent together; the backend/gateway use both when present.
- A successful analysis presents `FoodAnalysisReviewView` (app target) as a sheet with editable name/calories/protein/carbs/fat, pre-filled from the estimate, regardless of whether the estimate came from text, an image, or both. Confidence/warnings are shown as non-persisted review metadata only.
- Confirmation is coordinated by `FoodAnalysisKit.FoodEntryPersistenceCoordinator`: it inserts then saves, rolls back (deletes) the inserted object if the save throws, and guarantees at most one committed save per presented review (a rapid duplicate tap on "Übernehmen" is a no-op once saving/committed). A failed save shows an inline error in the sheet (never console-only), never dismisses, and allows retry. Cancelling/dismissing the sheet never touches `modelContext`. There is one review/persistence flow shared by text and image analysis — never a second one.

### Image input

- Selection: `PhotosPicker` (library) or the camera (`CameraCaptureView`, a `UIImagePickerController` bridge with `sourceType = .camera`) in `NutritionView`. Both feed the exact same `FoodAnalysisViewModel.setPickedImage(rawData:)` → `FoodImagePreprocessor` → upload → review → persistence pipeline; there is no parallel path for captured photos.
- Camera permission (`NSCameraUsageDescription` in `ios/Trainingsplan-Info.plist`) is requested only in direct response to the user tapping "Foto aufnehmen" (`AVCaptureDevice.requestAccess(for:.video)`), never proactively/on view load. `FoodAnalysisKit.CameraCaptureAvailability` (pure, no AVFoundation/UIKit dependency, unit-tested) decides whether to present the camera immediately, request permission first, or show a friendly blocked message, from an already-abstracted `CameraAuthorizationStatus`/hardware-availability input; the app layer maps `AVAuthorizationStatus` onto that enum in one place (`NutritionView`'s `CameraAuthorizationStatus` extension). The "Foto aufnehmen" button is hidden entirely when `UIImagePickerController.isSourceTypeAvailable(.camera)` is false (e.g. the Simulator), so it never attempts to present an unavailable camera.
- Captured photos are never saved to the Photos library (`UIImagePickerController`'s default, non-saving behavior is used as-is - no `UIImageWriteToSavedPhotosAlbum` call) and are never persisted beyond the same transient in-memory `selectedImage` state used for picked photos.
- Preprocessing (`FoodAnalysisKit.FoodImagePreprocessor`, pure ImageIO, no UIKit so it is testable via `swift test`): uses ImageIO's thumbnail API (`kCGImageSourceCreateThumbnailWithTransform`) to bake in EXIF orientation (output is always upright, regardless of source orientation) while resizing to a max 1280px longest side, then re-encodes as JPEG. If the first attempt (quality 0.7) exceeds the 3 MiB upload limit, quality is deterministically reduced (0.7 → 0.5 → 0.3 → 0.15) and, if still too large, the target dimension is deterministically halved and the quality sequence retried - a bounded, finite search, never an open-ended retry loop. If no combination fits, preprocessing fails explicitly (`.sizeLimitExceeded`) rather than uploading an oversized image. Re-encoding never copies the source image's properties/metadata dictionary to the output, which strips EXIF/GPS and other source metadata as a side effect — this is not optional and cannot be bypassed. Preprocessing never silently falls back to the original, full-resolution/unoriented image on any failure.
- Upload: `FoodAnalysisService.analyzeImage` sends `multipart/form-data` (fields: `image`, optional `food_description`) to the same `POST /api/food-analysis` endpoint used for text.
- UI states: image preview + "Entfernen" once selected (hides the picker), a photo-loading spinner while the picker item is being read, the existing "Analysiere…" spinner while the request is in flight, and the existing inline error text. The "Analysieren" button is enabled only when (text and/or image is present) AND no photo is still being loaded (`isLoadingPickedPhoto`) - this prevents submitting text-only while an intended photo hasn't finished loading yet. Duplicate submission while analyzing is already prevented by the existing `isAnalyzing` guard in the view model. Both the typed text and the selected image are retained after a failure so the user can retry without redoing input; both are cleared only after a successful confirmed save.
- Never send photo-library asset identifiers, filenames, or device metadata — only the preprocessed JPEG bytes and MIME type ever leave the device.
- Review values are validated (`FoodAnalysisReviewDraft.validated()`) before save: blank name, unparsable/negative/non-finite numbers, and out-of-bounds values (matching the backend's own 0...10000 kcal / 0...1000 g bounds) are all rejected. Calories are parsed as a decimal (comma or dot) and rounded to the nearest whole number.

## Backend base URL configuration (fail-closed)

- Configured via `FoodAnalysisKit.APIConfiguration.resolveBackendBaseURL()`, which returns a `Result` and never silently substitutes a fallback host for an explicitly-set but invalid/insecure/malformed value.
- **Simulator**: leave `API_BASE_URL` unset to use the recognized local-development default `http://127.0.0.1:7071/api` (the Simulator shares the Mac's network namespace, so loopback reaches `func start` directly). This default only compiles in for Simulator builds (`#if targetEnvironment(simulator)`); a device build with no override fails closed with a clear configuration error instead of silently trying `127.0.0.1` (which would just be the device itself).
- **Physical device (Debug builds only)**: set `API_BASE_URL` explicitly on the app's Xcode scheme (Product > Scheme > Edit Scheme... > Run > Arguments > Environment Variables) to the Mac's reachable LAN address, e.g. `http://192.168.1.23:7071`. Plain `http://` is only accepted for loopback and private-LAN hosts (`10.x`, `172.16-31.x`, `192.168.x`) **in Debug builds** (`#if DEBUG`); anything else, or any Release build regardless of host, must use `https://`.
- **Production/Release builds**: must use `https://` unconditionally - the LAN-IP HTTP development exception is compiled out of Release builds entirely (`allowsInsecureLocalDevelopmentHost` is `false` outside `#if DEBUG`), so a leftover development URL can never silently reach production.
- **Path**: only no path, `/`, `/api`, or `/api/` are accepted (all normalized to `/api`); any other path (e.g. `/staging`), a query string, or a fragment is rejected outright rather than silently appended to or truncated.
- **Authentication token**: the iOS app does not send a static backend secret. It uses a short-lived Microsoft Entra ID access token via `AccessTokenProviding` and sends it as `Authorization: Bearer <token>` in `FoodAnalysisService`. The real implementation is the app-layer `EntraAuthService` placeholder (`ios/Trainingsplan/EntraAuthService.swift`), which reads non-secret public config values (tenant ID, client ID, scope, redirect URI) from Info.plist. Until the real MSAL integration is configured and live, the app intentionally supplies `nil`/no provider and sends no `Authorization` header, preserving the existing local-development behavior exactly. A production build must not contain a client secret or a static backend API key; it relies on Entra ID + Azure App Service Authentication (Easy Auth) instead.

## Physical-device requirements (three distinct things)

Getting a physical iPhone to reach the local backend requires all three of the following; they are independent and easy to conflate:

1. **ATS local-network allowance** (`ios/Trainingsplan-Info.plist`, merged into the generated Info.plist via the `INFOPLIST_FILE` build setting, kept outside the synchronized `Trainingsplan/` source folder to avoid a duplicate-resource build conflict): `NSAppTransportSecurity.NSAllowsLocalNetworking = true`. This is what lets iOS's App Transport Security allow plain HTTP to literal IP-address hosts and `.local` mDNS hostnames at all. It does **not** set `NSAllowsArbitraryLoads` and does not relax ATS for ordinary internet domains, which still require HTTPS.
2. **iOS Local Network privacy permission**: a separate, user-facing OS permission (distinct from ATS) required for the app to discover/connect to devices on the local network at all; iOS shows a one-time system prompt the first time the app attempts this. Declared via the top-level `NSLocalNetworkUsageDescription` key in `ios/Trainingsplan-Info.plist`, with a concise German description that this is only used to reach the development backend on the user's Mac. Without this key, a physical-device connection to a LAN IP fails/is blocked regardless of the ATS setting above.
3. **`API_BASE_URL`** pointing to the Mac's actual reachable LAN address (see previous section) - `127.0.0.1`/`localhost` only ever works from the Simulator (it shares the Mac's loopback); a physical device talking to `127.0.0.1` is talking to itself, not your Mac.

All three are development-only conveniences; production/non-local endpoints remain HTTPS-only and are unaffected by any of them.

## Timeout hierarchy and long-running UX

- `FoodAnalysisService.timeoutInterval` defaults to 110s - above the recommended production backend (100s) and gateway (90s) timeouts (see `backend/AGENTS.md`'s table), so this outermost layer never aborts before an inner layer's own normalized timeout error can return.
- While `isAnalyzing`, `NutritionView` shows the existing spinner with "Analysiere…"; after 5 seconds it switches to a neutral "Das Essen wird analysiert …" without any fake percentage progress, since real Copilot calls typically take tens of seconds.
- No request cancellation is implemented (the task explicitly allows omitting it if it can't be added safely without inconsistent state; a same-request duplicate-submission guard already exists via `isAnalyzing` and is preserved).
- On a retry-eligible failure (`FoodAnalysisError.isRetryEligible`: connectivity, backend-unavailable, rate-limited, timeout, or generic analysis failure - not input/configuration problems), an explicit "Erneut versuchen" button appears next to the error text and re-calls `analyze()`; there is no automatic/silent retry of an AI request.

## Validation

- After any Swift or Xcode project change, build `ios/Trainingsplan.xcodeproj` using the existing `Trainingsplan` scheme and place DerivedData outside the repository.
- Run `swift test` in `ios/FoodAnalysisKit/` for the networking/validation/persistence-orchestration logic; run relevant app-level checks manually when automated coverage is absent (e.g. no XCTest target exists for the `Trainingsplan` app target itself - keep new business/networking logic in `FoodAnalysisKit` instead, where it's testable).
- Do not commit DerivedData, Xcode user data, generated archives, `.build/`, `.swiftpm/`, or other build output.

### Manual Simulator smoke (text + image)

1. Start the gateway with a vision-capable image route configured, e.g. `COPILOT_MODEL_ROUTES_JSON='{"food_text_v1": "gpt-5-mini", "food_image_v1": "gpt-5-mini"}'` (see `ai-gateway/README.md`).
2. Start the backend with `APP_ENV=development` pointed at the gateway (see `backend/AGENTS.md`).
3. Run the app in the Simulator with `API_BASE_URL` unset (uses the local default) or explicitly set.
4. Text flow: type a description in "KI-Analyse (Text & Foto)", tap "Analysieren", review, confirm.
5. Image flow: tap "Foto auswählen", pick a photo from the Simulator's Photos library, wait for the preview, tap "Analysieren", review, confirm.
6. Confirm exactly one `FoodEntry` is created per confirmed review in both cases, and that cancelling/dismissing the review sheet persists nothing.
