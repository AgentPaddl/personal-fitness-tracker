import Foundation

/// Resolves the Fitness API backend's base URL for the food-analysis flow.
///
/// This intentionally stays a small, source-level default rather than a
/// build system (Info.plist keys, xcconfig files, etc.) to avoid adding
/// configuration complexity for a single development URL.
///
/// Override for a real device (which cannot reach your Mac via
/// `localhost`) by setting the `API_BASE_URL` environment variable on the
/// app's Xcode scheme: Product > Scheme > Edit Scheme... > Run > Arguments
/// > Environment Variables, e.g. `http://192.168.1.23:7071/api`.
/// Defaults to the local Azure Functions Core Tools port used by
/// `func start` for the simulator.
public enum APIConfiguration {
    public static var backendBaseURL: URL {
        if let raw = ProcessInfo.processInfo.environment["API_BASE_URL"],
            let url = URL(string: raw)
        {
            return url
        }
        return URL(string: "http://127.0.0.1:7071/api")!
    }
}
