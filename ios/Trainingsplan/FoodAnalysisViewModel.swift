import Combine
import Foundation
import FoodAnalysisKit

/// Drives the text food-analysis flow: calls the backend, tracks
/// loading/error state, and exposes a review draft only after a
/// successful analysis. Nothing is persisted here; persistence happens
/// only after explicit user confirmation in `FoodAnalysisReviewView`.
@MainActor
final class FoodAnalysisViewModel: ObservableObject {
    @Published var descriptionText: String = ""
    @Published private(set) var isAnalyzing = false
    @Published var errorMessage: String?
    @Published var reviewDraft: FoodAnalysisReviewDraft?

    private let service: FoodAnalysisServicing

    init(service: FoodAnalysisServicing = FoodAnalysisService(baseURL: APIConfiguration.backendBaseURL)) {
        self.service = service
    }

    /// Triggers analysis of the current `descriptionText`. Guards against
    /// duplicate submissions and leaves the typed text untouched so the
    /// user can retry after an error.
    func analyze() async {
        let trimmed = descriptionText.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !trimmed.isEmpty, !isAnalyzing else { return }

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

    static func userMessage(for error: FoodAnalysisError) -> String {
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
}
