import Foundation

/// The camera authorization states this package cares about, abstracted
/// away from `AVAuthorizationStatus` so this logic has no AVFoundation/
/// UIKit dependency and is testable here.
public enum CameraAuthorizationStatus: Sendable, Equatable {
    case notDetermined
    case authorized
    case denied
    case restricted
}

/// Reasons camera capture cannot proceed right now.
public enum CameraCaptureUnavailableReason: Sendable, Equatable {
    /// No camera hardware is available (e.g. the iOS Simulator).
    case hardwareUnavailable
    /// The user previously denied camera access.
    case permissionDenied
    /// Camera access is restricted (e.g. parental controls/MDM policy).
    case permissionRestricted
}

/// Pure decision logic for whether tapping "Foto aufnehmen" should open the
/// camera, request permission, or show a friendly blocked-state message.
/// Kept independent of AVFoundation/UIKit so it is testable without a
/// simulator/device and reusable regardless of how the app layer queries
/// hardware/permission state.
public enum CameraCaptureAvailability {
    public enum Decision: Sendable, Equatable {
        /// Present the camera immediately.
        case presentCamera
        /// Authorization has never been asked; the app layer must call the
        /// system permission request before presenting the camera.
        case requestPermission
        /// Capture cannot proceed; show a friendly message for this reason.
        case unavailable(CameraCaptureUnavailableReason)
    }

    public static func decide(
        isCameraHardwareAvailable: Bool,
        authorizationStatus: CameraAuthorizationStatus
    ) -> Decision {
        guard isCameraHardwareAvailable else { return .unavailable(.hardwareUnavailable) }

        switch authorizationStatus {
        case .authorized:
            return .presentCamera
        case .notDetermined:
            return .requestPermission
        case .denied:
            return .unavailable(.permissionDenied)
        case .restricted:
            return .unavailable(.permissionRestricted)
        }
    }
}
