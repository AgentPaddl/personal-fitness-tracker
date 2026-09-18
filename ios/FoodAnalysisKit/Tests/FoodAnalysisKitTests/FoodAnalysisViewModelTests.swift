import CoreGraphics
import ImageIO
import UniformTypeIdentifiers
import XCTest

@testable import FoodAnalysisKit

@MainActor
private final class StubService: FoodAnalysisServicing {
    private(set) var operations: [FoodAnalysisOperation] = []

    func perform(operation: FoodAnalysisOperation) async throws -> FoodAnalysisResponseDTO.Estimate {
        operations.append(operation)
        switch operation.input {
        case .text(let description): return try await analyze(description: description)
        case .image(let data, let mimeType, let description):
            return try await analyzeImage(data: data, mimeType: mimeType, description: description)
        case .refinement(let request): return try await refine(request: request)
        }
    }

    var result: Result<FoodAnalysisResponseDTO.Estimate, Error>
    private(set) var callCount = 0
    private(set) var lastImageMimeType: String?
    private(set) var lastImageDescription: String?

    init(result: Result<FoodAnalysisResponseDTO.Estimate, Error>) {
        self.result = result
    }

    func analyze(description: String) async throws -> FoodAnalysisResponseDTO.Estimate {
        callCount += 1
        return try result.get()
    }

    func refine(request: FoodAnalysisRefinementRequestDTO) async throws -> FoodAnalysisResponseDTO.Estimate {
        callCount += 1
        return try result.get()
    }

    func analyzeImage(
        data: Data, mimeType: String, description: String?
    ) async throws -> FoodAnalysisResponseDTO.Estimate {
        callCount += 1
        lastImageMimeType = mimeType
        lastImageDescription = description
        return try result.get()
    }
}

/// Lets a test control exactly when the in-flight network call completes,
/// to deterministically exercise the duplicate-submission guard. Isolated
/// to `MainActor` (like its only caller) so its mutable state safely
/// satisfies the `FoodAnalysisServicing: Sendable` requirement.
@MainActor
private final class GatedService: FoodAnalysisServicing {
    private(set) var operations: [FoodAnalysisOperation] = []

    func perform(operation: FoodAnalysisOperation) async throws -> FoodAnalysisResponseDTO.Estimate {
        operations.append(operation)
        return try await analyze(description: "")
    }

    private(set) var callCount = 0
    private var continuations: [CheckedContinuation<FoodAnalysisResponseDTO.Estimate, Error>] = []
    var pendingCount: Int { continuations.count }

    func analyze(description: String) async throws -> FoodAnalysisResponseDTO.Estimate {
        callCount += 1
        return try await withCheckedThrowingContinuation { continuation in
            continuations.append(continuation)
        }
    }

    func refine(request: FoodAnalysisRefinementRequestDTO) async throws -> FoodAnalysisResponseDTO.Estimate {
        callCount += 1
        return try await withCheckedThrowingContinuation { continuation in
            continuations.append(continuation)
        }
    }

    func analyzeImage(
        data: Data, mimeType: String, description: String?
    ) async throws -> FoodAnalysisResponseDTO.Estimate {
        callCount += 1
        return try await withCheckedThrowingContinuation { continuation in
            continuations.append(continuation)
        }
    }

    func resume(with estimate: FoodAnalysisResponseDTO.Estimate) {
        guard !continuations.isEmpty else { return }
        continuations.removeFirst().resume(returning: estimate)
    }
}

@MainActor
private final class ReplacementService: FoodAnalysisServicing {
    func perform(operation: FoodAnalysisOperation) async throws -> FoodAnalysisResponseDTO.Estimate {
        switch operation.input {
        case .refinement(let request): return try await refine(request: request)
        default: return try await analyze(description: "")
        }
    }

    var analysisResults: [FoodAnalysisResponseDTO.Estimate]
    private var refinementContinuation: CheckedContinuation<FoodAnalysisResponseDTO.Estimate, Error>?
    var isRefinementWaiting: Bool { refinementContinuation != nil }

