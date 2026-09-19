import CryptoKit
import Foundation

public enum PilotAcceptanceFixture: String, CaseIterable, Sendable {
    case label = "L1"
    case nonFood = "P5"

    public var filename: String { self == .label ? "L1.png" : "P5.jpg" }
    public var foodDescription: String {
        self == .label
            ? "Ich habe 150 g des abgebildeten Produkts gegessen."
            : "Was zeigt dieses Bild?"
    }

    private var sourceHash: String {
        self == .label
            ? "0ff7ef5ab5f2ff413de5b26ea407ba05f1ee3cd50f736aecec1acfcfcda718fb"
            : "2c2f09a34a2be5cd1d679918a94ec8730e4ab68bba2c3e0b5b6f4f270ffaccef"
    }

    public func source(in directory: URL) throws -> Data {
        let data = try Data(contentsOf: directory.appendingPathComponent(filename))
        let actualHash = SHA256.hash(data: data).map { String(format: "%02x", $0) }.joined()
        guard actualHash == sourceHash else { throw FoodImagePreprocessingError.decodeFailed }
        return data
    }

    public func prepare(in directory: URL) throws -> PreprocessedFoodImage {
        let image = try FoodImagePreprocessor.preprocess(imageData: source(in: directory)).get()
        let destination = directory.appendingPathComponent(rawValue + "-upload.jpg")
        if FileManager.default.fileExists(atPath: destination.path) {
            guard try Data(contentsOf: destination) == image.data else {
                throw FoodImagePreprocessingError.encodeFailed
            }
        } else {
            try image.data.write(to: destination, options: .withoutOverwriting)
        }
        return image
    }
}