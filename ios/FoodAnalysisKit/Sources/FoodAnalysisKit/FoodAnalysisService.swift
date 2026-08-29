import Foundation

/// Minimal seam over `URLSession` so networking can be mocked in tests.
public protocol URLRequestPerforming: Sendable {
    func data(for request: URLRequest) async throws -> (Data, URLResponse)
}

extension URLSession: URLRequestPerforming {}

/// Provider-neutral seam for acquiring a short-lived access token to send
/// as `Authorization: Bearer <token>` on every backend request. The real
/// implementation (Entra ID via MSAL) lives in the app target
/// (`ios/Trainingsplan/EntraAuthService.swift`) - this package has no
/// dependency on MSAL or any provider-specific auth library.
///
/// `nil` (no provider configured) is a valid, supported state: no
/// `Authorization` header is ever sent, matching today's local-development
/// behavior exactly. A configured provider that fails to produce a token
/// must throw rather than silently proceed unauthenticated.
public protocol AccessTokenProviding: Sendable {
    func acquireAccessToken() async throws -> String
}

/// Public contract for the text food-analysis networking call.
public protocol FoodAnalysisServicing: Sendable {
    func analyze(description: String) async throws -> FoodAnalysisResponseDTO.Estimate
    /// Uploads an already-preprocessed image (and optional text) via
    /// `multipart/form-data`. `description`, if non-nil/non-blank, is sent
    /// alongside the image.
    func analyzeImage(
        data: Data, mimeType: String, description: String?
    ) async throws -> FoodAnalysisResponseDTO.Estimate
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
    private let tokenProvider: AccessTokenProviding?

    /// `timeoutInterval` default (110s) sits above the documented timeout
    /// hierarchy's outer bound - see `ios/AGENTS.md` - so this layer never
    /// aborts before the backend/gateway/provider layers below it can
    /// return their own normalized timeout.
    public init(
        baseURL: URL,
        session: URLRequestPerforming = URLSession.shared,
        timeoutInterval: TimeInterval = 110,
        tokenProvider: AccessTokenProviding? = nil
    ) {
        self.baseURL = baseURL
        self.session = session
        self.timeoutInterval = timeoutInterval
        self.tokenProvider = tokenProvider
    }

    public func analyze(description: String) async throws -> FoodAnalysisResponseDTO.Estimate {
        var request = URLRequest(url: baseURL.appendingPathComponent("food-analysis"))
        request.httpMethod = "POST"
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")
        try await applyAuthorization(to: &request)
        request.timeoutInterval = timeoutInterval
        request.httpBody = try JSONEncoder().encode(FoodAnalysisRequestDTO(foodDescription: description))

        return try await perform(request)
    }

    public func analyzeImage(
        data: Data, mimeType: String, description: String? = nil
    ) async throws -> FoodAnalysisResponseDTO.Estimate {
        let boundary = "Boundary-\(UUID().uuidString)"
        var request = URLRequest(url: baseURL.appendingPathComponent("food-analysis"))
        request.httpMethod = "POST"
        request.setValue("multipart/form-data; boundary=\(boundary)", forHTTPHeaderField: "Content-Type")
        try await applyAuthorization(to: &request)
        request.timeoutInterval = timeoutInterval
        request.httpBody = Self.multipartBody(
            boundary: boundary, imageData: data, mimeType: mimeType, description: description
        )

        return try await perform(request)
    }

    private func applyAuthorization(to request: inout URLRequest) async throws {
        guard let tokenProvider else { return }
        let token: String
        do {
            token = try await tokenProvider.acquireAccessToken()
        } catch {
            throw FoodAnalysisError.authenticationRequired
        }
        guard !token.isEmpty else { throw FoodAnalysisError.authenticationRequired }
        request.setValue("Bearer \(token)", forHTTPHeaderField: "Authorization")
    }

    private func perform(_ request: URLRequest) async throws -> FoodAnalysisResponseDTO.Estimate {
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

    static func multipartBody(boundary: String, imageData: Data, mimeType: String, description: String?) -> Data {
        var body = Data()

        func appendString(_ string: String) {
            if let stringData = string.data(using: .utf8) {
                body.append(stringData)
            }
        }

        if let description, !description.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty {
            appendString("--\(boundary)\r\n")
            appendString("Content-Disposition: form-data; name=\"food_description\"\r\n\r\n")
            appendString(description)
            appendString("\r\n")
        }

        appendString("--\(boundary)\r\n")
        appendString("Content-Disposition: form-data; name=\"image\"; filename=\"photo.jpg\"\r\n")
        appendString("Content-Type: \(mimeType)\r\n\r\n")
        body.append(imageData)
        appendString("\r\n")
        appendString("--\(boundary)--\r\n")

        return body
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
            case "unsupported_media_type":
                return .unsupportedImageType
            case "image_too_large":
                return .imageTooLarge
            case "image_required", "image_empty":
                return .imageMissingOrEmpty
            default:
                break
            }
        }

        switch statusCode {
        case 401, 403:
            return .unauthorized
        case 413:
            return .imageTooLarge
        case 415:
            return .unsupportedImageType
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
