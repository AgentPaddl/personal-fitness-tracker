import XCTest

@testable import FoodAnalysisKit

private struct MockPerformer: URLRequestPerforming {
    let handler: @Sendable (URLRequest) throws -> (Data, URLResponse)

    func data(for request: URLRequest) async throws -> (Data, URLResponse) {
        try handler(request)
    }
}

private struct StubTokenProvider: AccessTokenProviding {
    var token: String = ""
    var error: Error?

    func acquireAccessToken() async throws -> String {
        if let error { throw error }
        return token
    }
}

private actor RotatingTokenProvider: AccessTokenProviding {
    private var count = 0
    func acquireAccessToken() async throws -> String {
        count += 1
        return "synthetic-token-\(count)"
    }
}

@MainActor
private final class DeferredAccountProvider: AccountAccessTokenProviding {
    private var continuation: CheckedContinuation<AccountAccessToken, Never>?
    var isWaiting: Bool { continuation != nil }

    func acquireAccessToken() async throws -> String {
        try await acquireAccountAccessToken().token
    }

    func acquireAccountAccessToken() async throws -> AccountAccessToken {
        await withCheckedContinuation { continuation = $0 }
    }

    func completeLogin() {
        continuation?.resume(returning: AccountAccessToken(token: "synthetic-token", accountIdentifier: "account-a"))
        continuation = nil
    }
}

private actor SwitchingAccountProvider: AccountAccessTokenProviding {
    private var count = 0

    func acquireAccessToken() async throws -> String {
        try await acquireAccountAccessToken().token
    }

    func acquireAccountAccessToken() async throws -> AccountAccessToken {
        count += 1
        return AccountAccessToken(token: "synthetic-token-\(count)", accountIdentifier: count <= 2 ? "account-a" : "account-b")
    }
}

