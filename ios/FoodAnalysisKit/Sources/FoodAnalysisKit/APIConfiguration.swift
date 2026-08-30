import Foundation

/// Fail-closed reasons the backend base URL could not be resolved. Never
/// silently replaced with a fallback host - the caller must surface these.
public enum APIConfigurationError: Error, Equatable, Sendable {
    /// No `API_BASE_URL` override was provided and this is not a
    /// recognized local-development context (the Simulator).
    case missingConfiguration
    /// The provided value is not a well-formed URL with a scheme and host.
    case invalidURL(String)
    /// Scheme is neither `http` nor `https`.
    case unsupportedScheme(String)
    /// Plain HTTP was used for a host that isn't a recognized
    /// local-development address; HTTPS is required for anything else.
    case insecureSchemeForNonLocalHost(host: String)
    /// The path is neither empty/`/` nor `/api`, or the URL has a query
    /// string or fragment. Only the exact Azure Functions API route
    /// prefix is accepted - never an arbitrary path.
    case unsupportedPath(String)
}

/// Resolves the Fitness API backend's base URL for the food-analysis flow.
///
/// Precedence (highest first):
/// 1. **Compiled-in `ProductionAPIBaseURL` Info.plist value** - populated via
///    the `API_BASE_URL` build setting through Xcode's standard `$(VAR)`
///    Info.plist substitution (same mechanism as `EntraConfiguration`'s
///    `Entra*` keys). Blank in `Debug`, set to the real production URL in
///    `Release` - this is what makes Release archive/TestFlight-safe
///    without depending on a scheme environment variable.
/// 2. **`API_BASE_URL` environment variable** on the app's Xcode scheme
///    (Product > Scheme > Edit Scheme... > Run > Arguments > Environment
///    Variables) - only reached when the plist value above is blank (i.e.
///    in practice, `Debug` builds). Preserved for local/device development
///    convenience; never consulted once a build has a compiled-in value.
/// 3. **Simulator implicit default** (`http://127.0.0.1:7071/api`) if
///    neither of the above is set.
/// 4. Otherwise fails closed with `.missingConfiguration` - an
///    installed/device build never silently falls back to a localhost
///    address, and an explicitly configured but invalid/insecure value is
///    never silently replaced.
///
/// - Physical device (Debug, no compiled-in value): set `API_BASE_URL` on
///   the scheme to the Mac's reachable LAN hostname/IP, e.g.
///   `http://192.168.1.23:7071/api` (also requires the narrow
///   `NSAllowsLocalNetworking` ATS exception - see `ios/AGENTS.md`).
///   `localhost`/`127.0.0.1` refers to the device itself, not your Mac.
/// - Production-like endpoints must use `https://`.
public enum APIConfiguration {
    /// Public entry point: resolves using the real environment, the real
    /// build target (Simulator vs. device, Debug vs. Release), and the
    /// app's real Info.plist (`bundle`, defaulting to `Bundle.main`).
    public static func resolveBackendBaseURL(
        rawOverride: String? = ProcessInfo.processInfo.environment["API_BASE_URL"],
        bundle: Bundle = .main
    ) -> Result<URL, APIConfigurationError> {
        #if targetEnvironment(simulator)
        let allowsImplicitSimulatorDefault = true
        #else
        let allowsImplicitSimulatorDefault = false
        #endif
        // The plain-HTTP local-development exception (LAN IPs for physical-
        // device development) only ever applies to Debug builds. A Release
        // build - what an installed/production build actually is - must
        // always use HTTPS, regardless of host, so a misconfigured or
        // leftover development URL can never silently ship in production.
        #if DEBUG
        let allowsInsecureLocalDevelopmentHost = true
        #else
        let allowsInsecureLocalDevelopmentHost = false
        #endif
        return resolve(
            rawOverride: effectiveOverride(rawOverride: rawOverride, bundle: bundle),
            allowsImplicitSimulatorDefault: allowsImplicitSimulatorDefault,
            allowsInsecureLocalDevelopmentHost: allowsInsecureLocalDevelopmentHost
        )
    }

