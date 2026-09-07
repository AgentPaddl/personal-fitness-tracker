import XCTest

@testable import FoodAnalysisKit

@MainActor
private final class RefinementStubService: FoodAnalysisServicing {
    var results: [Result<FoodAnalysisResponseDTO.Estimate, Error>]
    private(set) var requests: [FoodAnalysisRefinementRequestDTO] = []

    init(results: [Result<FoodAnalysisResponseDTO.Estimate, Error>]) {
        self.results = results
    }

    func analyze(description: String) async throws -> FoodAnalysisResponseDTO.Estimate {
        fatalError("Initial analysis is not used by these session tests")
    }

    func analyzeImage(
        data: Data, mimeType: String, description: String?
    ) async throws -> FoodAnalysisResponseDTO.Estimate {
        fatalError("Image analysis is not used by these session tests")
    }

    func refine(request: FoodAnalysisRefinementRequestDTO) async throws -> FoodAnalysisResponseDTO.Estimate {
        requests.append(request)
        return try results.removeFirst().get()
    }
}

@MainActor
private final class GatedRefinementService: FoodAnalysisServicing {
    private(set) var requests: [FoodAnalysisRefinementRequestDTO] = []
    private var continuation: CheckedContinuation<FoodAnalysisResponseDTO.Estimate, Error>?

    func analyze(description: String) async throws -> FoodAnalysisResponseDTO.Estimate {
        fatalError("Initial analysis is not used by these session tests")
    }

    func analyzeImage(
        data: Data, mimeType: String, description: String?
    ) async throws -> FoodAnalysisResponseDTO.Estimate {
        fatalError("Image analysis is not used by these session tests")
    }

    func refine(request: FoodAnalysisRefinementRequestDTO) async throws -> FoodAnalysisResponseDTO.Estimate {
        requests.append(request)
        return try await withCheckedThrowingContinuation { continuation in
            self.continuation = continuation
        }
    }

    func succeed(with estimate: FoodAnalysisResponseDTO.Estimate) {
        continuation?.resume(returning: estimate)
        continuation = nil
    }

    func fail(with error: Error) {
        continuation?.resume(throwing: error)
        continuation = nil
    }
}

private func sessionEstimate(name: String = "Reis", calories: Double = 620) -> FoodAnalysisResponseDTO.Estimate {
    FoodAnalysisResponseDTO.Estimate(
        foodName: name,
        calories: calories,
        proteinGrams: 24,
        carbohydrateGrams: 86,
        fatGrams: 18,
        confidence: 0.72,
        warnings: ["Portion unsicher"],
        assumptions: ["Reis gekocht"]
    )
}

@MainActor
final class FoodAnalysisReviewSessionTests: XCTestCase {
    func testRefinementButtonEligibilityForEmptyValidTooLongAndInvalidDraft() {
        let service = RefinementStubService(results: [])
        let session = makeSession(service: service)

        XCTAssertFalse(session.canRefine)

        session.correctionText = "   "
        XCTAssertFalse(session.canRefine)

        session.correctionText = "Es waren 250 g Reis."
        XCTAssertTrue(session.canRefine)

        session.correctionText = String(
            repeating: "x",
            count: FoodAnalysisReviewSession.correctionCharacterLimit + 1
        )
        XCTAssertFalse(session.canRefine)

        session.correctionText = "Gültiger Kontext"
        session.currentDraft.calories = "ungültig"
        XCTAssertFalse(session.canRefine)
    }

    func testRefinementAndConfirmationAreDisabledWhileRequestIsInFlight() async {
        let service = GatedRefinementService()
        let session = makeSession(service: service)
        session.correctionText = "Nur die Hälfte"

        let task = Task { await session.refine() }
        await waitUntil { session.isRefining }

        XCTAssertFalse(session.canRefine)
        XCTAssertFalse(session.canConfirmCurrentDraft)

        service.succeed(with: sessionEstimate(calories: 310))
        await task.value

        XCTAssertTrue(session.canConfirmCurrentDraft)
    }

    func testStableSessionIDAndThreeSuccessfulRoundsThenFourthIsBlocked() async {
        let results = (1...3).map {
            Result<FoodAnalysisResponseDTO.Estimate, Error>.success(
                sessionEstimate(name: "Revision \($0)", calories: Double(620 - $0 * 100))
            )
        }
        let service = RefinementStubService(results: results)
        let session = makeSession(service: service)
        let originalID = session.id

        for expectedIteration in 1...3 {
            session.correctionText = "Korrektur \(expectedIteration)"
            await session.refine()
            XCTAssertEqual(service.requests.last?.refinement.iteration, expectedIteration)
            XCTAssertEqual(session.id, originalID)
        }

        session.correctionText = "Vierte Korrektur"
        await session.refine()

        XCTAssertEqual(service.requests.count, 3)
        XCTAssertEqual(session.successfulRefinementCount, 3)
        XCTAssertNil(session.nextIteration)
        XCTAssertTrue(session.isRefinementLimitReached)
        XCTAssertFalse(session.canRefine)
        XCTAssertTrue(session.canConfirmCurrentDraft)
        XCTAssertNotNil(session.refinementErrorMessage)
    }

