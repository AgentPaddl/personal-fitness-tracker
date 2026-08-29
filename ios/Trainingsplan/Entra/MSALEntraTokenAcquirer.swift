import EntraAuthKit
import MSAL
import UIKit

/// The only file in this app that imports `MSAL` directly. Wraps a single
/// `MSALPublicClientApplication` (native/public client - no client secret,
/// ever) and adapts its completion-block API to `EntraTokenAcquiring`'s
/// small async surface, translating MSAL's `NSError`s to `EntraTokenError`
/// so nothing above this file needs to know MSAL's error domain/codes.
public final class MSALEntraTokenAcquirer: EntraTokenAcquiring {
    private let application: MSALPublicClientApplication

    /// Throws if `configuration` is invalid (e.g. a malformed authority or
    /// redirect URI) - callers must treat that as a configuration failure,
    /// never fall back to an unconfigured/unauthenticated state silently.
    public init(configuration: EntraConfiguration) throws {
        guard let authorityURL = URL(string: configuration.authority),
            let authority = try? MSALAADAuthority(url: authorityURL)
        else {
            throw EntraTokenError.configurationInvalid
        }
        let msalConfig = MSALPublicClientApplicationConfig(
            clientId: configuration.clientId,
            redirectUri: configuration.redirectUri,
            authority: authority
        )
        do {
            self.application = try MSALPublicClientApplication(configuration: msalConfig)
        } catch {
            throw EntraTokenError.configurationInvalid
        }
    }

    public func resolveCachedAccounts() async throws -> EntraAccountResolution {
        // Genuine cache/keychain read failures must never be reported as
        // "no accounts" - that would incorrectly trigger an interactive
        // login instead of surfacing the real underlying problem.
        let accounts: [MSALAccount]
        do {
            accounts = try application.allAccounts()
        } catch {
            throw EntraTokenError.accountLookupFailed
        }
        // `MSALAccount.identifier` is optional in MSAL's API; an account
        // without one cannot be remembered/resolved by this app and is
        // dropped rather than force-unwrapped.
        let identifiers = accounts.compactMap(\.identifier)
        switch identifiers.count {
        case 0:
            return .none
        case 1:
            return .single(identifiers[0])
        default:
            return .multiple(identifiers)
        }
    }

    public func accountExists(identifier: String) async throws -> Bool {
        // Implemented via `allAccounts()` rather than `accountForIdentifier`,
        // since the latter throws indistinguishably for both "not found"
        // and genuine lookup failures in this MSAL version - `allAccounts()`
        // lets a real cache error (throws) be told apart from a clean
        // "not present" answer (a normal, non-throwing `false`).
        let accounts: [MSALAccount]
        do {
            accounts = try application.allAccounts()
        } catch {
            throw EntraTokenError.accountLookupFailed
        }
        return accounts.contains { $0.identifier == identifier }
    }

    public func acquireTokenSilently(accountIdentifier: String, scope: String) async throws -> String {
        let account: MSALAccount
        do {
            account = try application.account(forIdentifier: accountIdentifier)
        } catch {
            // Callers only reach this point after already confirming via
            // `accountExists`/`resolveCachedAccounts` that this identifier
            // is genuinely present, so a throw here is a real lookup
            // failure - never silently treated as "needs interaction".
            throw EntraTokenError.accountLookupFailed
        }
        let parameters = MSALSilentTokenParameters(scopes: [scope], account: account)
        return try await withCheckedThrowingContinuation { continuation in
            application.acquireTokenSilent(with: parameters) { result, error in
                if let result {
                    continuation.resume(returning: result.accessToken)
                } else {
                    continuation.resume(throwing: Self.mapError(error))
                }
            }
        }
    }

    @MainActor
    public func acquireTokenInteractively(scope: String) async throws -> EntraInteractiveResult {
        guard let presentationAnchor = Self.currentPresentationAnchor() else {
            // Cannot present the Microsoft sign-in UI at all right now
            // (e.g. no active foreground scene) - fail closed rather than
            // silently skipping authentication.
            throw EntraTokenError.interactionRequired
        }
        let webviewParameters = MSALWebviewParameters(authPresentationViewController: presentationAnchor)
        let parameters = MSALInteractiveTokenParameters(scopes: [scope], webviewParameters: webviewParameters)
        return try await withCheckedThrowingContinuation { continuation in
            application.acquireToken(with: parameters) { result, error in
                guard let result else {
                    continuation.resume(throwing: Self.mapError(error))
                    return
                }
                guard let accountIdentifier = result.account.identifier else {
                    // Unexpected MSAL state (successful sign-in but no
                    // usable account identifier to remember) - never
                    // silently proceed without one to store.
                    continuation.resume(throwing: EntraTokenError.unknown)
                    return
                }
                continuation.resume(
                    returning: EntraInteractiveResult(accessToken: result.accessToken, accountIdentifier: accountIdentifier)
                )
            }
        }
    }

    /// Handles the redirect URI callback when the app is reopened via
    /// `msauth.<bundle-id>://auth` (see `TrainingsplanApp`'s `onOpenURL`).
    /// Must be forwarded exactly this way for MSAL's interactive flow to
    /// ever complete.
    public static func handleRedirect(url: URL) -> Bool {
        MSALPublicClientApplication.handleMSALResponse(url, sourceApplication: nil)
    }

    @MainActor
    private static func currentPresentationAnchor() -> UIViewController? {
        UIApplication.shared.connectedScenes
            .compactMap { $0 as? UIWindowScene }
            .flatMap { $0.windows }
            .first { $0.isKeyWindow }?
            .rootViewController
    }

    private static func mapError(_ error: Error?) -> EntraTokenError {
        guard let nsError = error as NSError? else { return .unknown }
        if nsError.domain == MSALErrorDomain {
            switch nsError.code {
            case MSALError.interactionRequired.rawValue:
                return .interactionRequired
            case MSALError.userCanceled.rawValue:
                return .userCancelled
            default:
                break
            }
        }
        if nsError.domain == NSURLErrorDomain {
            return .noConnection
        }
        return .unknown
    }
}
