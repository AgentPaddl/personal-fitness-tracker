// swift-tools-version: 5.10
import PackageDescription

let package = Package(
    name: "FoodAnalysisKit",
    platforms: [.iOS(.v17), .macOS(.v12)],
    products: [
        .library(name: "FoodAnalysisKit", targets: ["FoodAnalysisKit"])
    ],
    targets: [
        .target(name: "FoodAnalysisKit"),
        .testTarget(name: "FoodAnalysisKitTests", dependencies: ["FoodAnalysisKit"])
    ]
)
