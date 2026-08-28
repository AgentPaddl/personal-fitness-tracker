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
}
