import XCTest

@testable import FoodAnalysisKit

private struct MockPerformer: URLRequestPerforming {
    let handler: @Sendable (URLRequest) throws -> (Data, URLResponse)

    func data(for request: URLRequest) async throws -> (Data, URLResponse) {
        try handler(request)
    }
}

private func assertThrowsFoodAnalysisError(
    _ expression: @autoclosure () async throws -> FoodAnalysisResponseDTO.Estimate,
    _ expected: FoodAnalysisError,
    file: StaticString = #filePath,
    line: UInt = #line
) async {
    do {
        _ = try await expression()
        XCTFail("Expected \(expected) to be thrown", file: file, line: line)
    } catch let error as FoodAnalysisError {
        XCTAssertEqual(error, expected, file: file, line: line)
    } catch {
        XCTFail("Expected FoodAnalysisError, got \(error)", file: file, line: line)
    }
}

final class FoodAnalysisServiceTests: XCTestCase {
    private let baseURL = URL(string: "https://example.test/api")!

    func testSuccessfulAnalysisReturnsEstimateAndSendsExpectedRequest() async throws {
        let baseURL = baseURL
        let responseJSON = """
            {"estimate": {"food_name": "Apfel", "calories": 95, "protein_grams": 0.5,
            "carbohydrate_grams": 25, "fat_grams": 0.3, "confidence": 0.9, "warnings": []}}
            """.data(using: .utf8)!

        let mock = MockPerformer { request in
            XCTAssertEqual(request.url, baseURL.appendingPathComponent("food-analysis"))
            XCTAssertEqual(request.httpMethod, "POST")
            let body = try XCTUnwrap(request.httpBody)
            let json = try JSONSerialization.jsonObject(with: body) as? [String: Any]
            XCTAssertEqual(json?["food_description"] as? String, "Ein Apfel")

            let response = HTTPURLResponse(url: request.url!, statusCode: 200, httpVersion: nil, headerFields: nil)!
            return (responseJSON, response)
        }

        let service = FoodAnalysisService(baseURL: baseURL, session: mock)
        let estimate = try await service.analyze(description: "Ein Apfel")

        XCTAssertEqual(estimate.foodName, "Apfel")
        XCTAssertEqual(estimate.calories, 95)
    }

    func testTimeoutIsMappedToTimeoutError() async {
        let mock = MockPerformer { _ in throw URLError(.timedOut) }
        let service = FoodAnalysisService(baseURL: baseURL, session: mock)

        await assertThrowsFoodAnalysisError(try await service.analyze(description: "x"), .timeout)
    }

    func testNoConnectionIsMappedToNoConnectionError() async {
        let mock = MockPerformer { _ in throw URLError(.notConnectedToInternet) }
        let service = FoodAnalysisService(baseURL: baseURL, session: mock)

        await assertThrowsFoodAnalysisError(try await service.analyze(description: "x"), .noConnection)
    }

    func testRateLimitedBackendErrorIsMapped() async {
        let errorJSON = #"{"error": {"code": "gateway_rate_limited", "message": "rate limited"}}"#
            .data(using: .utf8)!
        let mock = MockPerformer { request in
            let response = HTTPURLResponse(url: request.url!, statusCode: 429, httpVersion: nil, headerFields: nil)!
            return (errorJSON, response)
        }
        let service = FoodAnalysisService(baseURL: baseURL, session: mock)

        await assertThrowsFoodAnalysisError(try await service.analyze(description: "x"), .rateLimited)
    }

    func testBackendUnavailableErrorIsMapped() async {
        let errorJSON = #"{"error": {"code": "gateway_service_unavailable", "message": "unavailable"}}"#
            .data(using: .utf8)!
        let mock = MockPerformer { request in
            let response = HTTPURLResponse(url: request.url!, statusCode: 503, httpVersion: nil, headerFields: nil)!
            return (errorJSON, response)
        }
        let service = FoodAnalysisService(baseURL: baseURL, session: mock)

        await assertThrowsFoodAnalysisError(try await service.analyze(description: "x"), .backendUnavailable)
    }

    func testGatewayUnreachableErrorIsMapped() async {
        let errorJSON = #"{"error": {"code": "gateway_unreachable", "message": "unreachable"}}"#
            .data(using: .utf8)!
        let mock = MockPerformer { request in
            let response = HTTPURLResponse(url: request.url!, statusCode: 503, httpVersion: nil, headerFields: nil)!
            return (errorJSON, response)
        }
        let service = FoodAnalysisService(baseURL: baseURL, session: mock)

        await assertThrowsFoodAnalysisError(try await service.analyze(description: "x"), .backendUnavailable)
    }

    func testDevelopmentModeGateIsMappedToUnauthorized() async {
        // Backend returns 403 "not_implemented" outside APP_ENV=development.
        let mock = MockPerformer { request in
            let response = HTTPURLResponse(url: request.url!, statusCode: 403, httpVersion: nil, headerFields: nil)!
            return (Data("{}".utf8), response)
        }
        let service = FoodAnalysisService(baseURL: baseURL, session: mock)

        await assertThrowsFoodAnalysisError(try await service.analyze(description: "x"), .unauthorized)
    }

    func testGatewayTimeoutStatusIsMappedToTimeout() async {
        let mock = MockPerformer { request in
            let response = HTTPURLResponse(url: request.url!, statusCode: 504, httpVersion: nil, headerFields: nil)!
            return (Data("{}".utf8), response)
        }
        let service = FoodAnalysisService(baseURL: baseURL, session: mock)

        await assertThrowsFoodAnalysisError(try await service.analyze(description: "x"), .timeout)
    }

    func testInvalidJSONBodyIsMappedToInvalidResponse() async {
        let mock = MockPerformer { request in
            let response = HTTPURLResponse(url: request.url!, statusCode: 200, httpVersion: nil, headerFields: nil)!
            return (Data("not json".utf8), response)
        }
        let service = FoodAnalysisService(baseURL: baseURL, session: mock)

        await assertThrowsFoodAnalysisError(try await service.analyze(description: "x"), .invalidResponse)
    }

    func testMissingHTTPURLResponseIsMappedToInvalidResponse() async {
        let mock = MockPerformer { request in
            (Data(), URLResponse(url: request.url!, mimeType: nil, expectedContentLength: 0, textEncodingName: nil))
        }
        let service = FoodAnalysisService(baseURL: baseURL, session: mock)

        await assertThrowsFoodAnalysisError(try await service.analyze(description: "x"), .invalidResponse)
    }

    func testUnknownServerErrorFallsBackToAnalysisFailed() async {
        let mock = MockPerformer { request in
            let response = HTTPURLResponse(url: request.url!, statusCode: 500, httpVersion: nil, headerFields: nil)!
            return (Data("{}".utf8), response)
        }
        let service = FoodAnalysisService(baseURL: baseURL, session: mock)

        await assertThrowsFoodAnalysisError(try await service.analyze(description: "x"), .analysisFailed)
    }
}