    /// The compiled-in Info.plist value takes precedence over the scheme
    /// environment variable, so a Release build's durable production URL
    /// can never be silently shadowed by a leftover scheme override; the
    /// environment variable is only ever reached when the plist value is
    /// blank (in practice, Debug builds - see `resolveBackendBaseURL`'s
    /// precedence doc above).
    static func effectiveOverride(rawOverride: String?, bundle: Bundle) -> String? {
        nonBlankString(bundle, "ProductionAPIBaseURL") ?? nonBlank(rawOverride)
    }

    private static func nonBlankString(_ bundle: Bundle, _ key: String) -> String? {
        guard let value = bundle.object(forInfoDictionaryKey: key) as? String else { return nil }
        return nonBlank(value)
    }

    private static func nonBlank(_ value: String?) -> String? {
        guard let value else { return nil }
        let trimmed = value.trimmingCharacters(in: .whitespacesAndNewlines)
        return trimmed.isEmpty ? nil : trimmed
    }

    /// Testable core: takes the "are we allowed to default to the local
    /// Simulator address" and "are we allowed the local-HTTP development
    /// exception" decisions as plain parameters instead of compile-time
    /// platform/configuration checks.
    static func resolve(
        rawOverride: String?,
        allowsImplicitSimulatorDefault: Bool,
        allowsInsecureLocalDevelopmentHost: Bool = true
    ) -> Result<URL, APIConfigurationError> {
        let trimmed = (rawOverride ?? "").trimmingCharacters(in: .whitespacesAndNewlines)

        guard !trimmed.isEmpty else {
            guard allowsImplicitSimulatorDefault else { return .failure(.missingConfiguration) }
            // Explicit, recognized local-development default.
            return .success(URL(string: "http://127.0.0.1:7071/api")!)
        }

        guard let url = URL(string: trimmed), let scheme = url.scheme?.lowercased(), let host = url.host,
            !host.isEmpty
        else {
            return .failure(.invalidURL(trimmed))
        }

        guard scheme == "http" || scheme == "https" else {
            return .failure(.unsupportedScheme(scheme))
        }

        if scheme == "http" && !(allowsInsecureLocalDevelopmentHost && isLocalDevelopmentHost(host)) {
            return .failure(.insecureSchemeForNonLocalHost(host: host))
        }

        return normalizeAPIBasePath(of: url)
    }

    /// Loopback (Simulator) and common private-LAN ranges (a physical
    /// device reaching the developer's Mac directly). Anything else must
    /// use HTTPS.
    private static func isLocalDevelopmentHost(_ host: String) -> Bool {
        let lowercased = host.lowercased()
        if lowercased == "localhost" || lowercased == "127.0.0.1" || lowercased == "::1" {
            return true
        }
        let parts = lowercased.split(separator: ".")
        guard parts.count == 4, parts.allSatisfy({ Int($0) != nil }) else { return false }
        if parts[0] == "10" { return true }
        if parts[0] == "192" && parts[1] == "168" { return true }
        if parts[0] == "172", let second = Int(parts[1]), (16...31).contains(second) { return true }
        return false
    }

    /// Accepts only no path, `/`, `/api`, or `/api/` (all normalized to
    /// `/api`), and rejects any query string or fragment. This is
    /// deliberately strict - an arbitrary path like `/staging` is not a
    /// typo-tolerant convenience, it's a different, unintended endpoint.
    private static func normalizeAPIBasePath(of url: URL) -> Result<URL, APIConfigurationError> {
        guard url.query == nil, url.fragment == nil else {
            return .failure(.unsupportedPath(url.absoluteString))
        }

        let trimmedPath = url.path.hasSuffix("/") && url.path != "/" ? String(url.path.dropLast()) : url.path
        guard trimmedPath.isEmpty || trimmedPath == "/" || trimmedPath == "/api" else {
            return .failure(.unsupportedPath(url.absoluteString))
        }

        guard var components = URLComponents(url: url, resolvingAgainstBaseURL: false) else {
            return .failure(.unsupportedPath(url.absoluteString))
        }
        components.path = "/api"
        guard let normalized = components.url else {
            return .failure(.unsupportedPath(url.absoluteString))
        }
        return .success(normalized)
    }
}
