import FoodAnalysisKit
import XCTest

@testable import EntraAuthKit

/// All tests here use a fake `EntraTokenAcquiring`/`EntraAccountStoring` -
/// no MSAL, no network, no Microsoft/Azure endpoint is ever contacted.
final class EntraAuthServiceTests: XCTestCase {
    private let scope = "api://backend-app-id/FoodAnalysis.Access"

    private func makeService(
        acquirer: FakeTokenAcquirer, accountStore: FakeAccountStore = FakeAccountStore()
    ) -> EntraAuthService {
        let configuration = EntraConfiguration(
            tenantId: "test-tenant-id",
            clientId: "test-client-id",
            apiScope: scope,
            redirectUri: "msauth.com.example.app://auth"
        )
        return EntraAuthService(configuration: configuration, acquirer: acquirer, accountStore: accountStore)
    }

    // MARK: - Exactly one cached account (deterministic silent path)

    func test_acquireAccessToken_oneAccount_usesItSilentlyAndRemembersIt() async throws {
        let acquirer = FakeTokenAcquirer(resolveResult: .success(.single("cached-account")), silentResult: .success("silent-token"))
        let accountStore = FakeAccountStore()
        let service = makeService(acquirer: acquirer, accountStore: accountStore)

        let token = try await service.acquireAccessToken()

        XCTAssertEqual(token, "silent-token")
        XCTAssertEqual(acquirer.silentCallCount, 1)
        XCTAssertEqual(acquirer.interactiveCallCount, 0)
        XCTAssertEqual(acquirer.lastSilentAccountIdentifier, "cached-account")
        XCTAssertEqual(accountStore.selectedIdentifier, "cached-account")
    }

    func test_acquireAccessToken_requestsScopeFromConfiguration() async throws {
        let acquirer = FakeTokenAcquirer(resolveResult: .success(.single("cached-account")), silentResult: .success("silent-token"))
        let service = makeService(acquirer: acquirer)

        _ = try await service.acquireAccessToken()

        XCTAssertEqual(acquirer.lastRequestedScope, scope)
    }

    // MARK: - Zero cached accounts (interactive path)

    func test_acquireAccessToken_zeroAccounts_goesInteractiveDirectly() async throws {
        let acquirer = FakeTokenAcquirer(
            resolveResult: .success(.none),
            interactiveResult: .success(EntraInteractiveResult(accessToken: "first-sign-in-token", accountIdentifier: "new-account"))
        )
        let accountStore = FakeAccountStore()
        let service = makeService(acquirer: acquirer, accountStore: accountStore)

        let token = try await service.acquireAccessToken()

        XCTAssertEqual(token, "first-sign-in-token")
        XCTAssertEqual(acquirer.silentCallCount, 0)
        XCTAssertEqual(acquirer.interactiveCallCount, 1)
        XCTAssertEqual(accountStore.selectedIdentifier, "new-account")
    }

    // MARK: - Multiple cached accounts without a selection (normalized error)

    func test_acquireAccessToken_multipleAccountsWithoutSelection_failsWithNormalizedError() async {
        let acquirer = FakeTokenAcquirer(resolveResult: .success(.multiple(["account-a", "account-b"])))
        let service = makeService(acquirer: acquirer)

        do {
            _ = try await service.acquireAccessToken()
            XCTFail("Expected multipleAccountsRequireSelection to throw")
        } catch let error as EntraTokenError {
            XCTAssertEqual(error, .multipleAccountsRequireSelection)
        } catch {
            XCTFail("Expected EntraTokenError, got \(error)")
        }
        XCTAssertEqual(acquirer.silentCallCount, 0)
        XCTAssertEqual(acquirer.interactiveCallCount, 0)
    }

    // MARK: - Account/cache lookup failures propagate, never trigger interactive login

    func test_acquireAccessToken_cacheLookupFailure_propagatesWithoutInteractiveLogin() async {
        let acquirer = FakeTokenAcquirer(resolveResult: .failure(EntraTokenError.accountLookupFailed))
        let service = makeService(acquirer: acquirer)

        do {
            _ = try await service.acquireAccessToken()
            XCTFail("Expected accountLookupFailed to throw")
        } catch let error as EntraTokenError {
            XCTAssertEqual(error, .accountLookupFailed)
        } catch {
            XCTFail("Expected EntraTokenError, got \(error)")
        }
        XCTAssertEqual(acquirer.silentCallCount, 0)
        XCTAssertEqual(acquirer.interactiveCallCount, 0)
    }