    init(analysisResults: [FoodAnalysisResponseDTO.Estimate]) {
        self.analysisResults = analysisResults
    }

    func analyze(description: String) async throws -> FoodAnalysisResponseDTO.Estimate {
        analysisResults.removeFirst()
    }

    func analyzeImage(
        data: Data, mimeType: String, description: String?
    ) async throws -> FoodAnalysisResponseDTO.Estimate {
        analysisResults.removeFirst()
    }

    func refine(request: FoodAnalysisRefinementRequestDTO) async throws -> FoodAnalysisResponseDTO.Estimate {
        try await withCheckedThrowingContinuation { continuation in
            refinementContinuation = continuation
        }
    }

    func completeRefinement(with estimate: FoodAnalysisResponseDTO.Estimate) {
        refinementContinuation?.resume(returning: estimate)
        refinementContinuation = nil
    }
}

private func makeEstimate() -> FoodAnalysisResponseDTO.Estimate {
    FoodAnalysisResponseDTO.Estimate(
        foodName: "Apfel",
        calories: 95,
        proteinGrams: 0.5,
        carbohydrateGrams: 25,
        fatGrams: 0.3,
        confidence: 0.9
    )
}

@MainActor
final class FoodAnalysisViewModelTests: XCTestCase {
    func testLateInterruptedAnswerCannotClearNewerAttempt() async throws {
        let service = GatedService()
        let model = FoodAnalysisViewModel(service: service)
        model.descriptionText = "synthetic"
        let first = Task { await model.analyze() }
        for _ in 0..<1000 where service.pendingCount < 1 { await Task.yield() }
        XCTAssertEqual(service.pendingCount, 1)
        let snapshot = try XCTUnwrap(model.currentOperation)
        model.interruptAnalysis()
        let retry = Task { await model.retryOperation() }
        for _ in 0..<1000 where service.pendingCount < 2 { await Task.yield() }
        XCTAssertEqual(service.pendingCount, 2)
        let retryToken = model.currentRequestToken
        service.resume(with: makeEstimate())
        await first.value
        XCTAssertTrue(model.isAnalyzing)
        XCTAssertEqual(model.currentRequestToken, retryToken)
        XCTAssertNil(model.reviewSession)
        XCTAssertEqual(service.operations, [snapshot, snapshot])
        service.resume(with: makeEstimate())
        await retry.value
        XCTAssertFalse(model.isAnalyzing)
        XCTAssertNotNil(model.reviewSession)
    }

    func testClosingPendingReviewKeepsUncertaintyAndNeverReopensIt() async throws {
        let service = ReplacementService(analysisResults: [makeEstimate()])
        let model = FoodAnalysisViewModel(service: service)
        model.descriptionText = "synthetic"
        await model.analyze()
        let session = try XCTUnwrap(model.reviewSession)
        session.correctionText = "half"
        let refinement = Task { await session.refine() }
        for _ in 0..<1000 where !service.isRefinementWaiting { await Task.yield() }
        XCTAssertTrue(service.isRefinementWaiting)
        model.closeReviewSession()
        model.descriptionText = "changed"
        XCTAssertTrue(model.requiresNewOperationConfirmation)
        XCTAssertNil(session.currentOperation)
        XCTAssertFalse(session.canConfirmCurrentDraft)
        await model.analyze()
        XCTAssertNil(model.reviewSession)
        service.completeRefinement(with: makeEstimate())
        await refinement.value
        XCTAssertNil(model.reviewSession)
        XCTAssertEqual(session.successfulRefinementCount, 0)
    }

    func testAuthFailureOnRetryDoesNotEraseEarlierUncertainty() async throws {
        let service = StubService(result: .failure(FoodAnalysisError.timeout))
        let model = FoodAnalysisViewModel(service: service)
        model.descriptionText = "synthetic"
        await model.analyze()
        let original = try XCTUnwrap(model.currentOperation)
        service.result = .failure(FoodAnalysisError.authenticationRequired)
        await model.retryOperation()
        XCTAssertEqual(service.operations, [original, original])
        XCTAssertTrue(model.requiresNewOperationConfirmation)
        model.descriptionText = "changed"
        await model.analyze()
        XCTAssertEqual(service.operations.count, 2)
        await model.analyze(confirmNewOperation: true)
        XCTAssertNotEqual(model.currentOperation?.id, original.id)
        XCTAssertFalse(model.requiresNewOperationConfirmation)
    }

