import CoreGraphics
import ImageIO
import UniformTypeIdentifiers
import XCTest

@testable import FoodAnalysisKit

@MainActor
private final class StubService: FoodAnalysisServicing {
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
    private(set) var callCount = 0
    private var continuation: CheckedContinuation<FoodAnalysisResponseDTO.Estimate, Error>?

    func analyze(description: String) async throws -> FoodAnalysisResponseDTO.Estimate {
        callCount += 1
        return try await withCheckedThrowingContinuation { continuation in
            self.continuation = continuation
        }
    }

    func analyzeImage(
        data: Data, mimeType: String, description: String?
    ) async throws -> FoodAnalysisResponseDTO.Estimate {
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
    }

    func testAnalyzeWithTextAndImageSendsBoth() async {
        let service = StubService(result: .success(makeEstimate()))
        let viewModel = FoodAnalysisViewModel(service: service)
        viewModel.descriptionText = "a bowl of pasta"
        viewModel.setPickedImage(rawData: makeTestJPEGData())

        await viewModel.analyze()

        XCTAssertEqual(service.callCount, 1)
        XCTAssertEqual(service.lastImageDescription, "a bowl of pasta")
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
