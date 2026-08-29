import XCTest

@testable import FoodAnalysisKit

final class FoodAnalysisErrorRetryEligibilityTests: XCTestCase {
    func testConnectivityBackendRateLimitAndTimeoutAreRetryEligible() {
        for error: FoodAnalysisError in [.noConnection, .timeout, .backendUnavailable, .rateLimited, .analysisFailed] {
            XCTAssertTrue(error.isRetryEligible, "\(error) should be retry-eligible")
        }
    }

    func testInputAndConfigurationErrorsAreNotRetryEligible() {
        for error: FoodAnalysisError in [
            .unauthorized, .invalidResponse, .imageProcessingFailed, .imageMissingOrEmpty,
            .unsupportedImageType, .imageTooLarge, .authenticationRequired,
        ] {
            XCTAssertFalse(error.isRetryEligible, "\(error) should not be retry-eligible")
        }
    }
}