    func testTimeoutRetryRetainsOperationAndChangedInputRequiresConfirmedReplacement() async throws {
        let service = StubService(result: .failure(FoodAnalysisError.timeout))
        let model = FoodAnalysisViewModel(service: service)
        model.descriptionText = "synthetic"
        await model.analyze()
        let original = try XCTUnwrap(model.currentOperation)
        XCTAssertEqual(service.callCount, 1)
        XCTAssertTrue(model.requiresNewOperationConfirmation)
        await model.retryOperation()
        XCTAssertEqual(service.operations, [original, original])
        model.descriptionText = "changed"
        await model.analyze()
        XCTAssertEqual(service.callCount, 2)
        await model.analyze(confirmNewOperation: true)
        XCTAssertNotEqual(model.currentOperation?.id, original.id)
        XCTAssertEqual(service.operations.last?.input, .text("changed"))
    }

    func testImageRetryKeepsEncodedBytes() async throws {
        let service = StubService(result: .failure(FoodAnalysisError.timeout))
        let model = FoodAnalysisViewModel(service: service)
        model.setPickedImage(rawData: makeTestJPEGData())
        await model.analyze()
        await model.retryOperation()
        XCTAssertEqual(service.operations.count, 2)
        XCTAssertEqual(service.operations.first, service.operations.last)
    }

    func testInterruptIgnoresLateAnswerAndRestartDoesNotResume() async throws {
        let service = GatedService()
        let model = FoodAnalysisViewModel(service: service)
        model.descriptionText = "synthetic"
        let task = Task { await model.analyze() }
        for _ in 0..<100 where service.callCount == 0 { await Task.yield() }
        let original = try XCTUnwrap(model.currentOperation)
        model.interruptAnalysis()
        XCTAssertEqual(model.currentOperation, original)
        XCTAssertEqual(model.lastError, .operationInterrupted)
        service.resume(with: makeEstimate())
        await task.value
        XCTAssertNil(model.reviewSession)
        XCTAssertEqual(service.callCount, 1)
        let restarted = FoodAnalysisViewModel(service: service)
        XCTAssertNil(restarted.currentOperation)
        XCTAssertEqual(restarted.descriptionText, "")
        XCTAssertEqual(service.callCount, 1)
    }

    func testRapidSecondTapAfterSuccessDoesNotStartAnotherOperation() async {
        let service = StubService(result: .success(makeEstimate()))
        let model = FoodAnalysisViewModel(service: service)
        model.descriptionText = "synthetic"
        await model.analyze()
        await model.analyze()
        XCTAssertEqual(service.callCount, 1)
        model.descriptionText = "changed"
        await model.analyze()
        XCTAssertEqual(service.callCount, 2)
        XCTAssertNotEqual(service.operations[0].id, service.operations[1].id)
    }

    func testConsumedAndExpiredOperationsAreNotRetriedOrReplaced() async {
        for error in [FoodAnalysisError.operationConsumed, .operationRequired, .operationConflict] {
            let service = StubService(result: .failure(error))
            let model = FoodAnalysisViewModel(service: service)
            model.descriptionText = "synthetic"
            await model.analyze()
            let original = model.currentOperation
            await model.analyze()
            await model.retryOperation()
            XCTAssertEqual(service.callCount, 1)
            XCTAssertEqual(model.currentOperation, original)
            XCTAssertTrue(model.requiresNewOperationConfirmation)
        }
    }

    func testAnalyzeIgnoresBlankDescription() async {
        let service = StubService(result: .success(makeEstimate()))
        let viewModel = FoodAnalysisViewModel(service: service)
        viewModel.descriptionText = "   "

        await viewModel.analyze()

        XCTAssertEqual(service.callCount, 0)
        XCTAssertNil(viewModel.reviewDraft)
        XCTAssertNil(viewModel.errorMessage)
    }

