import XCTest

@testable import FoodAnalysisKit

@MainActor
private final class StubService: FoodAnalysisServicing {
    var result: Result<FoodAnalysisResponseDTO.Estimate, Error>
    private(set) var callCount = 0

    init(result: Result<FoodAnalysisResponseDTO.Estimate, Error>) {
        self.result = result
    }

    func analyze(description: String) async throws -> FoodAnalysisResponseDTO.Estimate {
        callCount += 1
        return try result.get()
    }
}

/// Lets a test control exactly when the in-flight network call completes,
/// to deterministically exercise the duplicate-submission guard. Isolated
/// to `MainActor` (like its only caller) so its mutable state safely
/// satisfies the `FoodAnalysisServicing: Sendable` requirement.
@MainActor
private final class GatedService: FoodAnalysisServicing {
    private(set) var callCount = 0
    private var continuation: CheckedContinuation<FoodAnalysisResponseDTO.Estimate, Error>?

    func analyze(description: String) async throws -> FoodAnalysisResponseDTO.Estimate {
        callCount += 1
        return try await withCheckedThrowingContinuation { continuation in
            self.continuation = continuation
        }
    }

    func resume(with estimate: FoodAnalysisResponseDTO.Estimate) {
        continuation?.resume(returning: estimate)
        continuation = nil
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
        XCTAssertNil(viewModel.errorMessage)
        XCTAssertFalse(viewModel.isAnalyzing)
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
        for _ in 0..<5 { await Task.yield() }
        XCTAssertTrue(viewModel.isAnalyzing)

        await viewModel.analyze()  // must be a no-op: isAnalyzing is already true

        service.resume(with: makeEstimate())
        await firstTask.value

        XCTAssertEqual(service.callCount, 1)
        XCTAssertFalse(viewModel.isAnalyzing)
        XCTAssertNotNil(viewModel.reviewDraft)
    }
}