private actor RecordingPerformer: URLRequestPerforming {
    private(set) var requests: [URLRequest] = []
    let firstStatus: Int

    init(firstStatus: Int) { self.firstStatus = firstStatus }

    func data(for request: URLRequest) async throws -> (Data, URLResponse) {
        requests.append(request)
        if requests.count == 1 && firstStatus == 0 { throw URLError(.timedOut) }
        let status = requests.count == 1 ? firstStatus : 200
        let data = Data(#"{"estimate":{"food_name":"synthetic","calories":1,"protein_grams":0,"carbohydrate_grams":0,"fat_grams":0,"confidence":0.5,"warnings":[]}}"#.utf8)
        return (data, HTTPURLResponse(url: request.url!, statusCode: status, httpVersion: nil, headerFields: nil)!)
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

    @MainActor
    func testDelayedLoginCompletionPreservesSnapshotUnlessExplicitlyCancelled() async throws {
        for cancelExplicitly in [false, true] {
            let provider = DeferredAccountProvider()
            let performer = RecordingPerformer(firstStatus: 200)
            let service = FoodAnalysisService(baseURL: baseURL, session: performer, tokenProvider: provider)
            let operation = try FoodAnalysisOperation(input: .text("synthetic"))
            let task = Task { try await service.perform(operation: operation) }
            for _ in 0..<1000 where !provider.isWaiting { await Task.yield() }
            XCTAssertTrue(provider.isWaiting)
            let beforeLogin = await performer.requests
            XCTAssertTrue(beforeLogin.isEmpty)
            if cancelExplicitly { task.cancel() }
            provider.completeLogin()
            do {
                _ = try await task.value
                XCTAssertFalse(cancelExplicitly)
            } catch is CancellationError {
                XCTAssertTrue(cancelExplicitly)
            }
            let sent = await performer.requests
            XCTAssertEqual(sent.count, cancelExplicitly ? 0 : 1)
            if !cancelExplicitly {
                XCTAssertEqual(sent.first?.httpBody, operation.body)
                XCTAssertEqual(sent.first?.value(forHTTPHeaderField: "X-Operation-Id"), operation.id.uuidString.lowercased())
            }
        }
    }

    func testRenewalRetainsAccountButAccountSwitchCannotRedispatchExistingOperation() async throws {
        let performer = RecordingPerformer(firstStatus: 0)
        let service = FoodAnalysisService(baseURL: baseURL, session: performer, tokenProvider: SwitchingAccountProvider())
        let operation = try FoodAnalysisOperation(input: .text("synthetic"))
        await assertThrowsFoodAnalysisError(try await service.perform(operation: operation), .timeout)
        _ = try await service.perform(operation: operation)
        await assertThrowsFoodAnalysisError(try await service.perform(operation: operation), .operationAccountChanged)
        let sent = await performer.requests
        XCTAssertEqual(sent.count, 2)
        XCTAssertEqual(sent[0].httpBody, sent[1].httpBody)
        _ = try await service.perform(operation: FoodAnalysisOperation(input: operation.input))
        let afterNewOperation = await performer.requests
        XCTAssertEqual(afterNewOperation.count, 3)
        XCTAssertNotEqual(sent[0].value(forHTTPHeaderField: "X-Operation-Id"), afterNewOperation[2].value(forHTTPHeaderField: "X-Operation-Id"))
    }

    func testExplicitRetryAfterTimeoutOrTokenRenewalKeepsExactIDAndPayload() async throws {
        let refinement = FoodAnalysisRefinementRequestDTO(foodDescription: "synthetic", refinement: .init(
            correctionText: "half", currentEstimate: .init(foodName: "synthetic", calories: 1, proteinGrams: 0,
                carbohydrateGrams: 0, fatGrams: 0, confidence: 0.5, warnings: [], assumptions: []),
            sourceKind: .image, iteration: 1))
        let inputs: [FoodAnalysisOperation.Input] = [.text("synthetic"),
            .image(data: Data([1, 2, 3]), mimeType: "image/jpeg", description: "synthetic"), .refinement(refinement)]
        for input in inputs {
            for status in [0, 401] {
                let performer = RecordingPerformer(firstStatus: status)
                let service = FoodAnalysisService(baseURL: baseURL, session: performer, tokenProvider: RotatingTokenProvider())
                let operation = try FoodAnalysisOperation(input: input)
                await assertThrowsFoodAnalysisError(try await service.perform(operation: operation), status == 0 ? .timeout : .unauthorized)
                let afterFailure = await performer.requests
                XCTAssertEqual(afterFailure.count, 1)
                _ = try await service.perform(operation: operation)
                let sent = await performer.requests
                XCTAssertEqual(sent.count, 2)
                XCTAssertEqual(sent[0].httpBody, sent[1].httpBody)
                XCTAssertEqual(sent[0].value(forHTTPHeaderField: "Content-Type"), sent[1].value(forHTTPHeaderField: "Content-Type"))
                XCTAssertEqual(sent[0].value(forHTTPHeaderField: "X-Operation-Id"), operation.id.uuidString.lowercased())
                XCTAssertEqual(sent[0].value(forHTTPHeaderField: "X-Operation-Id"), sent[1].value(forHTTPHeaderField: "X-Operation-Id"))
                XCTAssertEqual(sent[0].value(forHTTPHeaderField: "Authorization"), "Bearer synthetic-token-1")
                XCTAssertEqual(sent[1].value(forHTTPHeaderField: "Authorization"), "Bearer synthetic-token-2")
                XCTAssertNil(sent[0].value(forHTTPHeaderField: "X-Request-Id"))
                if case .refinement = input {
                    let json = try XCTUnwrap(JSONSerialization.jsonObject(with: operation.body) as? [String: Any])
                    XCTAssertNil(json["image"])
                    XCTAssertEqual(operation.contentType, "application/json")
                }
            }
        }
    }

    func testPilotPublicStatesMapWithoutTrustingBackendMessages() {
        let states: [(String, Int, FoodAnalysisError)] = [
            ("operation_consumed", 409, .operationConsumed), ("operation_conflict", 409, .operationConflict),
            ("operation_required", 400, .operationRequired), ("pilot_unavailable", 503, .pilotUnavailable),
            ("pilot_forbidden", 403, .pilotForbidden), ("pilot_limit", 429, .pilotLimit), ("pilot_input", 413, .pilotInput)
        ]
        for (code, status, expected) in states {
            let body = Data("{\"error\":{\"code\":\"\(code)\",\"message\":\"private-marker\"}}".utf8)
            let error = FoodAnalysisService.mapErrorResponse(statusCode: status, data: body)
            XCTAssertEqual(error, expected)
            XCTAssertFalse(error.userMessage.contains("private-marker"))
            XCTAssertFalse(error.userMessage.isEmpty)
        }
        XCTAssertFalse(FoodAnalysisError.operationConsumed.canRetryOperation)
        XCTAssertFalse(FoodAnalysisError.operationRequired.canRetryOperation)
        XCTAssertFalse(FoodAnalysisError.operationConflict.canRetryOperation)
        XCTAssertEqual(FoodAnalysisService.mapURLError(URLError(.cancelled)), .operationInterrupted)
    }

    func testInvalidUUIDv7TimestampFailsBeforeSending() {
        for seconds in [-1.0, Double.infinity, Double.nan, 281_474_976_710.656] {
            XCTAssertThrowsError(try FoodAnalysisOperation(input: .text("synthetic"), now: Date(timeIntervalSince1970: seconds)))
        }
    }

    func testOperationUUIDv7ContractAndUniqueRandomness() throws {
        let now = Date(timeIntervalSince1970: 1_789_646_400.125)
        var identifiers = Set<UUID>()
        for _ in 0..<100 {
            let operation = try FoodAnalysisOperation(input: .text("synthetic"), now: now)
            let bytes = operation.id.uuid
            XCTAssertEqual(bytes.6 >> 4, 7)
            XCTAssertEqual(bytes.8 >> 6, 2)
            let hex = operation.id.uuidString.replacingOccurrences(of: "-", with: "")
            XCTAssertEqual(UInt64(hex.prefix(12), radix: 16), 1_789_646_400_125)
            identifiers.insert(operation.id)
        }
        XCTAssertEqual(identifiers.count, 100)
        XCTAssertEqual(FoodAnalysisOperation.headerName, "X-Operation-Id")
    }

    func testOperationSnapshotKeepsImageBodyAndBoundary() throws {
        var image = Data([1, 2, 3])
        let operation = try FoodAnalysisOperation(input: .image(data: image, mimeType: "image/jpeg", description: "synthetic"))
        let repeated = operation
        image.append(4)
        XCTAssertEqual(operation, repeated)
        XCTAssertEqual(operation.input, .image(data: Data([1, 2, 3]), mimeType: "image/jpeg", description: "synthetic"))
        XCTAssertEqual(operation.body, repeated.body)
        XCTAssertEqual(operation.contentType, repeated.contentType)
        XCTAssertNotEqual(operation.id, try FoodAnalysisOperation(input: operation.input).id)
    }

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

    func testAuthorizationHeaderIsSentWhenTokenProviderConfigured() async throws {
        let responseJSON = """
            {"estimate": {"food_name": "Apfel", "calories": 95, "protein_grams": 0.5,
            "carbohydrate_grams": 25, "fat_grams": 0.3, "confidence": 0.9, "warnings": []}}
            """.data(using: .utf8)!

        let mock = MockPerformer { request in
            XCTAssertEqual(request.value(forHTTPHeaderField: "Authorization"), "Bearer test-access-token")
            let response = HTTPURLResponse(url: request.url!, statusCode: 200, httpVersion: nil, headerFields: nil)!
            return (responseJSON, response)
        }

        let service = FoodAnalysisService(
            baseURL: baseURL, session: mock, tokenProvider: StubTokenProvider(token: "test-access-token")
        )
        _ = try await service.analyze(description: "Ein Apfel")
    }

    func testNoAuthorizationHeaderWhenNoTokenProviderConfigured() async throws {
        let responseJSON = """
            {"estimate": {"food_name": "Apfel", "calories": 95, "protein_grams": 0.5,
            "carbohydrate_grams": 25, "fat_grams": 0.3, "confidence": 0.9, "warnings": []}}
            """.data(using: .utf8)!

        let mock = MockPerformer { request in
            XCTAssertNil(request.value(forHTTPHeaderField: "Authorization"))
            let response = HTTPURLResponse(url: request.url!, statusCode: 200, httpVersion: nil, headerFields: nil)!
            return (responseJSON, response)
        }

        let service = FoodAnalysisService(baseURL: baseURL, session: mock)
        _ = try await service.analyze(description: "Ein Apfel")
    }

    func testTokenAcquisitionFailureIsMappedToAuthenticationRequired() async {
        let mock = MockPerformer { _ in
            XCTFail("The network layer must never be reached when token acquisition fails")
            throw URLError(.unknown)
        }
        let service = FoodAnalysisService(
            baseURL: baseURL, session: mock, tokenProvider: StubTokenProvider(error: URLError(.userAuthenticationRequired))
        )

        await assertThrowsFoodAnalysisError(try await service.analyze(description: "x"), .authenticationRequired)
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

    // MARK: - Refinement

    func testRefinementUsesSameEndpointAuthorizationAndJSONWithoutImageBytes() async throws {
        let baseURL = baseURL
        let responseJSON = """
            {"estimate": {"food_name": "Reis", "calories": 310, "protein_grams": 12,
            "carbohydrate_grams": 43, "fat_grams": 9, "confidence": 0.8,
            "warnings": [], "assumptions": []}}
            """.data(using: .utf8)!
        let requestDTO = makeRefinementRequest()

        let mock = MockPerformer { request in
            XCTAssertEqual(request.url, baseURL.appendingPathComponent("food-analysis"))
            XCTAssertEqual(request.httpMethod, "POST")
            XCTAssertEqual(request.value(forHTTPHeaderField: "Content-Type"), "application/json")
            XCTAssertEqual(request.value(forHTTPHeaderField: "Authorization"), "Bearer refinement-token")
            let body = try XCTUnwrap(request.httpBody)
            let json = try XCTUnwrap(JSONSerialization.jsonObject(with: body) as? [String: Any])
            XCTAssertNil(json["image"])
            XCTAssertNotNil(json["refinement"])
            let response = HTTPURLResponse(url: request.url!, statusCode: 200, httpVersion: nil, headerFields: nil)!
            return (responseJSON, response)
        }

        let service = FoodAnalysisService(
            baseURL: baseURL,
            session: mock,
            tokenProvider: StubTokenProvider(token: "refinement-token")
        )
        let estimate = try await service.refine(request: requestDTO)

        XCTAssertEqual(estimate.calories, 310)
    }

    func testRefinementMapsErrorsLikeInitialAnalysis() async {
        let errorJSON = #"{"error": {"code": "gateway_rate_limited", "message": "rate limited"}}"#
            .data(using: .utf8)!
        let mock = MockPerformer { request in
            let response = HTTPURLResponse(url: request.url!, statusCode: 429, httpVersion: nil, headerFields: nil)!
            return (errorJSON, response)
        }
        let service = FoodAnalysisService(baseURL: baseURL, session: mock)

        await assertThrowsFoodAnalysisError(try await service.refine(request: makeRefinementRequest()), .rateLimited)
    }

    func testRefinementTokenFailurePreventsNetworkRequest() async {
        let mock = MockPerformer { _ in
            XCTFail("The network layer must never be reached when token acquisition fails")
            throw URLError(.unknown)
        }
        let service = FoodAnalysisService(
            baseURL: baseURL,
            session: mock,
            tokenProvider: StubTokenProvider(error: URLError(.userAuthenticationRequired))
        )

        await assertThrowsFoodAnalysisError(
            try await service.refine(request: makeRefinementRequest()), .authenticationRequired
        )
    }

    private func makeRefinementRequest() -> FoodAnalysisRefinementRequestDTO {
        FoodAnalysisRefinementRequestDTO(
            foodDescription: "Eine Schüssel Reis",
            refinement: FoodAnalysisRefinementDTO(
                correctionText: "Nur die Hälfte gegessen",
                currentEstimate: FoodAnalysisRefinementCurrentEstimateDTO(
                    foodName: "Reisschüssel",
                    calories: 620,
                    proteinGrams: 24,
                    carbohydrateGrams: 86,
                    fatGrams: 18,
                    confidence: 0.72,
                    warnings: [],
                    assumptions: []
                ),
                sourceKind: .text,
                iteration: 1
            )
        )
    }

    // MARK: - Image analysis

    func testImageAnalysisSendsMultipartRequestWithImageAndDescription() async throws {
        let baseURL = baseURL
        let responseJSON = """
            {"estimate": {"food_name": "Pasta", "calories": 450, "protein_grams": 12,
            "carbohydrate_grams": 70, "fat_grams": 10, "confidence": 0.6, "warnings": []}}
            """.data(using: .utf8)!
        let imageData = Data("fake-jpeg-bytes".utf8)

        let mock = MockPerformer { request in
            XCTAssertEqual(request.url, baseURL.appendingPathComponent("food-analysis"))
            XCTAssertEqual(request.httpMethod, "POST")
            let contentType = try XCTUnwrap(request.value(forHTTPHeaderField: "Content-Type"))
            XCTAssertTrue(contentType.hasPrefix("multipart/form-data; boundary="))

            let body = try XCTUnwrap(request.httpBody)
            let bodyString = String(decoding: body, as: UTF8.self)
            XCTAssertTrue(bodyString.contains("name=\"image\""))
            XCTAssertTrue(bodyString.contains("Content-Type: image/jpeg"))
            XCTAssertTrue(bodyString.contains("name=\"food_description\""))
            XCTAssertTrue(bodyString.contains("a bowl of pasta"))
            XCTAssertTrue(body.range(of: imageData) != nil)

            let response = HTTPURLResponse(url: request.url!, statusCode: 200, httpVersion: nil, headerFields: nil)!
            return (responseJSON, response)
        }

        let service = FoodAnalysisService(baseURL: baseURL, session: mock)
        let estimate = try await service.analyzeImage(
            data: imageData, mimeType: "image/jpeg", description: "a bowl of pasta"
        )

        XCTAssertEqual(estimate.foodName, "Pasta")
    }

    func testImageOnlyAnalysisOmitsDescriptionField() async throws {
        let imageData = Data("fake-jpeg-bytes".utf8)
        let responseJSON = """
            {"estimate": {"food_name": "Pasta", "calories": 450, "protein_grams": 12,
            "carbohydrate_grams": 70, "fat_grams": 10, "confidence": 0.6, "warnings": []}}
            """.data(using: .utf8)!

        let mock = MockPerformer { request in
            let body = try XCTUnwrap(request.httpBody)
            let bodyString = String(decoding: body, as: UTF8.self)
            XCTAssertFalse(bodyString.contains("name=\"food_description\""))

            let response = HTTPURLResponse(url: request.url!, statusCode: 200, httpVersion: nil, headerFields: nil)!
            return (responseJSON, response)
        }

        let service = FoodAnalysisService(baseURL: baseURL, session: mock)
        _ = try await service.analyzeImage(data: imageData, mimeType: "image/jpeg", description: nil)
    }

    func testUnsupportedImageTypeErrorIsMapped() async {
        let errorJSON = #"{"error": {"code": "unsupported_media_type", "message": "nope"}}"#.data(using: .utf8)!
        let mock = MockPerformer { request in
            let response = HTTPURLResponse(url: request.url!, statusCode: 415, httpVersion: nil, headerFields: nil)!
            return (errorJSON, response)
        }
        let service = FoodAnalysisService(baseURL: baseURL, session: mock)

        do {
            _ = try await service.analyzeImage(data: Data("x".utf8), mimeType: "image/gif", description: nil)
            XCTFail("Expected an error")
        } catch let error as FoodAnalysisError {
            XCTAssertEqual(error, .unsupportedImageType)
        } catch {
            XCTFail("Expected FoodAnalysisError, got \(error)")
        }
    }

    func testImageTooLargeErrorIsMapped() async {
        let errorJSON = #"{"error": {"code": "image_too_large", "message": "too big"}}"#.data(using: .utf8)!
        let mock = MockPerformer { request in
            let response = HTTPURLResponse(url: request.url!, statusCode: 413, httpVersion: nil, headerFields: nil)!
            return (errorJSON, response)
        }
        let service = FoodAnalysisService(baseURL: baseURL, session: mock)

        do {
            _ = try await service.analyzeImage(data: Data("x".utf8), mimeType: "image/jpeg", description: nil)
            XCTFail("Expected an error")
        } catch let error as FoodAnalysisError {
            XCTAssertEqual(error, .imageTooLarge)
        } catch {
            XCTFail("Expected FoodAnalysisError, got \(error)")
        }
    }

    func testImageNetworkTimeoutIsMappedToTimeout() async {
        let mock = MockPerformer { _ in throw URLError(.timedOut) }
        let service = FoodAnalysisService(baseURL: baseURL, session: mock)

        do {
            _ = try await service.analyzeImage(data: Data("x".utf8), mimeType: "image/jpeg", description: nil)
            XCTFail("Expected an error")
        } catch let error as FoodAnalysisError {
            XCTAssertEqual(error, .timeout)
        } catch {
            XCTFail("Expected FoodAnalysisError, got \(error)")
        }
    }
}
