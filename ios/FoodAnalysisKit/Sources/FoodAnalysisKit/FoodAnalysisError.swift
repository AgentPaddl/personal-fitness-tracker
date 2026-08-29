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
}
