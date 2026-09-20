// swift-tools-version: 5.10
import PackageDescription

let package = Package(
    name: "MarkerAppPersistenceChecks",
    platforms: [.macOS(.v14)],
    dependencies: [.package(path: "ActivitySummaryKit"), .package(path: "FoodAnalysisKit")],
    targets: [
        .executableTarget(name: "LegacyFoodStoreWriter"),
        .target(
            name: "MarkerAppPersistence",
            dependencies: [.product(name: "ActivitySummaryKit", package: "ActivitySummaryKit"),
                           .product(name: "FoodAnalysisKit", package: "FoodAnalysisKit")]
        ),
        .testTarget(
            name: "MarkerAppPersistenceTests",
            dependencies: ["MarkerAppPersistence"]
        )
    ]
)