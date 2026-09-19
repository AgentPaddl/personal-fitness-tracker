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
    @Published public private(set) var currentOperation: FoodAnalysisOperation?
    @Published public private(set) var lastError: FoodAnalysisError?

    private let service: FoodAnalysisServicing
    private var isClosed = false
    private var refinementTask: Task<FoodAnalysisResponseDTO.Estimate, Error>?
    @Published private var hasUncertainOutcome = false

    private var currentInput: FoodAnalysisOperation.Input? {
        guard let iteration = nextIteration, let estimate = currentDraft.refinementCurrentEstimate(), isCorrectionValid else { return nil }
        return .refinement(FoodAnalysisRefinementRequestDTO(
            foodDescription: originalDescription,
            refinement: FoodAnalysisRefinementDTO(
                correctionText: correctionText.trimmingCharacters(in: .whitespacesAndNewlines),
                currentEstimate: estimate, sourceKind: sourceKind, iteration: iteration
            )
        ))
    }

    public var requiresNewOperationConfirmation: Bool {
        hasUncertainOutcome || lastError?.requiresNewOperationConfirmation == true
    }

    public var canRetryOperation: Bool {
        !isClosed && !isRefining && currentOperation != nil && currentOperation?.input == currentInput
            && lastError?.canRetryOperation == true
    }

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
            && lastError != .pilotNotActivated
            && !isRefinementLimitReached
            && isCorrectionValid
            && currentDraft.refinementCurrentEstimate() != nil
            && (currentOperation == nil || currentOperation?.input != currentInput
                || canRetryOperation || requiresNewOperationConfirmation)
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
    public func refine(confirmNewOperation: Bool = false) async {
        guard !isClosed, !isRefining, lastError != .pilotNotActivated else { return }
        guard nextIteration != nil else {
            refinementErrorMessage = "Maximal drei Überarbeitungen pro Analyse sind möglich."
            return
        }

        let trimmedCorrection = correctionText.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !trimmedCorrection.isEmpty, correctionText.count <= Self.correctionCharacterLimit else {
            refinementErrorMessage = "Die Korrektur muss zwischen 1 und 1000 Zeichen lang sein."
            return
        }
        guard currentDraft.refinementCurrentEstimate() != nil else {
            refinementErrorMessage = "Bitte prüfe die aktuellen Nährwerte vor der erneuten Berechnung."
            return
        }
        guard let input = currentInput else { return }
        do {
            if currentOperation?.input == input && !confirmNewOperation {
                guard canRetryOperation else { return }
            } else {
                guard !requiresNewOperationConfirmation || confirmNewOperation else { return }
                currentOperation = try FoodAnalysisOperation(input: input)
                hasUncertainOutcome = false
            }
        } catch {
            lastError = .analysisFailed
            refinementErrorMessage = FoodAnalysisError.analysisFailed.userMessage
            return
        }
        guard let operation = currentOperation else { return }

        let requestToken = UUID()
        currentRequestToken = requestToken
        isRefining = true
        refinementErrorMessage = nil
        lastError = nil
        let task = Task { try await service.perform(operation: operation) }
        refinementTask = task

        do {
            let estimate = try await withTaskCancellationHandler(operation: {
                try await task.value
            }, onCancel: { task.cancel() })
            guard acceptsResponse(sessionID: id, requestToken: requestToken) else { return }
            guard !Task.isCancelled, !task.isCancelled, operation.input == currentInput else {
                interruptRefinement()
                return
            }
            self.currentEstimate = estimate
            currentDraft = FoodAnalysisReviewDraft(id: id, estimate: estimate)
            successfulRefinementCount += 1
            hasUncertainOutcome = false
            correctionText = ""
            refinementErrorMessage = nil
            currentRequestToken = nil
            isRefining = false
            currentOperation = nil
            refinementTask = nil
        } catch {
            guard acceptsResponse(sessionID: id, requestToken: requestToken) else { return }
            let failure = Task.isCancelled || task.isCancelled
                ? FoodAnalysisError.operationInterrupted : (error as? FoodAnalysisError ?? .analysisFailed)
            lastError = failure
            hasUncertainOutcome = hasUncertainOutcome || failure.requiresNewOperationConfirmation
            refinementErrorMessage = failure == .pilotNotActivated && hasUncertainOutcome
                ? failure.userMessage + " " + FoodAnalysisError.pilotUnavailable.userMessage : failure.userMessage
            currentRequestToken = nil
            isRefining = false
            refinementTask = nil
        }
    }

    public func retryOperation() async {
        guard canRetryOperation else { return }
        await refine()
    }

    public func interruptRefinement() {
        guard isRefining else { return }
        currentRequestToken = nil
        refinementTask?.cancel()
        refinementTask = nil
        isRefining = false
        lastError = .operationInterrupted
        hasUncertainOutcome = true
        refinementErrorMessage = FoodAnalysisError.operationInterrupted.userMessage
    }

    /// Invalidates any in-flight response when the review is dismissed or
    /// replaced. The underlying transport need not support cancellation.
    public func close() {
        interruptRefinement()
        isClosed = true
        currentRequestToken = nil
        isRefining = false
        currentOperation = nil
    }

    private func acceptsResponse(sessionID: UUID, requestToken: UUID) -> Bool {
        !isClosed && id == sessionID && currentRequestToken == requestToken
    }
}
