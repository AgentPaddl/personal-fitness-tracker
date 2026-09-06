// swift-tools-version: 5.10
import PackageDescription

let package = Package(
    name: "ActivitySummaryKit",
    platforms: [.iOS(.v17), .macOS(.v12)],
    products: [
        .library(name: "ActivitySummaryKit", targets: ["ActivitySummaryKit"])
    ],
    targets: [
        .target(name: "ActivitySummaryKit"),
        .testTarget(
            name: "ActivitySummaryKitTests",
            dependencies: ["ActivitySummaryKit"]
        )
    ]
)
