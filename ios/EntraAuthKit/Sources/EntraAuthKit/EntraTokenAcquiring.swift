import Foundation

/// Normalized, MSAL-independent outcome categories for token acquisition.
/// `EntraAuthService` maps every underlying MSAL `NSError` onto one of
/// these before it ever reaches `FoodAnalysisKit` or UI code, so nothing
/// above this adapter boundary needs to know about `MSALErrorDomain` or
/// MSAL error codes.
public enum EntraTokenError: Error, Equatable, Sendable {
    /// The interactive sign-in sheet was dismissed/cancelled by the user.
    case userCancelled
    /// No network path to the identity provider.
    case noConnection
    /// Silent acquisition needs interaction, and an interactive attempt
    /// either was not possible here (e.g. no presentation anchor) or also
    /// failed for a reason other than cancellation.
    case interactionRequired
    /// Configuration (tenant/client id/scope/redirect URI) is missing or
    /// MSAL rejected it (e.g. malformed redirect URI).
    case configurationInvalid
    /// MSAL's own account cache/keychain query itself failed (e.g. a
    /// Keychain read error) - distinct from a genuinely empty cache. Must
    /// never be silently collapsed into "no account exists", since that
    /// would incorrectly trigger an interactive login on every transient
    /// cache failure.
    case accountLookupFailed
    /// MSAL's cache has more than one signed-in account and none has been
    /// selected yet (see `EntraAuthService`'s account-selection policy).
    /// This app never picks one arbitrarily.
    case multipleAccountsRequireSelection
    /// At least one cached MSAL account exists but lacks the identifier
    /// this app's account-selection strategy requires to remember/resolve
    /// it deterministically. Never silently dropped - dropping it could
    /// otherwise turn two cached accounts into what looks like one, or a
    /// single identifier-less account into what looks like none.
    case unsupportedCachedAccountState
    /// Any other MSAL failure, deliberately not detailed further here -
    /// raw MSAL error text/codes must never reach the UI layer.
    case unknown
}

/// The result of MSAL's cached-account enumeration, before any silent/
/// interactive token acquisition is attempted. Zero and exactly-one
/// accounts have an unambiguous next step; more than one requires an
/// explicit selection this app does not yet make automatically (see
/// `EntraAuthService.acquireAccessToken()`).
public enum EntraAccountResolution: Equatable, Sendable {
    case none
    case single(String)
    case multiple([String])
}

/// Pure, MSAL-independent normalization from raw cached-account
/// identifiers (as reported by MSAL's `allAccounts()`, one optional
/// `String` per account - `MSALAccount.identifier` is itself optional) to
/// a deterministic `EntraAccountResolution`.
///
/// The full collection is evaluated before any account is discarded: an
/// identifier-less account is never silently dropped, since that could
/// otherwise turn two cached accounts into what looks like a single
/// account, or a lone identifier-less account into what looks like no
/// account at all - both would violate the "never choose an account
/// arbitrarily" policy. If any cached account lacks a usable identifier,
/// normalization fails closed for the whole result rather than picking
/// among the remaining ones.
public enum EntraCachedAccountNormalization {
    public static func resolution(forCachedAccountIdentifiers identifiers: [String?]) throws -> EntraAccountResolution {
        guard !identifiers.isEmpty else { return .none }

        var resolved: [String] = []
        resolved.reserveCapacity(identifiers.count)
        for identifier in identifiers {
            guard let identifier, !identifier.isEmpty else {
                throw EntraTokenError.unsupportedCachedAccountState
            }
            resolved.append(identifier)
        }

        return resolved.count == 1 ? .single(resolved[0]) : .multiple(resolved)
    }
}

/// Result of a completed interactive sign-in: both the access token and
/// the account identifier MSAL just created/reused, so the caller can
/// remember which account to use next time (see `EntraAccountStoring`).
public struct EntraInteractiveResult: Equatable, Sendable {
    public let accessToken: String
    public let accountIdentifier: String

    public init(accessToken: String, accountIdentifier: String) {
        self.accessToken = accessToken
        self.accountIdentifier = accountIdentifier
    }
}

/// The smallest seam around MSAL needed by `EntraAuthService`, so its
/// account-selection and silent-then-interactive orchestration logic can
/// be unit-tested with a fake instead of exercising real MSAL/network/UI
/// code. The only type that imports `MSAL` and conforms to this is
/// `ios/Trainingsplan/Entra/MSALEntraTokenAcquirer.swift` in the app
/// target (this package has no MSAL dependency at all).
public protocol EntraTokenAcquiring: Sendable {
    /// Enumerates MSAL's cached accounts. Must throw
    /// `EntraTokenError.accountLookupFailed` (never return `.none`) if the
    /// underlying cache/keychain query itself fails - only a genuinely
    /// empty cache is `.none`.
    func resolveCachedAccounts() async throws -> EntraAccountResolution

    /// Whether the given previously-selected account identifier still
    /// resolves in MSAL's cache. `false` only for a genuine "not found";
    /// throws `EntraTokenError.accountLookupFailed` for any other lookup
    /// failure - never conflates the two.
    func accountExists(identifier: String) async throws -> Bool

    /// Attempts silent (no UI) token acquisition for the given cached
    /// account and scope. Throws `EntraTokenError.interactionRequired` if
    /// MSAL reports the cached session can't satisfy this silently, or
    /// `EntraTokenError.accountLookupFailed` if resolving the account
    /// itself failed (as opposed to genuinely not existing).
    func acquireTokenSilently(accountIdentifier: String, scope: String) async throws -> String

    /// Presents the interactive Microsoft sign-in UI and returns the
    /// resulting access token together with the account identifier to
    /// remember for subsequent silent requests.
    func acquireTokenInteractively(scope: String) async throws -> EntraInteractiveResult
}

/// Non-secret app-state persistence for "which MSAL account this
/// single-user app should use for silent acquisition" - an opaque MSAL
/// account identifier (not an access token, not a refresh token, not a
/// secret). MSAL's own keychain-backed cache remains the only place any
/// token ever lives; this only remembers *which* cached account to ask
/// for.
public protocol EntraAccountStoring: Sendable {
    func loadSelectedAccountIdentifier() -> String?
    func saveSelectedAccountIdentifier(_ identifier: String)
    func clearSelectedAccountIdentifier()
}

/// `UserDefaults`-backed `EntraAccountStoring` - the smallest existing iOS
/// persistence mechanism suitable for a non-secret opaque identifier
/// string. Never used for tokens or any other secret.
public final class UserDefaultsEntraAccountStore: EntraAccountStoring, @unchecked Sendable {
    private static let key = "EntraAuthKit.selectedAccountIdentifier"

    private let defaults: UserDefaults

    public init(defaults: UserDefaults = .standard) {
        self.defaults = defaults
    }

    public func loadSelectedAccountIdentifier() -> String? {
        defaults.string(forKey: Self.key)
    }

    public func saveSelectedAccountIdentifier(_ identifier: String) {
        defaults.set(identifier, forKey: Self.key)
    }

    public func clearSelectedAccountIdentifier() {
        defaults.removeObject(forKey: Self.key)
    }
}
