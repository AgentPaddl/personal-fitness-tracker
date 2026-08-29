import CoreGraphics
import Foundation
import ImageIO
import UniformTypeIdentifiers

/// Reasons a picked photo could not be turned into an uploadable image.
public enum FoodImagePreprocessingError: Error, Equatable, Sendable {
    /// The input data could not be decoded as an image at all.
    case decodeFailed
    /// The image decoded but could not be re-encoded as JPEG.
    case encodeFailed
}

/// A preprocessed, ready-to-upload image and its MIME type.
public struct PreprocessedFoodImage: Equatable, Sendable {
    public let data: Data
    public let mimeType: String

    public init(data: Data, mimeType: String) {
        self.data = data
        self.mimeType = mimeType
    }
}

/// Deterministic, testable client-side image preprocessing for food photos.
///
/// Uses only ImageIO/CoreGraphics (no UIKit) so this is testable on macOS
/// via `swift test`, matching the rest of this package. Every input is
/// resized to a sensible maximum dimension and re-encoded as JPEG - this
/// also strips EXIF/GPS and other source metadata, since the JPEG
/// destination is never given the source's properties dictionary.
public enum FoodImagePreprocessor {
    /// Longest side, in pixels, after resizing. Large enough to preserve
    /// enough detail for food recognition; far below a full-resolution
    /// iPhone photo.
    public static let maxDimensionPixels: CGFloat = 1280
    public static let jpegCompressionQuality: CGFloat = 0.7

    public static func preprocess(
        imageData: Data,
        maxDimensionPixels: CGFloat = maxDimensionPixels,
        jpegCompressionQuality: CGFloat = jpegCompressionQuality
    ) -> Result<PreprocessedFoodImage, FoodImagePreprocessingError> {
        guard let source = CGImageSourceCreateWithData(imageData as CFData, nil),
            let cgImage = CGImageSourceCreateImageAtIndex(source, 0, nil)
        else {
            return .failure(.decodeFailed)
        }

        let resized = resizedIfNeeded(cgImage, maxDimensionPixels: maxDimensionPixels)

        guard let jpegData = encodeJPEG(resized, quality: jpegCompressionQuality) else {
            return .failure(.encodeFailed)
        }

        return .success(PreprocessedFoodImage(data: jpegData, mimeType: "image/jpeg"))
    }

    private static func resizedIfNeeded(_ image: CGImage, maxDimensionPixels: CGFloat) -> CGImage {
        let width = CGFloat(image.width)
        let height = CGFloat(image.height)
        let largestSide = max(width, height)
        guard largestSide > maxDimensionPixels, largestSide > 0 else { return image }

        let scale = maxDimensionPixels / largestSide
        let newWidth = max(1, Int((width * scale).rounded()))
        let newHeight = max(1, Int((height * scale).rounded()))

        guard
            let context = CGContext(
                data: nil,
                width: newWidth,
                height: newHeight,
                bitsPerComponent: 8,
                bytesPerRow: 0,
                space: CGColorSpaceCreateDeviceRGB(),
                bitmapInfo: CGImageAlphaInfo.premultipliedLast.rawValue
            )
        else {
            return image
        }

        context.interpolationQuality = .high
        context.draw(image, in: CGRect(x: 0, y: 0, width: newWidth, height: newHeight))
        return context.makeImage() ?? image
    }

    private static func encodeJPEG(_ image: CGImage, quality: CGFloat) -> Data? {
        let data = NSMutableData()
        guard
            let destination = CGImageDestinationCreateWithData(
                data, UTType.jpeg.identifier as CFString, 1, nil
            )
        else {
            return nil
        }

        // Intentionally never copies the source's metadata/properties
        // dictionary (which would carry EXIF/GPS) into the destination.
        let options: [CFString: Any] = [kCGImageDestinationLossyCompressionQuality: quality]
        CGImageDestinationAddImage(destination, image, options as CFDictionary)

        guard CGImageDestinationFinalize(destination) else { return nil }
        return data as Data
    }
}
