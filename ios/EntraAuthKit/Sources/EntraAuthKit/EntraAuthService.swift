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
public final class EntraAuthService: AccountAccessTokenProviding {
    private let configuration: EntraConfiguration
    private let acquirer: EntraTokenAcquiring
    private let accountStore: EntraAccountStoring

    public init(
        configuration: EntraConfiguration,
        acquirer: EntraTokenAcquiring,
        accountStore: EntraAccountStoring = UserDefaultsEntraAccountStore()
    ) {
        self.configuration = configuration
        self.acquirer = acquirer
        self.accountStore = accountStore
    }

    /// Account-selection policy (single-user app, never picks an account
    /// arbitrarily):
    /// 1. A previously-selected account identifier (`accountStore`) is
    ///    tried first, resolved deterministically via
    ///    `acquirer.accountExists(identifier:)`. If it no longer resolves
    ///    (e.g. removed via Settings), it is cleared and resolution falls
    ///    through to step 2 rather than either failing outright or
    ///    blindly going interactive.
    /// 2. With no selected identifier, `acquirer.resolveCachedAccounts()`
    ///    decides: zero cached accounts goes straight to interactive;
    ///    exactly one is selected and remembered; more than one throws
    ///    `EntraTokenError.multipleAccountsRequireSelection` rather than
    ///    choosing arbitrarily.
    /// Any account/cache *lookup* failure (`accountLookupFailed`) from
    /// either step propagates immediately - it is never treated as "no
    /// account" and never triggers an interactive login. Only
    /// `EntraTokenError.interactionRequired` from a silent acquisition
    /// attempt falls back to interactive. A user cancelling that
    /// interactive sign-in surfaces as
    /// `FoodAnalysisError.authenticationRequired` to the caller (via
    /// `FoodAnalysisService.applyAuthorization`), never a crash or a
    /// silently-unauthenticated request.
    public func acquireAccessToken() async throws -> String {
        try await acquireAccountAccessToken().token
    }

    public func acquireAccountAccessToken() async throws -> AccountAccessToken {
        if let selectedIdentifier = accountStore.loadSelectedAccountIdentifier() {
            if try await acquirer.accountExists(identifier: selectedIdentifier) {
                do {
                    let token = try await acquirer.acquireTokenSilently(
                        accountIdentifier: selectedIdentifier, scope: configuration.apiScope
                    )
                    return AccountAccessToken(token: token, accountIdentifier: selectedIdentifier)
                } catch EntraTokenError.interactionRequired {
                    return try await acquireInteractively()
                }
            }
            // Selected identifier no longer resolves - re-resolve from
            // the current cache below instead of failing or guessing.
            accountStore.clearSelectedAccountIdentifier()
        }

        switch try await acquirer.resolveCachedAccounts() {
        case .none:
            return try await acquireInteractively()
        case .single(let identifier):
            accountStore.saveSelectedAccountIdentifier(identifier)
            do {
                let token = try await acquirer.acquireTokenSilently(accountIdentifier: identifier, scope: configuration.apiScope)
                return AccountAccessToken(token: token, accountIdentifier: identifier)
            } catch EntraTokenError.interactionRequired {
                return try await acquireInteractively()
            }
        case .multiple:
            throw EntraTokenError.multipleAccountsRequireSelection
        }
    }

    private func acquireInteractively() async throws -> AccountAccessToken {
        let result = try await acquirer.acquireTokenInteractively(scope: configuration.apiScope)
        accountStore.saveSelectedAccountIdentifier(result.accountIdentifier)
        return AccountAccessToken(token: result.accessToken, accountIdentifier: result.accountIdentifier)
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
