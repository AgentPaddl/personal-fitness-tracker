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
    @Published public var reviewDraft: FoodAnalysisReviewDraft?
    /// The preprocessed (resized/JPEG-compressed/metadata-stripped) image
    /// ready for upload, if the user picked one. Held only in memory for
    /// the duration of this flow; never persisted.
    @Published public private(set) var selectedImage: PreprocessedFoodImage?

    private let service: FoodAnalysisServicing?
    private let configurationErrorMessage: String?

    /// Real usage: resolves the backend base URL from the environment/
    /// build target. If resolution fails (fail-closed configuration), no
    /// network call is ever attempted; `analyze()` immediately surfaces
    /// `errorMessage` instead.
    public convenience init() {
        switch APIConfiguration.resolveBackendBaseURL() {
        case .success(let url):
            self.init(service: FoodAnalysisService(baseURL: url))
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
    public func analyze() async {
        let trimmed = descriptionText.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !trimmed.isEmpty || selectedImage != nil, !isAnalyzing else { return }

        guard let service else {
            errorMessage = configurationErrorMessage
            return
        }

        isAnalyzing = true
        errorMessage = nil
        defer { isAnalyzing = false }

        do {
            let estimate: FoodAnalysisResponseDTO.Estimate
            if let selectedImage {
                estimate = try await service.analyzeImage(
                    data: selectedImage.data,
                    mimeType: selectedImage.mimeType,
                    description: trimmed.isEmpty ? nil : trimmed
                )
            } else {
                estimate = try await service.analyze(description: trimmed)
            }
            reviewDraft = FoodAnalysisReviewDraft(estimate: estimate)
        } catch let error as FoodAnalysisError {
            errorMessage = Self.userMessage(for: error)
        } catch {
            errorMessage = Self.userMessage(for: .analysisFailed)
        }
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

    public static func userMessage(for error: FoodAnalysisError) -> String {
        switch error {
        case .noConnection:
            return "Keine Internetverbindung. Bitte überprüfe deine Verbindung und versuche es erneut."
        case .timeout:
            return "Die Analyse hat zu lange gedauert. Bitte versuche es erneut."
        case .backendUnavailable:
            return "Der Analysedienst ist derzeit nicht erreichbar. Bitte versuche es später erneut."
        case .rateLimited:
            return "Zu viele Anfragen. Bitte warte einen Moment und versuche es erneut."
        case .unauthorized:
            return "Die Analyse ist momentan nicht verfügbar."
        case .invalidResponse:
            return "Die Antwort konnte nicht verarbeitet werden. Bitte versuche es erneut."
        case .analysisFailed:
            return "Die Analyse ist fehlgeschlagen. Bitte versuche es erneut."
        case .imageProcessingFailed:
            return "Das Foto konnte nicht verarbeitet werden. Bitte wähle ein anderes Foto."
        case .imageMissingOrEmpty:
            return "Es wurde kein gültiges Foto übermittelt. Bitte wähle ein Foto aus."
        case .unsupportedImageType:
            return "Dieses Bildformat wird nicht unterstützt. Bitte verwende ein JPEG- oder PNG-Foto."
        case .imageTooLarge:
            return "Das Foto ist zu groß. Bitte wähle ein kleineres Foto."
        }
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
