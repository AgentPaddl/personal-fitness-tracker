// swift-tools-version: 5.10
import PackageDescription

/// MSAL-independent Microsoft Entra ID token-acquisition orchestration
/// (silent-first, interactive-fallback), testable via `swift test` without
/// Xcode, MSAL, network access, or a real backend. The only place that
/// imports MSAL is `ios/Trainingsplan/Entra/MSALEntraTokenAcquirer.swift`
/// in the app target, which conforms to `EntraTokenAcquiring` from this
/// package - see docs/architecture.md.
let package = Package(
    name: "EntraAuthKit",
    platforms: [.iOS(.v17), .macOS(.v12)],
    products: [
        .library(name: "EntraAuthKit", targets: ["EntraAuthKit"])
    ],
    dependencies: [
        .package(path: "../FoodAnalysisKit")
    ],
    targets: [
        .target(
            name: "EntraAuthKit",
            dependencies: ["FoodAnalysisKit"]
        ),
        .testTarget(
            name: "EntraAuthKitTests",
            dependencies: ["EntraAuthKit"]
        )
    ]
)
