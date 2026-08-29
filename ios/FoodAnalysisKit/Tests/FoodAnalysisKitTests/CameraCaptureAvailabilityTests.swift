import XCTest

@testable import FoodAnalysisKit

final class CameraCaptureAvailabilityTests: XCTestCase {
    func testHardwareUnavailableAlwaysWinsRegardlessOfAuthorization() {
        for status in [
            CameraAuthorizationStatus.authorized, .notDetermined, .denied, .restricted,
        ] {
            let decision = CameraCaptureAvailability.decide(
                isCameraHardwareAvailable: false, authorizationStatus: status
            )
            XCTAssertEqual(decision, .unavailable(.hardwareUnavailable))
        }
    }

    func testAuthorizedWithHardwarePresentsCameraImmediately() {
        let decision = CameraCaptureAvailability.decide(
            isCameraHardwareAvailable: true, authorizationStatus: .authorized
        )
        XCTAssertEqual(decision, .presentCamera)
    }

    func testNotDeterminedRequestsPermissionFirst() {
        let decision = CameraCaptureAvailability.decide(
            isCameraHardwareAvailable: true, authorizationStatus: .notDetermined
        )
        XCTAssertEqual(decision, .requestPermission)
    }

    func testDeniedIsUnavailableWithoutReprompting() {
        let decision = CameraCaptureAvailability.decide(
            isCameraHardwareAvailable: true, authorizationStatus: .denied
        )
        XCTAssertEqual(decision, .unavailable(.permissionDenied))
    }

    func testRestrictedIsUnavailable() {
        let decision = CameraCaptureAvailability.decide(
            isCameraHardwareAvailable: true, authorizationStatus: .restricted
        )
        XCTAssertEqual(decision, .unavailable(.permissionRestricted))
    }
}
