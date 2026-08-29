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

    public func currentAccountIdentifier() async throws -> String? {
        // Single-user app: MSAL's own keychain-backed cache is the only
        // place an account identifier ever lives - this app never stores
        // one itself. If sign-in was ever completed on this device, MSAL
        // returns exactly one cached account here.
        do {
            let accounts = try application.allAccounts()
            return accounts.first?.identifier
        } catch {
            return nil
        }
    }

    public func acquireTokenSilently(accountIdentifier: String, scope: String) async throws -> String {
        guard let account = try? application.account(forIdentifier: accountIdentifier) else {
            throw EntraTokenError.interactionRequired
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
    public func acquireTokenInteractively(scope: String) async throws -> String {
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
                if let result {
                    continuation.resume(returning: result.accessToken)
                } else {
                    continuation.resume(throwing: Self.mapError(error))
                }
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