    func testSuccessfulAnalysisPopulatesReviewDraft() async {
        let service = StubService(result: .success(makeEstimate()))
        let viewModel = FoodAnalysisViewModel(service: service)
        viewModel.descriptionText = "Ein Apfel"

        await viewModel.analyze()

        XCTAssertEqual(viewModel.reviewDraft?.name, "Apfel")
        XCTAssertEqual(viewModel.reviewSession?.currentDraft.name, "Apfel")
        XCTAssertEqual(viewModel.reviewSession?.originalDescription, "Ein Apfel")
        XCTAssertEqual(viewModel.reviewSession?.sourceKind, .text)
        XCTAssertEqual(viewModel.reviewSession?.id, viewModel.reviewDraft?.id)
        XCTAssertNil(viewModel.errorMessage)
        XCTAssertFalse(viewModel.isAnalyzing)
    }

    func testReplacingReviewSessionIgnoresLateResponseFromPreviousSession() async {
        let replacement = FoodAnalysisResponseDTO.Estimate(
            foodName: "Banane",
            calories: 105,
            proteinGrams: 1.3,
            carbohydrateGrams: 27,
            fatGrams: 0.4,
            confidence: 0.9
        )
        let service = ReplacementService(analysisResults: [makeEstimate(), replacement])
        let viewModel = FoodAnalysisViewModel(service: service)
        viewModel.descriptionText = "Ein Apfel"
        await viewModel.analyze()
        let oldSession = try! XCTUnwrap(viewModel.reviewSession)
        oldSession.correctionText = "Nur die Hälfte"
        let refinement = Task { await oldSession.refine() }
        for _ in 0..<1000 where !service.isRefinementWaiting { await Task.yield() }
        XCTAssertTrue(service.isRefinementWaiting)

        viewModel.descriptionText = "Eine Banane"
        await viewModel.analyze()
        let replacementID = viewModel.reviewSession?.id
        service.completeRefinement(with: FoodAnalysisResponseDTO.Estimate(
            foodName: "Verspäteter Apfel",
            calories: 1,
            proteinGrams: 0,
            carbohydrateGrams: 0,
            fatGrams: 0,
            confidence: 0.1
        ))
        await refinement.value

        XCTAssertNotEqual(oldSession.id, replacementID)
        XCTAssertEqual(oldSession.currentEstimate, makeEstimate())
        XCTAssertEqual(viewModel.reviewSession?.currentEstimate, replacement)
        XCTAssertEqual(viewModel.reviewDraft?.name, "Banane")
    }

    func testDescriptionTextIsPreservedAfterFailure() async {
        let service = StubService(result: .failure(FoodAnalysisError.timeout))
        let viewModel = FoodAnalysisViewModel(service: service)
        viewModel.descriptionText = "Ein Apfel"

        await viewModel.analyze()

        XCTAssertEqual(viewModel.descriptionText, "Ein Apfel")
        XCTAssertEqual(viewModel.errorMessage, FoodAnalysisViewModel.userMessage(for: .timeout))
        XCTAssertNil(viewModel.reviewDraft)
    }

    func testDuplicateAnalyzeCallWhileInFlightIsIgnored() async {
        let service = GatedService()
        let viewModel = FoodAnalysisViewModel(service: service)
        viewModel.descriptionText = "Ein Apfel"

        let firstTask = Task { await viewModel.analyze() }

        // Let the first call reach its suspension point (the gated network
        // call) before attempting a duplicate submission.
        for _ in 0..<1000 where service.pendingCount == 0 { await Task.yield() }
        XCTAssertEqual(service.pendingCount, 1)
        XCTAssertTrue(viewModel.isAnalyzing)

        await viewModel.analyze()  // must be a no-op: isAnalyzing is already true

        service.resume(with: makeEstimate())
        await firstTask.value

        XCTAssertEqual(service.callCount, 1)
        XCTAssertFalse(viewModel.isAnalyzing)
        XCTAssertNotNil(viewModel.reviewDraft)
    }

    // MARK: - Image support

