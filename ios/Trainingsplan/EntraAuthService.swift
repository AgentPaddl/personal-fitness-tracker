import FoodAnalysisKit
import Foundation

/// Placeholder Microsoft Entra ID (via MSAL) access-token provider for the
/// `iOS native public client -> Entra ID -> Easy Auth -> backend` design
/// (see `docs/architecture.md` and `backend/AGENTS.md`).
///
/// No MSAL SDK dependency has been added to the project yet. This type
/// intentionally implements only the non-secret plumbing (reading
/// placeholder configuration keys, deciding whether Entra ID has been
/// configured at all) and documents exactly what remains to integrate a
/// real MSAL client. It must never contain a client secret - native
/// public clients authenticate via MSAL's interactive/silent token
/// acquisition, not a stored secret.
///
/// `configuredProviderOrNil()` returns `nil` until the placeholder Info.plist
/// keys below are filled in with real values from an actual Entra app
/// registration, so `FoodAnalysisViewModel` sends no `Authorization`
/// header and today's unauthenticated local-development behavior is
/// preserved exactly until Entra ID is actually set up.
public final class EntraAuthService: AccessTokenProviding {
    /// Non-secret Entra ID/MSAL configuration. All four values are public
    /// identifiers (not secrets) that are safe to ship in an Info.plist
    /// for a native public client, but they are still placeholders here -
    /// filling them in requires an actual Entra app registration (see the
    /// checklist in `docs/architecture.md`).
    struct Configuration {
        let tenantId: String
        let clientId: String
        let apiScope: String
        let redirectUri: String
    }

    enum ServiceError: Error {
        /// MSAL is not yet integrated; only a documented placeholder
        /// exists so far.
        case notImplemented
    }

    private let configuration: Configuration

    private init(configuration: Configuration) {
        self.configuration = configuration
    }

    /// Reads `EntraTenantID`, `EntraClientID`, `EntraAPIScope`, and
    /// `EntraRedirectURI` from the given bundle's Info.plist. All four
    /// must be present and non-blank; a partially configured bundle is
    /// treated the same as unconfigured (fails closed to "no provider",
    /// never a half-working one).
    static func loadConfiguration(bundle: Bundle) -> Configuration? {
        guard
            let tenantId = bundle.object(forInfoDictionaryKey: "EntraTenantID") as? String,
            !tenantId.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty,
            let clientId = bundle.object(forInfoDictionaryKey: "EntraClientID") as? String,
            !clientId.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty,
            let apiScope = bundle.object(forInfoDictionaryKey: "EntraAPIScope") as? String,
            !apiScope.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty,
            let redirectUri = bundle.object(forInfoDictionaryKey: "EntraRedirectURI") as? String,
            !redirectUri.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty
        else {
            return nil
        }
        return Configuration(tenantId: tenantId, clientId: clientId, apiScope: apiScope, redirectUri: redirectUri)
    }

    /// Returns a configured provider only once real Entra ID values have
    /// been filled in; returns `nil` otherwise so callers send no
    /// `Authorization` header at all (matching current behavior).
    public static func configuredProviderOrNil(bundle: Bundle = .main) -> AccessTokenProviding? {
        guard let configuration = loadConfiguration(bundle: bundle) else { return nil }
        return EntraAuthService(configuration: configuration)
    }

    /// Not yet implemented: once configured (see `configuredProviderOrNil`),
    /// this must perform an MSAL interactive/silent `acquireToken` call
    /// scoped to `configuration.apiScope` and return its access token.
    /// Until the MSAL SDK is integrated, a configured instance still fails
    /// closed here rather than fabricating a token.
    public func acquireAccessToken() async throws -> String {
        throw ServiceError.notImplemented
    }
}
