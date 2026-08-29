import FoodAnalysisKit
import XCTest

@testable import EntraAuthKit

/// All tests here use a fake `EntraTokenAcquiring` - no MSAL, no network,
/// no Microsoft/Azure endpoint is ever contacted.
final class EntraAuthServiceTests: XCTestCase {
    private let scope = "api://backend-app-id/FoodAnalysis.Access"

    private func makeService(acquirer: FakeTokenAcquirer) -> EntraAuthService {
        let configuration = EntraConfiguration(
            tenantId: "test-tenant-id",
            clientId: "test-client-id",
            apiScope: scope,
            redirectUri: "msauth.com.example.app://auth"
        )
        return EntraAuthService(configuration: configuration, acquirer: acquirer)
    }

    // MARK: - Silent acquisition

    func test_acquireAccessToken_returnsSilentTokenWhenCachedAccountExists() async throws {
        let acquirer = FakeTokenAcquirer(cachedAccountIdentifier: "cached-account", silentResult: .success("silent-token"))
        let service = makeService(acquirer: acquirer)

        let token = try await service.acquireAccessToken()

        XCTAssertEqual(token, "silent-token")
        XCTAssertEqual(acquirer.silentCallCount, 1)
        XCTAssertEqual(acquirer.interactiveCallCount, 0)
    }

    func test_acquireAccessToken_requestsScopeFromConfiguration() async throws {
        let acquirer = FakeTokenAcquirer(cachedAccountIdentifier: "cached-account", silentResult: .success("silent-token"))
        let service = makeService(acquirer: acquirer)

        _ = try await service.acquireAccessToken()

        XCTAssertEqual(acquirer.lastRequestedScope, scope)
    }

    // MARK: - Interactive fallback

    func test_acquireAccessToken_fallsBackToInteractiveWhenSilentRequiresInteraction() async throws {
        let acquirer = FakeTokenAcquirer(
            cachedAccountIdentifier: "cached-account",
            silentResult: .failure(EntraTokenError.interactionRequired),
            interactiveResult: .success("interactive-token")
        )
        let service = makeService(acquirer: acquirer)

        let token = try await service.acquireAccessToken()

        XCTAssertEqual(token, "interactive-token")
        XCTAssertEqual(acquirer.silentCallCount, 1)
        XCTAssertEqual(acquirer.interactiveCallCount, 1)
    }

    func test_acquireAccessToken_goesInteractiveDirectlyWithNoCachedAccount() async throws {
        let acquirer = FakeTokenAcquirer(cachedAccountIdentifier: nil, interactiveResult: .success("first-sign-in-token"))
        let service = makeService(acquirer: acquirer)

        let token = try await service.acquireAccessToken()

        XCTAssertEqual(token, "first-sign-in-token")
        XCTAssertEqual(acquirer.silentCallCount, 0)
        XCTAssertEqual(acquirer.interactiveCallCount, 1)
    }

    func test_acquireAccessToken_interactiveSuccessAfterInteractionRequired() async throws {
        let acquirer = FakeTokenAcquirer(
            cachedAccountIdentifier: "cached-account",
            silentResult: .failure(EntraTokenError.interactionRequired),
            interactiveResult: .success("refreshed-token")
        )
        let service = makeService(acquirer: acquirer)

        let token = try await service.acquireAccessToken()

        XCTAssertEqual(token, "refreshed-token")
    }

    // MARK: - User cancellation

    func test_acquireAccessToken_propagatesUserCancellation() async {
        let acquirer = FakeTokenAcquirer(
            cachedAccountIdentifier: nil,
            interactiveResult: .failure(EntraTokenError.userCancelled)
        )
        let service = makeService(acquirer: acquirer)

        do {
            _ = try await service.acquireAccessToken()
            XCTFail("Expected cancellation to throw")
        } catch let error as EntraTokenError {
            XCTAssertEqual(error, .userCancelled)
        }
    }

    // MARK: - Error normalization

    func test_acquireAccessToken_propagatesNormalizedNetworkError() async {
        let acquirer = FakeTokenAcquirer(cachedAccountIdentifier: nil, interactiveResult: .failure(EntraTokenError.noConnection))
        let service = makeService(acquirer: acquirer)

        do {
            _ = try await service.acquireAccessToken()
            XCTFail("Expected failure to throw")
        } catch let error as EntraTokenError {
            XCTAssertEqual(error, .noConnection)
        }
    }

