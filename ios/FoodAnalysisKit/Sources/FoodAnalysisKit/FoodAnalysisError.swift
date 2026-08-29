/// User-facing, provider-neutral error categories for the food-analysis flow.
/// Never carries raw backend/provider text, model ids, or stack traces -
/// UI copy is derived separately from these cases only.
public enum FoodAnalysisError: Error, Equatable, Sendable {
    case noConnection
    case timeout
    case backendUnavailable
    case rateLimited
    case unauthorized
    case invalidResponse
    case analysisFailed
    /// The picked photo could not be decoded/re-encoded on-device.
    case imageProcessingFailed
    /// No image was selected (or it was empty) when an image call was made.
    case imageMissingOrEmpty
    /// The backend rejected the image's MIME type.
    case unsupportedImageType
    /// The backend rejected the image for exceeding the size limit.
    case imageTooLarge
    /// An `AccessTokenProviding` implementation failed to produce a token
    /// before the request could even be sent (e.g. interactive Entra ID
    /// sign-in is required, or a refresh silently failed). Distinct from
    /// `.unauthorized`, which is the backend itself rejecting the request
    /// after it was sent.
    case authenticationRequired

    /// Whether an explicit "Erneut versuchen" retry action makes sense for
    /// this failure. Only failures where an identical retry could
    /// plausibly succeed without any change to the input (connectivity,
    /// a temporarily unavailable backend, rate limiting, or a timeout) are
    /// eligible; input/configuration problems are not, since retrying the
    /// exact same request would just fail the same way again.
    public var isRetryEligible: Bool {
        switch self {
        case .noConnection, .timeout, .backendUnavailable, .rateLimited, .analysisFailed:
            return true
        case .unauthorized, .invalidResponse, .imageProcessingFailed, .imageMissingOrEmpty,
            .unsupportedImageType, .imageTooLarge, .authenticationRequired:
            return false
        }
    }
}
