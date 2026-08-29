import XCTest

@testable import EntraAuthKit

/// Pure, MSAL-independent tests for the cached-account normalization used
/// by `MSALEntraTokenAcquirer.resolveCachedAccounts()`. No MSAL type is
/// needed here - only the raw identifier list MSAL's `allAccounts()`
/// would report (`MSALAccount.identifier` is itself optional).
final class EntraCachedAccountNormalizationTests: XCTestCase {
    func test_zeroAccounts_returnsNone() throws {
        let resolution = try EntraCachedAccountNormalization.resolution(forCachedAccountIdentifiers: [])
        XCTAssertEqual(resolution, .none)
    }

    func test_oneAccountWithIdentifier_returnsSingle() throws {
        let resolution = try EntraCachedAccountNormalization.resolution(forCachedAccountIdentifiers: ["account-a"])
        XCTAssertEqual(resolution, .single("account-a"))
    }

    func test_oneAccountWithoutIdentifier_failsClosed() {
        XCTAssertThrowsError(try EntraCachedAccountNormalization.resolution(forCachedAccountIdentifiers: [nil])) { error in
            XCTAssertEqual(error as? EntraTokenError, .unsupportedCachedAccountState)
        }
    }

    func test_twoAccountsWithIdentifiers_returnsMultiple() throws {
        let resolution = try EntraCachedAccountNormalization.resolution(
            forCachedAccountIdentifiers: ["account-a", "account-b"]
        )
        XCTAssertEqual(resolution, .multiple(["account-a", "account-b"]))
    }

    func test_twoAccountsOneMissingIdentifier_failsClosed() {
        // Must NOT silently become .single("account-a") - that would be
        // exactly the arbitrary-choice bug this normalization exists to
        // prevent.
        XCTAssertThrowsError(
            try EntraCachedAccountNormalization.resolution(forCachedAccountIdentifiers: ["account-a", nil])
        ) { error in
            XCTAssertEqual(error as? EntraTokenError, .unsupportedCachedAccountState)
        }
    }

    func test_multipleAccountsAllMissingIdentifiers_failsClosed() {
        // Must NOT silently become .none - that would incorrectly permit
        // an interactive login while cached (but unusable) accounts exist.
        XCTAssertThrowsError(
            try EntraCachedAccountNormalization.resolution(forCachedAccountIdentifiers: [nil, nil])
        ) { error in
            XCTAssertEqual(error as? EntraTokenError, .unsupportedCachedAccountState)
        }
    }

    func test_blankIdentifierIsTreatedAsMissing() {
        XCTAssertThrowsError(try EntraCachedAccountNormalization.resolution(forCachedAccountIdentifiers: [""])) { error in
            XCTAssertEqual(error as? EntraTokenError, .unsupportedCachedAccountState)
        }
    }
}