    func testFailureConsumesNoRoundAndManualRetryUsesSameIterationWithNewToken() async {
        let service = GatedRefinementService()
        let session = makeSession(service: service)
        session.correctionText = "Nur die Hälfte"

        let first = Task { await session.refine() }
        await waitUntil { session.isRefining }
        let firstToken = session.currentRequestToken
        service.fail(with: FoodAnalysisError.timeout)
        await first.value

        XCTAssertEqual(session.successfulRefinementCount, 0)
        XCTAssertEqual(service.requests[0].refinement.iteration, 1)
        XCTAssertEqual(session.correctionText, "Nur die Hälfte")
        XCTAssertNotNil(session.refinementErrorMessage)

        let retry = Task { await session.refine() }
        await waitUntil { session.isRefining }
        let retryToken = session.currentRequestToken
        XCTAssertNotEqual(retryToken, firstToken)
        service.succeed(with: sessionEstimate(name: "Halbe Portion", calories: 310))
        await retry.value

        XCTAssertEqual(service.requests[1].refinement.iteration, 1)
        XCTAssertEqual(session.successfulRefinementCount, 1)
        XCTAssertEqual(session.correctionText, "")
        XCTAssertNil(session.refinementErrorMessage)
    }

    func testDuplicateRefinementWhileInFlightStartsOnlyOneRequest() async {
        let service = GatedRefinementService()
        let session = makeSession(service: service)
        session.correctionText = "Nur die Hälfte"

        let first = Task { await session.refine() }
        await waitUntil { session.isRefining }
        await session.refine()

        XCTAssertEqual(service.requests.count, 1)
        service.succeed(with: sessionEstimate(calories: 310))
        await first.value
    }

    func testSuccessUpdatesCurrentEstimateOnlyAndPreservesSessionIdentity() async {
        let initial = sessionEstimate()
        let refined = FoodAnalysisResponseDTO.Estimate(
            foodName: "Halbe Portion",
            calories: 310,
            proteinGrams: 12.5,
            carbohydrateGrams: 43.25,
            fatGrams: 9.75,
            confidence: 0.94,
            warnings: ["Neue Warnung"],
            assumptions: ["Neue Annahme"]
        )
        let service = RefinementStubService(results: [.success(refined)])
        let session = makeSession(service: service, initialEstimate: initial)
        let id = session.id
        session.correctionText = "Nur die Hälfte"

        await session.refine()

        XCTAssertEqual(session.id, id)
        XCTAssertEqual(session.initialEstimate, initial)
        XCTAssertEqual(session.currentEstimate, refined)
        XCTAssertEqual(session.currentDraft.id, id)
        XCTAssertEqual(session.currentDraft.name, "Halbe Portion")
        XCTAssertEqual(session.currentDraft.calories, "310")
        XCTAssertEqual(session.currentDraft.protein, "12.5")
        XCTAssertEqual(session.currentDraft.carbs, "43.2")
        XCTAssertEqual(session.currentDraft.fat, "9.8")
        XCTAssertEqual(session.assumptions, refined.assumptions)
        XCTAssertEqual(session.warnings, refined.warnings)
        XCTAssertEqual(session.confidence, refined.confidence)
        XCTAssertEqual(session.correctionText, "")
    }

    func testFailurePreservesEstimateDraftAndCorrection() async {
        let service = RefinementStubService(results: [.failure(FoodAnalysisError.backendUnavailable)])
        let session = makeSession(service: service)
        session.currentDraft.name = "Manuell geändert"
        session.correctionText = "Ohne Sauce"
        let estimateBefore = session.currentEstimate
        let draftBefore = session.currentDraft

        await session.refine()

        XCTAssertEqual(session.currentEstimate, estimateBefore)
        XCTAssertEqual(session.currentDraft, draftBefore)
        XCTAssertEqual(session.correctionText, "Ohne Sauce")
        XCTAssertEqual(session.successfulRefinementCount, 0)
        XCTAssertEqual(session.refinementErrorMessage, FoodAnalysisError.backendUnavailable.userMessage)
    }

    func testCurrentManuallyEditedVisibleValuesAreSent() async {
        let service = RefinementStubService(results: [.success(sessionEstimate(calories: 300))])
        let session = makeSession(service: service)
        session.currentDraft.name = "Manuelle Portion"
        session.currentDraft.calories = "333,5"
        session.currentDraft.protein = "12,5"
        session.currentDraft.carbs = "44"
        session.currentDraft.fat = "7,25"
        session.correctionText = "Bitte neu berechnen"

        await session.refine()

        let sent = service.requests[0].refinement.currentEstimate
        XCTAssertEqual(sent.foodName, "Manuelle Portion")
        XCTAssertEqual(sent.calories, 333.5)
        XCTAssertEqual(sent.proteinGrams, 12.5)
        XCTAssertEqual(sent.carbohydrateGrams, 44)
        XCTAssertEqual(sent.fatGrams, 7.25)
    }