    func test_acquireAccessToken_doesNotRetryInteractiveAfterNonInteractionSilentFailure() async {
        // A silent failure that is NOT `.interactionRequired` (e.g. a
        // transient/unknown MSAL error) must propagate directly - only
        // `.interactionRequired` triggers the interactive fallback. An
        // unrelated silent failure must never be masked by an unrelated
        // interactive success.
        let acquirer = FakeTokenAcquirer(
            cachedAccountIdentifier: "cached-account",
            silentResult: .failure(EntraTokenError.unknown),
            interactiveResult: .success("must-not-be-used")
        )
        let service = makeService(acquirer: acquirer)

        do {
            _ = try await service.acquireAccessToken()
            XCTFail("Expected the non-interactionRequired silent failure to propagate")
        } catch let error as EntraTokenError {
            XCTAssertEqual(error, .unknown)
        }
        XCTAssertEqual(acquirer.interactiveCallCount, 0)
    }

    // MARK: - Bearer token attached exactly once / no header on failure

    func test_foodAnalysisService_attachesBearerTokenExactlyOnce() async throws {
        let acquirer = FakeTokenAcquirer(cachedAccountIdentifier: "cached-account", silentResult: .success("the-token"))
        let entraService = makeService(acquirer: acquirer)
        let session = RecordingURLSession()
        let service = FoodAnalysisService(
            baseURL: URL(string: "https://backend.example.com/api")!,
            session: session,
            tokenProvider: entraService
        )

        _ = try? await service.analyze(description: "Apfel")

        XCTAssertEqual(session.capturedRequests.count, 1)
        let authHeaders = session.capturedRequests[0].allHTTPHeaderFields?
            .filter { $0.key == "Authorization" }
        XCTAssertEqual(authHeaders?.count, 1)
        XCTAssertEqual(authHeaders?["Authorization"], "Bearer the-token")
    }

    func test_foodAnalysisService_sendsNoAuthorizationHeaderWhenTokenAcquisitionFails() async throws {
        let acquirer = FakeTokenAcquirer(cachedAccountIdentifier: nil, interactiveResult: .failure(EntraTokenError.userCancelled))
        let entraService = makeService(acquirer: acquirer)
        let session = RecordingURLSession()
        let service = FoodAnalysisService(
            baseURL: URL(string: "https://backend.example.com/api")!,
            session: session,
            tokenProvider: entraService
        )

        do {
            _ = try await service.analyze(description: "Apfel")
            XCTFail("Expected authenticationRequired")
        } catch let error as FoodAnalysisError {
            XCTAssertEqual(error, .authenticationRequired)
        }

        // The request must never have been sent at all once token
        // acquisition failed - not sent-without-a-header.
        XCTAssertEqual(session.capturedRequests.count, 0)
    }
}

// MARK: - Test doubles

private final class FakeTokenAcquirer: EntraTokenAcquiring, @unchecked Sendable {
    private let cachedAccountIdentifier: String?
    private let silentResult: Result<String, Error>?
    private let interactiveResult: Result<String, Error>?

    private(set) var silentCallCount = 0
    private(set) var interactiveCallCount = 0
    private(set) var lastRequestedScope: String?

    init(
        cachedAccountIdentifier: String?,
        silentResult: Result<String, Error>? = nil,
        interactiveResult: Result<String, Error>? = nil
    ) {
        self.cachedAccountIdentifier = cachedAccountIdentifier
        self.silentResult = silentResult
        self.interactiveResult = interactiveResult
    }

    func currentAccountIdentifier() async throws -> String? {
        cachedAccountIdentifier
    }

    func acquireTokenSilently(accountIdentifier: String, scope: String) async throws -> String {
        silentCallCount += 1
        lastRequestedScope = scope
        guard let silentResult else {
            XCTFail("acquireTokenSilently called unexpectedly")
            throw EntraTokenError.unknown
        }
        return try silentResult.get()
    }

    func acquireTokenInteractively(scope: String) async throws -> String {
        interactiveCallCount += 1
        lastRequestedScope = scope
        guard let interactiveResult else {
            XCTFail("acquireTokenInteractively called unexpectedly")
            throw EntraTokenError.unknown
        }
        return try interactiveResult.get()
    }
}

/// Records every outgoing request instead of performing real networking.
private final class RecordingURLSession: URLRequestPerforming, @unchecked Sendable {
    private(set) var capturedRequests: [URLRequest] = []

    func data(for request: URLRequest) async throws -> (Data, URLResponse) {
        capturedRequests.append(request)
        let json = """
        {"estimate":{"food_name":"Apfel","calories":95,"protein_grams":0.5,\
        "carbohydrate_grams":25,"fat_grams":0.3,"confidence":0.9,"warnings":[]}}
        """
        let response = HTTPURLResponse(url: request.url!, statusCode: 200, httpVersion: nil, headerFields: nil)!
        return (Data(json.utf8), response)
    }
}
