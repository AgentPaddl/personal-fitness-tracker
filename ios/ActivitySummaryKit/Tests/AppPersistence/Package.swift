// swift-tools-version: 5.10
import PackageDescription

let package = Package(
    name: "MarkerAppPersistenceChecks",
    platforms: [.macOS(.v14)],
    dependencies: [.package(path: "ActivitySummaryKit")],
    targets: [
        .target(
            name: "MarkerAppPersistence",
            dependencies: [.product(name: "ActivitySummaryKit", package: "ActivitySummaryKit")]
        ),
        .testTarget(
            name: "MarkerAppPersistenceTests",
            dependencies: ["MarkerAppPersistence"]
        )
    ]
)