    func testInvalidCorrectionDoesNotStartRequest() async {
        let service = RefinementStubService(results: [])
        let session = makeSession(service: service)

        session.correctionText = "   "
        await session.refine()
        session.correctionText = String(repeating: "x", count: 1001)
        await session.refine()

        XCTAssertTrue(service.requests.isEmpty)
        XCTAssertEqual(session.successfulRefinementCount, 0)
    }

    func testClosedSessionInvalidatesRequestTokenAndIgnoresLateResponse() async {
        let service = GatedRefinementService()
        let session = makeSession(service: service)
        let original = session.currentEstimate
        session.correctionText = "Nur die Hälfte"

        let task = Task { await session.refine() }
        await waitUntil { session.currentRequestToken != nil }
        session.close()
        service.succeed(with: sessionEstimate(name: "Verspätet", calories: 1))
        await task.value

        XCTAssertNil(session.currentRequestToken)
        XCTAssertEqual(session.currentEstimate, original)
        XCTAssertEqual(session.successfulRefinementCount, 0)
    }

    func testPersistenceCoordinatorRemainsSingleCommitAcrossRefinements() async {
        let service = RefinementStubService(results: [.success(sessionEstimate(calories: 310))])
        let session = makeSession(service: service)
        let coordinator = session.persistenceCoordinator
        session.correctionText = "Nur die Hälfte"
        await session.refine()

        var insertions = 0
        let first = coordinator.save(insert: { insertions += 1 }, persist: {}, rollback: {})
        let second = session.persistenceCoordinator.save(insert: { insertions += 1 }, persist: {}, rollback: {})

        XCTAssertTrue(coordinator === session.persistenceCoordinator)
        XCTAssertEqual(first, .saved)
        XCTAssertEqual(second, .skipped)
        XCTAssertEqual(insertions, 1)
    }

    func testConfirmationAfterRefinementUsesFinalVisibleEstimateExactlyOnce() async throws {
        let refined = FoodAnalysisResponseDTO.Estimate(
            foodName: "250 g Reis",
            calories: 325,
            proteinGrams: 6.75,
            carbohydrateGrams: 70.5,
            fatGrams: 1.25,
            confidence: 0.91,
            warnings: [],
            assumptions: ["gekochtes Gewicht"]
        )
        let service = RefinementStubService(results: [.success(refined)])
        let session = makeSession(service: service)
        session.correctionText = "Es waren 250 g Reis"
        await session.refine()
        let finalInput = try XCTUnwrap(session.currentDraft.validated())
        var persistedInputs: [ValidatedFoodEntryInput] = []

        let first = session.persistenceCoordinator.save(
            insert: { persistedInputs.append(finalInput) },
            persist: {},
            rollback: {}
        )
        let second = session.persistenceCoordinator.save(
            insert: { persistedInputs.append(finalInput) },
            persist: {},
            rollback: {}
        )

        XCTAssertEqual(first, .saved)
        XCTAssertEqual(second, .skipped)
        XCTAssertEqual(persistedInputs, [ValidatedFoodEntryInput(
            name: "250 g Reis",
            calories: 325,
            proteinGrams: 6.8,
            carbsGrams: 70.5,
            fatGrams: 1.2
        )])
    }

    func testClosingWithoutConfirmationDisablesActionsAndDoesNotPersist() {
        let service = RefinementStubService(results: [])
        let session = makeSession(service: service)

        session.close()

        XCTAssertFalse(session.canConfirmCurrentDraft)
        XCTAssertFalse(session.canRefine)
        XCTAssertFalse(session.persistenceCoordinator.isSaving)
        XCTAssertFalse(session.persistenceCoordinator.hasCommitted)
    }

    func testManualEditingWithoutRefinementStillProducesConfirmableValues() throws {
        let service = RefinementStubService(results: [])
        let session = makeSession(service: service)
        session.currentDraft.name = "Manuell angepasst"
        session.currentDraft.calories = "450"
        session.currentDraft.protein = "20,5"
        session.currentDraft.carbs = "50"
        session.currentDraft.fat = "12,25"

        XCTAssertTrue(session.canConfirmCurrentDraft)
        let input = try XCTUnwrap(session.currentDraft.validated())
        XCTAssertEqual(input.name, "Manuell angepasst")
        XCTAssertEqual(input.calories, 450)
        XCTAssertEqual(input.proteinGrams, 20.5)
        XCTAssertEqual(input.carbsGrams, 50)
        XCTAssertEqual(input.fatGrams, 12.25)
        XCTAssertTrue(service.requests.isEmpty)
    }

    private func makeSession(
        service: FoodAnalysisServicing,
        initialEstimate: FoodAnalysisResponseDTO.Estimate = sessionEstimate()
    ) -> FoodAnalysisReviewSession {
        FoodAnalysisReviewSession(
            originalDescription: "Eine Schüssel Reis",
            sourceKind: .text,
            initialEstimate: initialEstimate,
            service: service
        )
    }

    private func waitUntil(_ condition: @escaping () -> Bool) async {
        for _ in 0..<100 where !condition() {
            await Task.yield()
        }
        XCTAssertTrue(condition())
    }
}
