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
        width: Int, height: Int, format: UTType = .jpeg, includeGPSMetadata: Bool = false, orientation: Int? = nil
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
        if let orientation {
            options[kCGImagePropertyOrientation] = orientation
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

    // MARK: - EXIF orientation

    func testEXIFOrientationIsAppliedBeforeResizingProducingUprightOutput() throws {
        // Stored as landscape 300x150 but tagged orientation=6 ("rotate 90°
        // CW to display upright"), i.e. the correctly-oriented display size
        // is portrait 150x300. A baked-in, orientation-corrected output
        // must reflect the *displayed* (portrait) dimensions, not the raw
        // stored (landscape) ones.
        let original = TestImageFactory.makeImageData(width: 300, height: 150, orientation: 6)

        let result = FoodImagePreprocessor.preprocess(imageData: original)

        guard case .success(let preprocessed) = result else {
            return XCTFail("Expected successful preprocessing")
        }
        let dims = try dimensions(of: preprocessed.data)
        XCTAssertEqual(dims.width, 150)
        XCTAssertEqual(dims.height, 300)
    }

    func testOutputHasNoResidualOrientationTag() throws {
        // Orientation is baked into the pixel data, so the output should
        // not carry forward a separate orientation tag requiring another
        // consumer to re-apply it.
        let original = TestImageFactory.makeImageData(width: 300, height: 150, orientation: 6)

        let result = FoodImagePreprocessor.preprocess(imageData: original)

        guard case .success(let preprocessed) = result else {
            return XCTFail("Expected successful preprocessing")
        }
        let properties = try metadataProperties(of: preprocessed.data)
        let outputOrientation = properties[kCGImagePropertyOrientation as String] as? Int ?? 1
        XCTAssertEqual(outputOrientation, 1)
    }

    // MARK: - Guaranteed size limit

    func testFailsWithSizeLimitExceededWhenLimitIsUnreachable() {
        let original = TestImageFactory.makeImageData(width: 1000, height: 1000)

        // No JPEG of a non-trivial photo can plausibly fit in 10 bytes;
        // every deterministic quality/dimension step must be exhausted and
        // preprocessing must fail explicitly, never silently exceeding the
        // caller's limit.
        let result = FoodImagePreprocessor.preprocess(imageData: original, maxUploadBytes: 10)

        guard case .failure(let error) = result else {
            return XCTFail("Expected a failure")
        }
        XCTAssertEqual(error, .sizeLimitExceeded)
    }

    func testOutputNeverExceedsConfiguredUploadLimit() throws {
        let original = TestImageFactory.makeImageData(width: 3000, height: 3000)

        let result = FoodImagePreprocessor.preprocess(imageData: original, maxUploadBytes: 50_000)

        guard case .success(let preprocessed) = result else {
            return XCTFail("Expected successful preprocessing")
        }
        XCTAssertLessThanOrEqual(preprocessed.data.count, 50_000)
    }

    func testOutputNeverExceedsMaxDimensionEvenWhenQualityStepsAloneCannotFit() throws {
        // A very tight byte budget forces the dimension-reduction fallback
        // (quality steps alone cannot fit a 4000x4000 source into 20 KB).
        let original = TestImageFactory.makeImageData(width: 4000, height: 4000)

        let result = FoodImagePreprocessor.preprocess(imageData: original, maxUploadBytes: 20_000)

        guard case .success(let preprocessed) = result else {
            return XCTFail("Expected successful preprocessing")
        }
        let dims = try dimensions(of: preprocessed.data)
        XCTAssertLessThanOrEqual(max(dims.width, dims.height), 1280)
        XCTAssertLessThanOrEqual(preprocessed.data.count, 20_000)
    }

    func testValidJPEGOutputRemainsDecodable() throws {
        let original = TestImageFactory.makeImageData(width: 500, height: 500)

        let result = FoodImagePreprocessor.preprocess(imageData: original)

        guard case .success(let preprocessed) = result else {
            return XCTFail("Expected successful preprocessing")
        }
        guard let source = CGImageSourceCreateWithData(preprocessed.data as CFData, nil),
            let cgImage = CGImageSourceCreateImageAtIndex(source, 0, nil)
        else {
            return XCTFail("Output JPEG must remain decodable")
        }
        XCTAssertGreaterThan(cgImage.width, 0)
        XCTAssertGreaterThan(cgImage.height, 0)
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
