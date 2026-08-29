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
    /// Any other MSAL failure, deliberately not detailed further here -
    /// raw MSAL error text/codes must never reach the UI layer.
    case unknown
}

/// The smallest seam around MSAL needed by `EntraAuthService`, so its
/// silent-then-interactive orchestration logic can be unit-tested with a
/// fake instead of exercising real MSAL/network/UI code. The only type
/// that imports `MSAL` and conforms to this is
/// `ios/Trainingsplan/Entra/MSALEntraTokenAcquirer.swift` in the app
/// target (this package has no MSAL dependency at all).
public protocol EntraTokenAcquiring: Sendable {
    /// Identifier of a previously signed-in account usable for silent
    /// acquisition, if MSAL's own token cache already has one. This app is
    /// single-user, so "the first cached account" is the only account it
    /// ever expects; never persisted by this app itself (see
    /// `EntraAuthService`'s "no manual access-token persistence").
    func currentAccountIdentifier() async throws -> String?

    /// Attempts silent (no UI) token acquisition for the given cached
    /// account and scope. Throws `EntraTokenError.interactionRequired` if
    /// MSAL reports the cached session can't satisfy this silently.
    func acquireTokenSilently(accountIdentifier: String, scope: String) async throws -> String

    /// Presents the interactive Microsoft sign-in UI and returns the
    /// resulting access token.
    func acquireTokenInteractively(scope: String) async throws -> String
}
