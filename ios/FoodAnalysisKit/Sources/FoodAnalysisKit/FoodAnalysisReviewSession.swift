import Combine
import Foundation

/// In-memory state for one review and its bounded sequence of refinements.
/// No value owned by this object is persisted automatically.
@MainActor
public final class FoodAnalysisReviewSession: ObservableObject, Identifiable {
    public static let maximumSuccessfulRefinements = 3
    public static let correctionCharacterLimit = 1_000

    public let id: UUID
    public let originalDescription: String?
    public let sourceKind: FoodAnalysisSourceKind
    public let initialEstimate: FoodAnalysisResponseDTO.Estimate
    public let persistenceCoordinator: FoodEntryPersistenceCoordinator

    @Published public var currentDraft: FoodAnalysisReviewDraft
    @Published public var correctionText = ""
    @Published public private(set) var successfulRefinementCount = 0
    @Published public private(set) var isRefining = false
    @Published public private(set) var refinementErrorMessage: String?
    @Published public private(set) var currentRequestToken: UUID?
    @Published public private(set) var currentEstimate: FoodAnalysisResponseDTO.Estimate

    private let service: FoodAnalysisServicing
    private var isClosed = false

    public init(
        id: UUID = UUID(),
        originalDescription: String?,
        sourceKind: FoodAnalysisSourceKind,
        initialEstimate: FoodAnalysisResponseDTO.Estimate,
        service: FoodAnalysisServicing,
        persistenceCoordinator: FoodEntryPersistenceCoordinator = FoodEntryPersistenceCoordinator()
    ) {
        self.id = id
        self.originalDescription = originalDescription
        self.sourceKind = sourceKind
        self.initialEstimate = initialEstimate
        self.service = service
        self.persistenceCoordinator = persistenceCoordinator
        self.currentEstimate = initialEstimate
        self.currentDraft = FoodAnalysisReviewDraft(id: id, estimate: initialEstimate)
    }

    public var assumptions: [String] { currentEstimate.assumptions }
    public var warnings: [String] { currentEstimate.warnings }
    public var confidence: Double { currentEstimate.confidence }
    public var isRefinementLimitReached: Bool {
        successfulRefinementCount >= Self.maximumSuccessfulRefinements
    }
    public var isCorrectionValid: Bool {
        let trimmedCorrection = correctionText.trimmingCharacters(in: .whitespacesAndNewlines)
        return !trimmedCorrection.isEmpty && correctionText.count <= Self.correctionCharacterLimit
    }
    public var canRefine: Bool {
        !isClosed
            && !isRefining
            && !isRefinementLimitReached
            && isCorrectionValid
            && currentDraft.refinementCurrentEstimate() != nil
    }
    public var canConfirmCurrentDraft: Bool {
        !isClosed && !isRefining && currentDraft.validated() != nil
    }
    public var nextIteration: Int? {
        guard successfulRefinementCount < Self.maximumSuccessfulRefinements else { return nil }
        return successfulRefinementCount + 1
    }

    /// Performs one explicit refinement. Invalid input, an in-flight call,
    /// a closed session, or an exhausted three-round limit is a local no-op.
    public func refine() async {
        guard !isClosed, !isRefining else { return }
        guard let iteration = nextIteration else {
            refinementErrorMessage = "Maximal drei Überarbeitungen pro Analyse sind möglich."
            return
        }

        let trimmedCorrection = correctionText.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !trimmedCorrection.isEmpty, correctionText.count <= Self.correctionCharacterLimit else {
            refinementErrorMessage = "Die Korrektur muss zwischen 1 und 1000 Zeichen lang sein."
            return
        }
        guard let currentEstimate = currentDraft.refinementCurrentEstimate() else {
            refinementErrorMessage = "Bitte prüfe die aktuellen Nährwerte vor der erneuten Berechnung."
            return
        }

        let requestToken = UUID()
        currentRequestToken = requestToken
        isRefining = true
        refinementErrorMessage = nil

        let request = FoodAnalysisRefinementRequestDTO(
            foodDescription: originalDescription,
            refinement: FoodAnalysisRefinementDTO(
                correctionText: trimmedCorrection,
                currentEstimate: currentEstimate,
                sourceKind: sourceKind,
                iteration: iteration
            )
        )

        do {
            let estimate = try await service.refine(request: request)
            guard acceptsResponse(sessionID: id, requestToken: requestToken) else { return }
            self.currentEstimate = estimate
            currentDraft = FoodAnalysisReviewDraft(id: id, estimate: estimate)
            successfulRefinementCount += 1
            correctionText = ""
            refinementErrorMessage = nil
            currentRequestToken = nil
            isRefining = false
        } catch let error as FoodAnalysisError {
            guard acceptsResponse(sessionID: id, requestToken: requestToken) else { return }
            refinementErrorMessage = error.userMessage
            currentRequestToken = nil
            isRefining = false
        } catch {
            guard acceptsResponse(sessionID: id, requestToken: requestToken) else { return }
            refinementErrorMessage = FoodAnalysisError.analysisFailed.userMessage
            currentRequestToken = nil
            isRefining = false
        }
    }

    /// Invalidates any in-flight response when the review is dismissed or
    /// replaced. The underlying transport need not support cancellation.
    public func close() {
        isClosed = true
        currentRequestToken = nil
        isRefining = false
    }

    private func acceptsResponse(sessionID: UUID, requestToken: UUID) -> Bool {
        !isClosed && id == sessionID && currentRequestToken == requestToken
    }
}
