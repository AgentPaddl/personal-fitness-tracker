import Combine
import Foundation

/// Drives the text/image food-analysis flow: calls the backend, tracks
/// loading/error state, and exposes a review draft only after a
/// successful analysis. Nothing is persisted here; persistence happens
/// only after explicit user confirmation in the app's review view.
@MainActor
public final class FoodAnalysisViewModel: ObservableObject {
    @Published public var descriptionText: String = ""
    @Published public private(set) var isAnalyzing = false
    @Published public var errorMessage: String?
    /// The specific error behind `errorMessage`, if any - lets the UI
    /// decide whether an explicit "Erneut versuchen" action makes sense
    /// (`FoodAnalysisError.isRetryEligible`) without re-deriving it from
    /// the display string. `nil` whenever `errorMessage` came from a
    /// configuration failure rather than a request failure.
    @Published public private(set) var lastError: FoodAnalysisError?
    @Published public var reviewDraft: FoodAnalysisReviewDraft?
    @Published public private(set) var reviewSession: FoodAnalysisReviewSession?
    /// The preprocessed (resized/JPEG-compressed/metadata-stripped) image
    /// ready for upload, if the user picked one. Held only in memory for
    /// the duration of this flow; never persisted.
    @Published public private(set) var selectedImage: PreprocessedFoodImage?
    @Published public private(set) var currentOperation: FoodAnalysisOperation?
    @Published public private(set) var currentRequestToken: UUID?

    private let service: FoodAnalysisServicing?
    private let configurationErrorMessage: String?
    private var analysisTask: Task<FoodAnalysisResponseDTO.Estimate, Error>?
    private var operationCompleted = false
    @Published private var hasUncertainOutcome = false

    private var currentInput: FoodAnalysisOperation.Input {
        let trimmed = descriptionText.trimmingCharacters(in: .whitespacesAndNewlines)
        if let selectedImage {
            return .image(data: selectedImage.data, mimeType: selectedImage.mimeType,
                          description: trimmed.isEmpty ? nil : trimmed)
        }
        return .text(trimmed)
    }

    public var requiresNewOperationConfirmation: Bool {
        hasUncertainOutcome || lastError?.requiresNewOperationConfirmation == true
            || (operationCompleted && currentOperation?.input == currentInput)
    }

    public var canRetryOperation: Bool {
        !isAnalyzing && !operationCompleted && currentOperation?.input == currentInput
            && lastError?.canRetryOperation == true
    }

    public var canAnalyze: Bool {
        !isAnalyzing && (!descriptionText.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty || selectedImage != nil)
            && (currentOperation == nil || currentOperation?.input != currentInput
                || canRetryOperation || requiresNewOperationConfirmation)
    }

    /// Real usage: resolves the backend base URL from the environment/
    /// build target. If resolution fails (fail-closed configuration), no
    /// network call is ever attempted; `analyze()` immediately surfaces
    /// `errorMessage` instead. `tokenProvider` is `nil` unless the app
    /// layer supplies a configured `AccessTokenProviding` (Entra ID) -
    /// preserves today's unauthenticated local-development behavior
    /// exactly when it is not configured.
    public convenience init(tokenProvider: AccessTokenProviding? = nil) {
        switch APIConfiguration.resolveBackendBaseURL() {
        case .success(let url):
            self.init(service: FoodAnalysisService(baseURL: url, tokenProvider: tokenProvider))
        case .failure(let error):
            self.init(configurationError: error)
        }
    }

    /// Dependency-injected for tests/previews.
    public init(service: FoodAnalysisServicing) {
        self.service = service
        self.configurationErrorMessage = nil
    }

    private init(configurationError: APIConfigurationError) {
        self.service = nil
        self.configurationErrorMessage = Self.userMessage(forConfigurationError: configurationError)
    }

