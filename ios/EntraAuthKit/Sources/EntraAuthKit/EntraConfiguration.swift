import Foundation

/// Non-secret Microsoft Entra ID / MSAL configuration for the native/public
/// iOS client. All four values are public identifiers - safe to ship in an
/// Info.plist - not secrets: a native public client has no client secret at
/// all (see docs/architecture.md's Entra setup checklist).
///
/// `authority` is derived from `tenantId` (`https://login.microsoftonline.com/<tenantId>`),
/// the standard Microsoft Entra ID work/school-account authority format; this
/// app does not support consumer Microsoft accounts or multi-tenant sign-in.
public struct EntraConfiguration: Equatable, Sendable {
    public let tenantId: String
    public let clientId: String
    /// Full scope URI for the backend's delegated API permission, e.g.
    /// `api://<backend-app-id>/FoodAnalysis.Access` (see the Application ID
    /// URI checklist in docs/architecture.md). Requested exactly as
    /// configured - never silently widened or defaulted to Graph scopes.
    public let apiScope: String
    /// MSAL's documented default iOS/macOS redirect URI format,
    /// `msauth.<bundle-id>://auth` - see
    /// `ios/Trainingsplan-Info.plist`'s `CFBundleURLTypes` and
    /// https://learn.microsoft.com/entra/msal/objc/redirect-uris-ios.
    public let redirectUri: String

    public init(tenantId: String, clientId: String, apiScope: String, redirectUri: String) {
        self.tenantId = tenantId
        self.clientId = clientId
        self.apiScope = apiScope
        self.redirectUri = redirectUri
    }

    public var authority: String {
        "https://login.microsoftonline.com/\(tenantId)"
    }

    /// Reads `EntraTenantID`, `EntraClientID`, `EntraAPIScope`, and
    /// `EntraRedirectURI` from the given bundle's Info.plist. All four must
    /// be present and non-blank; a partially configured bundle is treated
    /// the same as unconfigured (fails closed to "no configuration", never
    /// a half-working one).
    public static func load(bundle: Bundle) -> EntraConfiguration? {
        guard
            let tenantId = nonBlankString(bundle, "EntraTenantID"),
            let clientId = nonBlankString(bundle, "EntraClientID"),
            let apiScope = nonBlankString(bundle, "EntraAPIScope"),
            let redirectUri = nonBlankString(bundle, "EntraRedirectURI")
        else {
            return nil
        }
        return EntraConfiguration(tenantId: tenantId, clientId: clientId, apiScope: apiScope, redirectUri: redirectUri)
    }

    private static func nonBlankString(_ bundle: Bundle, _ key: String) -> String? {
        guard let value = bundle.object(forInfoDictionaryKey: key) as? String else { return nil }
        let trimmed = value.trimmingCharacters(in: .whitespacesAndNewlines)
        return trimmed.isEmpty ? nil : trimmed
    }
}
