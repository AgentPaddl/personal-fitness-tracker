import Combine
import Foundation

/// Drives the text food-analysis flow: calls the backend, tracks
/// loading/error state, and exposes a review draft only after a
/// successful analysis. Nothing is persisted here; persistence happens
/// only after explicit user confirmation in the app's review view.
@MainActor
public final class FoodAnalysisViewModel: ObservableObject {
    @Published public var descriptionText: String = ""
    @Published public private(set) var isAnalyzing = false
    @Published public var errorMessage: String?
    @Published public var reviewDraft: FoodAnalysisReviewDraft?

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

    /// Triggers analysis of the current `descriptionText`. Guards against
    /// duplicate submissions and leaves the typed text untouched so the
    /// user can retry after an error.
    public func analyze() async {
        let trimmed = descriptionText.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !trimmed.isEmpty, !isAnalyzing else { return }

        guard let service else {
            errorMessage = configurationErrorMessage
            return
        }

        isAnalyzing = true
        errorMessage = nil
        defer { isAnalyzing = false }

        do {
            let estimate = try await service.analyze(description: trimmed)
            reviewDraft = FoodAnalysisReviewDraft(estimate: estimate)
        } catch let error as FoodAnalysisError {
            errorMessage = Self.userMessage(for: error)
        } catch {
            errorMessage = Self.userMessage(for: .analysisFailed)
        }
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
        }
    }
}
