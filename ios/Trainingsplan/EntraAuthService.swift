import EntraAuthKit
import FoodAnalysisKit
import Foundation

/// App-target factory for the real Entra ID `AccessTokenProviding`
/// implementation. This is the only place that combines the
/// MSAL-independent, unit-tested orchestration (`EntraAuthKit.EntraAuthService`)
/// with the concrete MSAL adapter (`MSALEntraTokenAcquirer`) - kept out of
/// the `EntraAuthKit` package itself so that package stays free of any MSAL
/// dependency and stays testable via plain `swift test`.
public enum EntraAuthServiceFactory {
    /// Returns a configured provider only when real Entra ID configuration
    /// values are present. `DEBUG` builds with no configuration return
    /// `nil` (existing local-development behavior: no `Authorization`
    /// header sent, unchanged). A `Release` build with missing or invalid
    /// configuration fails closed by returning a provider whose
    /// `acquireAccessToken()` always throws, rather than silently sending
    /// unauthenticated requests in production.
    public static func configuredProviderOrNil(bundle: Bundle = .main) -> AccessTokenProviding? {
        guard let configuration = EntraConfiguration.load(bundle: bundle) else {
            #if DEBUG
            return nil
            #else
            return FailClosedAccessTokenProvider(error: .configurationMissing)
            #endif
        }
        do {
            let acquirer = try MSALEntraTokenAcquirer(configuration: configuration)
            return EntraAuthKit.EntraAuthService(configuration: configuration, acquirer: acquirer)
        } catch {
            #if DEBUG
            return nil
            #else
            return FailClosedAccessTokenProvider(error: .configurationInvalid)
            #endif
        }
    }
}