    func test_acquireAccessToken_selectedIdentifierLookupFailure_propagatesWithoutClearingOrInteractiveLogin() async {
        let accountStore = FakeAccountStore(initialSelectedIdentifier: "stored-account")
        let acquirer = FakeTokenAcquirer(accountExistsResults: ["stored-account": .failure(EntraTokenError.accountLookupFailed)])
        let service = makeService(acquirer: acquirer, accountStore: accountStore)

        do {
            _ = try await service.acquireAccessToken()
            XCTFail("Expected accountLookupFailed to throw")
        } catch let error as EntraTokenError {
            XCTAssertEqual(error, .accountLookupFailed)
        } catch {
            XCTFail("Expected EntraTokenError, got \(error)")
        }
        // A genuine lookup error is not "not found" - the stored selection
        // must not be cleared, and no interactive login must be attempted.
        XCTAssertEqual(accountStore.selectedIdentifier, "stored-account")
        XCTAssertEqual(acquirer.interactiveCallCount, 0)
    }

    // MARK: - Selected account identifier

    func test_acquireAccessToken_selectedIdentifierResolves_usesItDirectlyWithoutReResolvingCache() async throws {
        let accountStore = FakeAccountStore(initialSelectedIdentifier: "stored-account")
        let acquirer = FakeTokenAcquirer(
            accountExistsResults: ["stored-account": .success(true)],
            silentResult: .success("token-for-stored-account")
        )
        let service = makeService(acquirer: acquirer, accountStore: accountStore)

        let token = try await service.acquireAccessToken()

        XCTAssertEqual(token, "token-for-stored-account")
        XCTAssertEqual(acquirer.lastSilentAccountIdentifier, "stored-account")
        XCTAssertEqual(acquirer.resolveCachedAccountsCallCount, 0)
    }

    func test_acquireAccessToken_selectedIdentifierNoLongerResolving_clearsAndReResolvesSafely() async throws {
        let accountStore = FakeAccountStore(initialSelectedIdentifier: "stale-account")
        let acquirer = FakeTokenAcquirer(
            resolveResult: .success(.single("fresh-account")),
            accountExistsResults: ["stale-account": .success(false)],
            silentResult: .success("fresh-token")
        )
        let service = makeService(acquirer: acquirer, accountStore: accountStore)

        let token = try await service.acquireAccessToken()

        XCTAssertEqual(token, "fresh-token")
        XCTAssertEqual(acquirer.lastSilentAccountIdentifier, "fresh-account")
        XCTAssertEqual(accountStore.selectedIdentifier, "fresh-account")
        XCTAssertGreaterThanOrEqual(accountStore.clearCallCount, 1)
    }

    // MARK: - Interactive fallback on interactionRequired

    func test_acquireAccessToken_fallsBackToInteractiveWhenSilentRequiresInteraction() async throws {
        let acquirer = FakeTokenAcquirer(
            resolveResult: .success(.single("cached-account")),
            silentResult: .failure(EntraTokenError.interactionRequired),
            interactiveResult: .success(EntraInteractiveResult(accessToken: "interactive-token", accountIdentifier: "cached-account"))
        )
        let service = makeService(acquirer: acquirer)

        let token = try await service.acquireAccessToken()

        XCTAssertEqual(token, "interactive-token")
        XCTAssertEqual(acquirer.silentCallCount, 1)
        XCTAssertEqual(acquirer.interactiveCallCount, 1)
    }

    // MARK: - User cancellation

    func test_acquireAccessToken_propagatesUserCancellation() async {
        let acquirer = FakeTokenAcquirer(
            resolveResult: .success(.none),
            interactiveResult: .failure(EntraTokenError.userCancelled)
        )
        let service = makeService(acquirer: acquirer)

        do {
            _ = try await service.acquireAccessToken()
            XCTFail("Expected cancellation to throw")
        } catch let error as EntraTokenError {
            XCTAssertEqual(error, .userCancelled)
        } catch {
            XCTFail("Expected EntraTokenError, got \(error)")
        }
    }

    // MARK: - Error normalization

    func test_acquireAccessToken_propagatesNormalizedNetworkError() async {
        let acquirer = FakeTokenAcquirer(resolveResult: .success(.none), interactiveResult: .failure(EntraTokenError.noConnection))
        let service = makeService(acquirer: acquirer)

        do {
            _ = try await service.acquireAccessToken()
            XCTFail("Expected failure to throw")
        } catch let error as EntraTokenError {
            XCTAssertEqual(error, .noConnection)
        } catch {
            XCTFail("Expected EntraTokenError, got \(error)")
        }
    }

