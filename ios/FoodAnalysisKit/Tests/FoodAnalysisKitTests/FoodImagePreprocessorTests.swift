import CoreGraphics
import ImageIO
import UniformTypeIdentifiers
import XCTest

@testable import FoodAnalysisKit

/// Builds a synthetic, deterministic test JPEG/PNG in-memory (no bundled
/// fixture, no network, no user photo), optionally embedding EXIF/GPS
/// metadata so preprocessing's metadata-stripping behavior is verifiable.
private enum TestImageFactory {
    static func makeImageData(
        width: Int, height: Int, format: UTType = .jpeg, includeGPSMetadata: Bool = false
    ) -> Data {
        guard
            let context = CGContext(
                data: nil,
                width: width,
                height: height,
                bitsPerComponent: 8,
                bytesPerRow: 0,
                space: CGColorSpaceCreateDeviceRGB(),
                bitmapInfo: CGImageAlphaInfo.premultipliedLast.rawValue
            )
        else {
            fatalError("Failed to create test CGContext")
        }
        context.setFillColor(CGColor(red: 0.8, green: 0.2, blue: 0.1, alpha: 1))
        context.fill(CGRect(x: 0, y: 0, width: width, height: height))
        guard let cgImage = context.makeImage() else {
            fatalError("Failed to create test CGImage")
        }

        let data = NSMutableData()
        guard let destination = CGImageDestinationCreateWithData(data, format.identifier as CFString, 1, nil) else {
            fatalError("Failed to create test CGImageDestination")
        }
        var options: [CFString: Any] = [:]
        if includeGPSMetadata {
            options[kCGImagePropertyGPSDictionary] = [
                kCGImagePropertyGPSLatitude: 52.5,
                kCGImagePropertyGPSLatitudeRef: "N",
                kCGImagePropertyGPSLongitude: 13.4,
                kCGImagePropertyGPSLongitudeRef: "E",
            ]
        }
        CGImageDestinationAddImage(destination, cgImage, options as CFDictionary)
        guard CGImageDestinationFinalize(destination) else {
            fatalError("Failed to finalize test image")
        }
        return data as Data
    }
}

final class FoodImagePreprocessorTests: XCTestCase {
    func testSmallImagePassesThroughWithoutResizing() throws {
        let original = TestImageFactory.makeImageData(width: 200, height: 100)

        let result = FoodImagePreprocessor.preprocess(imageData: original)

        guard case .success(let preprocessed) = result else {
            return XCTFail("Expected successful preprocessing")
        }
        XCTAssertEqual(preprocessed.mimeType, "image/jpeg")
        let dimensions = try dimensions(of: preprocessed.data)
        XCTAssertEqual(dimensions.width, 200)
        XCTAssertEqual(dimensions.height, 100)
    }

    func testLargeImageIsResizedToMaxDimension() throws {
        let original = TestImageFactory.makeImageData(width: 3000, height: 1500)

        let result = FoodImagePreprocessor.preprocess(imageData: original, maxDimensionPixels: 1280)

        guard case .success(let preprocessed) = result else {
            return XCTFail("Expected successful preprocessing")
        }
        let dimensions = try dimensions(of: preprocessed.data)
        XCTAssertEqual(dimensions.width, 1280)
        XCTAssertEqual(dimensions.height, 640)
    }

    func testPortraitImagePreservesAspectRatioWhenResizing() throws {
        let original = TestImageFactory.makeImageData(width: 1500, height: 3000)

        let result = FoodImagePreprocessor.preprocess(imageData: original, maxDimensionPixels: 1280)

        guard case .success(let preprocessed) = result else {
            return XCTFail("Expected successful preprocessing")
        }
        let dimensions = try dimensions(of: preprocessed.data)
        XCTAssertEqual(dimensions.width, 640)
        XCTAssertEqual(dimensions.height, 1280)
    }

    func testOutputIsAlwaysJPEGRegardlessOfInputFormat() throws {
        let original = TestImageFactory.makeImageData(width: 100, height: 100, format: .png)

        let result = FoodImagePreprocessor.preprocess(imageData: original)

        guard case .success(let preprocessed) = result else {
            return XCTFail("Expected successful preprocessing")
        }
        XCTAssertEqual(preprocessed.mimeType, "image/jpeg")
        XCTAssertEqual(try imageFormat(of: preprocessed.data), UTType.jpeg.identifier)
    }

    func testGPSMetadataIsNotForwardedToOutput() throws {
        let original = TestImageFactory.makeImageData(width: 100, height: 100, includeGPSMetadata: true)
        // Sanity check the fixture actually embedded GPS metadata.
        XCTAssertNotNil(try metadataProperties(of: original)[kCGImagePropertyGPSDictionary as String])

        let result = FoodImagePreprocessor.preprocess(imageData: original)

        guard case .success(let preprocessed) = result else {
            return XCTFail("Expected successful preprocessing")
        }
        let outputProperties = try metadataProperties(of: preprocessed.data)
        XCTAssertNil(outputProperties[kCGImagePropertyGPSDictionary as String])
    }

    func testUndecodableDataFailsWithDecodeFailed() {
        let garbage = Data("this is definitely not an image".utf8)

        let result = FoodImagePreprocessor.preprocess(imageData: garbage)

        guard case .failure(let error) = result else {
            return XCTFail("Expected a failure")
        }
        XCTAssertEqual(error, .decodeFailed)
    }

    func testEmptyDataFailsWithDecodeFailed() {
        let result = FoodImagePreprocessor.preprocess(imageData: Data())

        guard case .failure(let error) = result else {
            return XCTFail("Expected a failure")
        }
        XCTAssertEqual(error, .decodeFailed)
    }

    // MARK: - Helpers

    private func dimensions(of data: Data) throws -> (width: Int, height: Int) {
        guard let source = CGImageSourceCreateWithData(data as CFData, nil),
            let properties = CGImageSourceCopyPropertiesAtIndex(source, 0, nil) as? [CFString: Any],
            let width = properties[kCGImagePropertyPixelWidth] as? Int,
            let height = properties[kCGImagePropertyPixelHeight] as? Int
        else {
            throw XCTSkip("Could not read output image dimensions")
        }
        return (width, height)
    }

    private func imageFormat(of data: Data) throws -> String? {
        guard let source = CGImageSourceCreateWithData(data as CFData, nil) else { return nil }
        return CGImageSourceGetType(source) as String?
    }

    private func metadataProperties(of data: Data) throws -> [String: Any] {
        guard let source = CGImageSourceCreateWithData(data as CFData, nil),
            let properties = CGImageSourceCopyPropertiesAtIndex(source, 0, nil) as? [CFString: Any]
        else {
            return [:]
        }
        return Dictionary(uniqueKeysWithValues: properties.map { (String($0.key), $0.value) })
    }
}
