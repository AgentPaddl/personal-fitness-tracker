import Foundation

/// Minimal seam over `URLSession` so networking can be mocked in tests.
public protocol URLRequestPerforming: Sendable {
    func data(for request: URLRequest) async throws -> (Data, URLResponse)
}

extension URLSession: URLRequestPerforming {}

/// Public contract for the text food-analysis networking call.
public protocol FoodAnalysisServicing: Sendable {
    func analyze(description: String) async throws -> FoodAnalysisResponseDTO.Estimate
}

/// Calls the Fitness API backend's `POST /api/food-analysis` endpoint.
///
/// This is the only network call in the food-analysis flow, and it only
/// ever talks to our own backend's public JSON contract. It has no
/// knowledge of the Personal AI Gateway, GitHub Copilot, model ids,
/// provider routing, or credentials of any kind.
public final class FoodAnalysisService: FoodAnalysisServicing {
    private let baseURL: URL
    private let session: URLRequestPerforming
    private let timeoutInterval: TimeInterval

    public init(
        baseURL: URL,
        session: URLRequestPerforming = URLSession.shared,
        timeoutInterval: TimeInterval = 30
    ) {
        self.baseURL = baseURL
        self.session = session
        self.timeoutInterval = timeoutInterval
    }

    public func analyze(description: String) async throws -> FoodAnalysisResponseDTO.Estimate {
        var request = URLRequest(url: baseURL.appendingPathComponent("food-analysis"))
        request.httpMethod = "POST"
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")
        request.timeoutInterval = timeoutInterval
        request.httpBody = try JSONEncoder().encode(FoodAnalysisRequestDTO(foodDescription: description))

        let data: Data
        let response: URLResponse
        do {
            (data, response) = try await session.data(for: request)
        } catch let urlError as URLError {
            throw Self.mapURLError(urlError)
        } catch {
            throw FoodAnalysisError.analysisFailed
        }

        guard let httpResponse = response as? HTTPURLResponse else {
            throw FoodAnalysisError.invalidResponse
        }

        guard (200..<300).contains(httpResponse.statusCode) else {
            throw Self.mapErrorResponse(statusCode: httpResponse.statusCode, data: data)
        }

        guard let decoded = try? JSONDecoder().decode(FoodAnalysisResponseDTO.self, from: data) else {
            throw FoodAnalysisError.invalidResponse
        }
        return decoded.estimate
    }

    static func mapURLError(_ error: URLError) -> FoodAnalysisError {
        switch error.code {
        case .notConnectedToInternet, .networkConnectionLost, .cannotConnectToHost, .cannotFindHost,
            .dataNotAllowed, .dnsLookupFailed:
            return .noConnection
        case .timedOut:
            return .timeout
        default:
            return .analysisFailed
        }
    }

    static func mapErrorResponse(statusCode: Int, data: Data) -> FoodAnalysisError {
        // Prefer the backend's own normalized error code when present; it
        // already encodes the right category (e.g. a 502 that is really a
        // rate-limit or timeout at the gateway boundary).
        if let code = (try? JSONDecoder().decode(BackendErrorEnvelope.self, from: data))?.error.code {
            switch code {
            case "gateway_rate_limited":
                return .rateLimited
            case "gateway_timeout":
                return .timeout
            case "gateway_service_unavailable", "gateway_unreachable":
                return .backendUnavailable
            default:
                break
            }
        }

        switch statusCode {
        case 401, 403:
            return .unauthorized
        case 429:
            return .rateLimited
        case 503:
            return .backendUnavailable
        case 504:
            return .timeout
        default:
            return .analysisFailed
        }
    }
}