    func test_acquireAccessToken_doesNotRetryInteractiveAfterNonInteractionSilentFailure() async {
        // A silent failure that is NOT `.interactionRequired` (e.g. a
        // transient/unknown MSAL error) must propagate directly - only
        // `.interactionRequired` triggers the interactive fallback. An
        // unrelated silent failure must never be masked by an unrelated
        // interactive success.
        let acquirer = FakeTokenAcquirer(
            resolveResult: .success(.single("cached-account")),
            silentResult: .failure(EntraTokenError.unknown),
            interactiveResult: .success(EntraInteractiveResult(accessToken: "must-not-be-used", accountIdentifier: "cached-account"))
        )
        let service = makeService(acquirer: acquirer)

        do {
            _ = try await service.acquireAccessToken()
            XCTFail("Expected the non-interactionRequired silent failure to propagate")
        } catch let error as EntraTokenError {
            XCTAssertEqual(error, .unknown)
        } catch {
            XCTFail("Expected EntraTokenError, got \(error)")
        }
        XCTAssertEqual(acquirer.interactiveCallCount, 0)
    }

    // MARK: - Bearer token attached exactly once / no header on failure

    func test_foodAnalysisService_attachesBearerTokenExactlyOnce() async throws {
        let acquirer = FakeTokenAcquirer(resolveResult: .success(.single("cached-account")), silentResult: .success("the-token"))
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
        let acquirer = FakeTokenAcquirer(
            resolveResult: .success(.none), interactiveResult: .failure(EntraTokenError.userCancelled)
        )
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
        } catch {
            XCTFail("Expected FoodAnalysisError, got \(error)")
        }

        // The request must never have been sent at all once token
        // acquisition failed - not sent-without-a-header.
        XCTAssertEqual(session.capturedRequests.count, 0)
    }
}

// MARK: - Test doubles

private final class FakeTokenAcquirer: EntraTokenAcquiring, @unchecked Sendable {
    private let resolveResult: Result<EntraAccountResolution, Error>
    private let accountExistsResults: [String: Result<Bool, Error>]
    private let silentResult: Result<String, Error>?
    private let interactiveResult: Result<EntraInteractiveResult, Error>?

    private(set) var resolveCachedAccountsCallCount = 0
    private(set) var silentCallCount = 0
    private(set) var interactiveCallCount = 0
    private(set) var lastRequestedScope: String?
    private(set) var lastSilentAccountIdentifier: String?

    init(
        resolveResult: Result<EntraAccountResolution, Error> = .success(.none),
        accountExistsResults: [String: Result<Bool, Error>] = [:],
        silentResult: Result<String, Error>? = nil,
        interactiveResult: Result<EntraInteractiveResult, Error>? = nil
    ) {
        self.resolveResult = resolveResult
        self.accountExistsResults = accountExistsResults
        self.silentResult = silentResult
        self.interactiveResult = interactiveResult
    }

    func resolveCachedAccounts() async throws -> EntraAccountResolution {
        resolveCachedAccountsCallCount += 1
        return try resolveResult.get()
    }

    func accountExists(identifier: String) async throws -> Bool {
        guard let result = accountExistsResults[identifier] else {
            XCTFail("accountExists called for unexpected identifier \(identifier)")
            return false
        }
        return try result.get()
    }

    func acquireTokenSilently(accountIdentifier: String, scope: String) async throws -> String {
        silentCallCount += 1
        lastRequestedScope = scope
        lastSilentAccountIdentifier = accountIdentifier
        guard let silentResult else {
            XCTFail("acquireTokenSilently called unexpectedly")
            throw EntraTokenError.unknown
        }
        return try silentResult.get()
    }

    func acquireTokenInteractively(scope: String) async throws -> EntraInteractiveResult {
        interactiveCallCount += 1
        lastRequestedScope = scope
        guard let interactiveResult else {
            XCTFail("acquireTokenInteractively called unexpectedly")
            throw EntraTokenError.unknown
        }
        return try interactiveResult.get()
    }
}

private final class FakeAccountStore: EntraAccountStoring, @unchecked Sendable {
    private(set) var selectedIdentifier: String?
    private(set) var clearCallCount = 0

    init(initialSelectedIdentifier: String? = nil) {
        self.selectedIdentifier = initialSelectedIdentifier
    }

    func loadSelectedAccountIdentifier() -> String? {
        selectedIdentifier
    }

    func saveSelectedAccountIdentifier(_ identifier: String) {
        selectedIdentifier = identifier
    }

    func clearSelectedAccountIdentifier() {
        selectedIdentifier = nil
        clearCallCount += 1
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