    /// Triggers analysis of the current `descriptionText`/`selectedImage`.
    /// Guards against duplicate submissions. Leaves the typed text and
    /// selected image untouched so the user can retry after an error.
    /// If both text and an image are present, both are sent together.
    public func analyze(confirmNewOperation: Bool = false) async {
        let trimmed = descriptionText.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !trimmed.isEmpty || selectedImage != nil, !isAnalyzing else { return }

        guard let service else {
            errorMessage = configurationErrorMessage
            return
        }

        do {
            if currentOperation?.input == currentInput && !confirmNewOperation {
                guard canRetryOperation else { return }
            } else {
                guard !requiresNewOperationConfirmation || confirmNewOperation else { return }
                currentOperation = try FoodAnalysisOperation(input: currentInput)
                operationCompleted = false
                hasUncertainOutcome = false
            }
        } catch {
            lastError = .analysisFailed
            errorMessage = FoodAnalysisError.analysisFailed.userMessage
            return
        }
        guard let operation = currentOperation else { return }
        let requestToken = UUID()
        currentRequestToken = requestToken
        isAnalyzing = true
        errorMessage = nil
        lastError = nil
        let task = Task { try await service.perform(operation: operation) }
        analysisTask = task

        do {
            let estimate = try await withTaskCancellationHandler(operation: {
                try await task.value
            }, onCancel: { task.cancel() })
            guard currentRequestToken == requestToken else { return }
            guard !Task.isCancelled, !task.isCancelled, operation.input == currentInput else {
                interruptAnalysis()
                return
            }
            let sourceKind: FoodAnalysisSourceKind
            let originalDescription: String?
            switch operation.input {
            case .text(let description):
                sourceKind = .text
                originalDescription = description
            case .image(_, _, let description):
                sourceKind = description == nil ? .image : .textAndImage
                originalDescription = description
            case .refinement:
                return
            }
            operationCompleted = true
            hasUncertainOutcome = false
            isAnalyzing = false
            currentRequestToken = nil
            analysisTask = nil
            reviewSession?.close()
            let session = FoodAnalysisReviewSession(
                originalDescription: originalDescription,
                sourceKind: sourceKind,
                initialEstimate: estimate,
                service: service
            )
            reviewSession = session
            // Kept as the stable sheet presentation item for the existing UI.
            reviewDraft = session.currentDraft
        } catch {
            guard currentRequestToken == requestToken else { return }
            let failure = Task.isCancelled || task.isCancelled
                ? FoodAnalysisError.operationInterrupted : (error as? FoodAnalysisError ?? .analysisFailed)
            errorMessage = failure.userMessage
            lastError = failure
            hasUncertainOutcome = hasUncertainOutcome || failure.requiresNewOperationConfirmation
            currentRequestToken = nil
            isAnalyzing = false
            analysisTask = nil
        }
    }

    public func retryOperation() async {
        guard canRetryOperation else { return }
        await analyze()
    }

    public func interruptAnalysis() {
        guard isAnalyzing else { return }
        currentRequestToken = nil
        analysisTask?.cancel()
        analysisTask = nil
        isAnalyzing = false
        lastError = .operationInterrupted
        hasUncertainOutcome = true
        errorMessage = FoodAnalysisError.operationInterrupted.userMessage
    }

    public func clearAfterSave() {
        closeReviewSession()
        currentOperation = nil
        operationCompleted = false
        hasUncertainOutcome = false
        descriptionText = ""
        selectedImage = nil
        lastError = nil
        errorMessage = nil
    }

    /// Preprocesses and stores a freshly picked photo (resize/JPEG-compress,
    /// strip metadata). On failure, `errorMessage` is set and no image is
    /// retained. Replaces any previously selected image.
    public func setPickedImage(rawData: Data) {
        switch FoodImagePreprocessor.preprocess(imageData: rawData) {
        case .success(let preprocessed):
            selectedImage = preprocessed
            errorMessage = nil
        case .failure:
            errorMessage = Self.userMessage(for: .imageProcessingFailed)
        }
    }

    public func removeSelectedImage() {
        selectedImage = nil
    }

    public func closeReviewSession() {
        reviewSession?.close()
        if reviewSession?.requiresNewOperationConfirmation == true {
            hasUncertainOutcome = true
            lastError = .operationInterrupted
            errorMessage = FoodAnalysisError.operationInterrupted.userMessage
        }
        reviewSession = nil
        reviewDraft = nil
    }

    public static func userMessage(for error: FoodAnalysisError) -> String {
        error.userMessage
    }

    public static func userMessage(forConfigurationError error: APIConfigurationError) -> String {
        switch error {
        case .missingConfiguration:
            return "Die Backend-Adresse ist nicht konfiguriert. Bitte API_BASE_URL im Xcode-Schema setzen."
        case .invalidURL:
            return "Die konfigurierte Backend-Adresse ist ungültig."
        case .unsupportedScheme:
            return "Die konfigurierte Backend-Adresse verwendet ein nicht unterstütztes Protokoll."
        case .insecureSchemeForNonLocalHost:
            return "Unverschlüsseltes HTTP ist nur für die lokale Entwicklung erlaubt. Bitte HTTPS verwenden."
        case .unsupportedPath:
            return "Die konfigurierte Backend-Adresse enthält einen nicht unterstützten Pfad."
        }
    }

    public static func userMessage(for reason: CameraCaptureUnavailableReason) -> String {
        switch reason {
        case .hardwareUnavailable:
            return "Auf diesem Gerät ist keine Kamera verfügbar."
        case .permissionDenied:
            return "Kein Kamerazugriff. Bitte erlaube den Zugriff in den Einstellungen, um ein Foto aufzunehmen."
        case .permissionRestricted:
            return "Der Kamerazugriff ist auf diesem Gerät eingeschränkt."
        }
    }
}
