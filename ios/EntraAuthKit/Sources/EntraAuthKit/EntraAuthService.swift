import FoodAnalysisKit
import Foundation

/// Real Microsoft Entra ID (via MSAL) access-token provider for the
/// `iOS native public client -> Entra ID -> Easy Auth -> backend` design
/// (see `docs/architecture.md` and `backend/AGENTS.md`).
///
/// Silent-first, interactive-fallback orchestration lives here, over the
/// small `EntraTokenAcquiring` seam - never over concrete MSAL types
/// directly - so this logic is unit-testable (`EntraAuthKitTests`) with a
/// fake acquirer, with no MSAL dependency in this package at all. The
/// concrete adapter that talks to MSAL
/// (`ios/Trainingsplan/Entra/MSALEntraTokenAcquirer.swift`) lives in the
/// app target instead, since only it needs MSAL/UIKit.
///
/// No access token is ever persisted by this type: MSAL's own supported
/// keychain-backed token cache is the only place a token or refresh token
/// lives. This type only ever holds the non-secret `EntraConfiguration`
/// and delegates every acquisition to the injected `EntraTokenAcquiring`.
public final class EntraAuthService: AccessTokenProviding {
    private let configuration: EntraConfiguration
    private let acquirer: EntraTokenAcquiring

    public init(configuration: EntraConfiguration, acquirer: EntraTokenAcquiring) {
        self.configuration = configuration
        self.acquirer = acquirer
    }

    /// Silent-first: if MSAL's own cache has a usable account, try a
    /// silent token first. Only if that reports interaction is required
    /// (expired refresh token, revoked consent, first use, etc.) does this
    /// fall back to the interactive Microsoft sign-in UI. A user
    /// cancelling that interactive sign-in surfaces as
    /// `FoodAnalysisError.authenticationRequired` to the caller (via
    /// `FoodAnalysisService.applyAuthorization`), never a crash or a
    /// silently-unauthenticated request.
    public func acquireAccessToken() async throws -> String {
        if let accountIdentifier = try? await acquirer.currentAccountIdentifier() {
            do {
                return try await acquirer.acquireTokenSilently(
                    accountIdentifier: accountIdentifier, scope: configuration.apiScope
                )
            } catch EntraTokenError.interactionRequired {
                // Fall through to interactive below.
            }
        }
        return try await acquirer.acquireTokenInteractively(scope: configuration.apiScope)
    }
}

/// Thrown by `EntraAuthServiceFactory`-style call sites (see the app
/// target's `EntraAuthService+Factory.swift`) when `Release` configuration
/// is missing/invalid, or MSAL itself rejected it at construction time. A
/// configured provider must never fabricate a token or silently proceed
/// unauthenticated once this has happened.
public enum EntraConfigurationError: Error, Equatable, Sendable {
    case configurationMissing
    case configurationInvalid
}

/// Always-throwing provider used in `Release` builds when configuration is
/// missing/invalid, so production fails closed (every request surfaces
/// `FoodAnalysisError.authenticationRequired`) instead of silently sending
/// unauthenticated requests.
public struct FailClosedAccessTokenProvider: AccessTokenProviding {
    private let error: EntraConfigurationError

    public init(error: EntraConfigurationError) {
        self.error = error
    }

    public func acquireAccessToken() async throws -> String {
        throw error
    }
}