    private func makeTestJPEGData() -> Data {
        let width = 4
        let height = 4
        let context = CGContext(
            data: nil, width: width, height: height, bitsPerComponent: 8, bytesPerRow: 0,
            space: CGColorSpaceCreateDeviceRGB(), bitmapInfo: CGImageAlphaInfo.premultipliedLast.rawValue
        )!
        context.setFillColor(CGColor(red: 1, green: 0, blue: 0, alpha: 1))
        context.fill(CGRect(x: 0, y: 0, width: width, height: height))
        let cgImage = context.makeImage()!
        let data = NSMutableData()
        let destination = CGImageDestinationCreateWithData(data, UTType.jpeg.identifier as CFString, 1, nil)!
        CGImageDestinationAddImage(destination, cgImage, nil)
        CGImageDestinationFinalize(destination)
        return data as Data
    }

    func testAnalyzeIgnoresEmptyStateWithNoTextOrImage() async {
        let service = StubService(result: .success(makeEstimate()))
        let viewModel = FoodAnalysisViewModel(service: service)

        await viewModel.analyze()

        XCTAssertEqual(service.callCount, 0)
    }

    func testSetPickedImageStoresPreprocessedImageOnSuccess() {
        let service = StubService(result: .success(makeEstimate()))
        let viewModel = FoodAnalysisViewModel(service: service)

        viewModel.setPickedImage(rawData: makeTestJPEGData())

        XCTAssertNotNil(viewModel.selectedImage)
        XCTAssertEqual(viewModel.selectedImage?.mimeType, "image/jpeg")
        XCTAssertNil(viewModel.errorMessage)
    }

    func testSetPickedImageWithInvalidDataSurfacesError() {
        let service = StubService(result: .success(makeEstimate()))
        let viewModel = FoodAnalysisViewModel(service: service)

        viewModel.setPickedImage(rawData: Data("not an image".utf8))

        XCTAssertNil(viewModel.selectedImage)
        XCTAssertEqual(viewModel.errorMessage, FoodAnalysisViewModel.userMessage(for: .imageProcessingFailed))
    }

    func testRemoveSelectedImageClearsState() {
        let service = StubService(result: .success(makeEstimate()))
        let viewModel = FoodAnalysisViewModel(service: service)
        viewModel.setPickedImage(rawData: makeTestJPEGData())
        XCTAssertNotNil(viewModel.selectedImage)

        viewModel.removeSelectedImage()

        XCTAssertNil(viewModel.selectedImage)
    }

    func testAnalyzeWithImageOnlyCallsAnalyzeImage() async {
        let service = StubService(result: .success(makeEstimate()))
        let viewModel = FoodAnalysisViewModel(service: service)
        viewModel.setPickedImage(rawData: makeTestJPEGData())

        await viewModel.analyze()

        XCTAssertEqual(service.callCount, 1)
        XCTAssertNil(service.lastImageDescription)
        XCTAssertNotNil(viewModel.reviewDraft)
        XCTAssertEqual(viewModel.reviewSession?.sourceKind, .image)
    }

    func testAnalyzeWithTextAndImageSendsBoth() async {
        let service = StubService(result: .success(makeEstimate()))
        let viewModel = FoodAnalysisViewModel(service: service)
        viewModel.descriptionText = "a bowl of pasta"
        viewModel.setPickedImage(rawData: makeTestJPEGData())

        await viewModel.analyze()

        XCTAssertEqual(service.callCount, 1)
        XCTAssertEqual(service.lastImageDescription, "a bowl of pasta")
        XCTAssertEqual(viewModel.reviewSession?.sourceKind, .textAndImage)
    }

    func testSelectedImageIsRetainedAfterAnalysisFailure() async {
        let service = StubService(result: .failure(FoodAnalysisError.timeout))
        let viewModel = FoodAnalysisViewModel(service: service)
        viewModel.setPickedImage(rawData: makeTestJPEGData())

        await viewModel.analyze()

        XCTAssertNotNil(viewModel.selectedImage)
        XCTAssertEqual(viewModel.errorMessage, FoodAnalysisViewModel.userMessage(for: .timeout))
    }
}
