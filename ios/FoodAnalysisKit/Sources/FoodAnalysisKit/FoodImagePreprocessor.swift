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
    /// No combination of the deterministic quality/dimension steps below
    /// produced an encoded image within `maxUploadBytes`.
    case sizeLimitExceeded
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
/// Uses only ImageIO (no UIKit) so this is testable on macOS via
/// `swift test`, matching the rest of this package. Every input is
/// EXIF-orientation-corrected and resized to a maximum dimension via
/// ImageIO's thumbnail API (`kCGImageSourceCreateThumbnailWithTransform`
/// bakes the orientation into the pixel data, so the output is always
/// upright regardless of how the source declared its orientation), then
/// re-encoded as JPEG - which also strips EXIF/GPS and other source
/// metadata, since the JPEG destination is never given the source's
/// properties dictionary.
///
/// Every produced image is guaranteed (or preprocessing fails explicitly,
/// with no silent fallback to the original full-resolution/unoriented
/// image) to have:
/// - a longest side <= `maxDimensionPixels`
/// - an encoded size <= `maxUploadBytes`
public enum FoodImagePreprocessor {
    /// Longest side, in pixels, after resizing. Large enough to preserve
    /// enough detail for food recognition; far below a full-resolution
    /// iPhone photo.
    public static let maxDimensionPixels: CGFloat = 1280
    public static let jpegCompressionQuality: CGFloat = 0.7
    /// Matches the backend/gateway's `MAX_IMAGE_BYTES` upload limit (also
    /// chosen to fit within the currently-configured vision model's
    /// advertised max prompt image size).
    public static let maxUploadBytes: Int = 3 * 1024 * 1024

    /// Deterministic, finite JPEG quality steps tried (in order) at each
    /// dimension step until the encoded size fits `maxUploadBytes`. Never
    /// retried indefinitely.
    private static let qualitySteps: [CGFloat] = [0.7, 0.5, 0.3, 0.15]
    /// The smallest longest-side this will ever downscale to while
    /// searching for a fit.
    private static let minDimensionPixels: CGFloat = 320

    public static func preprocess(
        imageData: Data,
        maxDimensionPixels: CGFloat = maxDimensionPixels,
        maxUploadBytes: Int = maxUploadBytes
    ) -> Result<PreprocessedFoodImage, FoodImagePreprocessingError> {
        guard let source = CGImageSourceCreateWithData(imageData as CFData, nil) else {
            return .failure(.decodeFailed)
        }

        var producedAnyThumbnail = false
        for dimension in dimensionCandidates(startingAt: maxDimensionPixels) {
            guard let thumbnail = makeOrientedThumbnail(source: source, maxDimensionPixels: dimension) else {
                continue
            }
            producedAnyThumbnail = true

            for quality in qualitySteps {
                guard let jpegData = encodeJPEG(thumbnail, quality: quality) else { continue }
                if jpegData.count <= maxUploadBytes {
                    return .success(PreprocessedFoodImage(data: jpegData, mimeType: "image/jpeg"))
                }
            }
        }

        // Never falls back to the original, full-resolution/unoriented
        // CGImage: either a bounded candidate satisfied both limits above,
        // or preprocessing fails explicitly here.
        return .failure(producedAnyThumbnail ? .sizeLimitExceeded : .decodeFailed)
    }

    /// `[maxDimensionPixels, maxDimensionPixels/2, maxDimensionPixels/4, ...]`,
    /// stopping once the next step would go below `minDimensionPixels`.
    /// Finite by construction - never open-ended.
    private static func dimensionCandidates(startingAt start: CGFloat) -> [CGFloat] {
        var candidates: [CGFloat] = [start]
        var current = start
        while current / 2 >= minDimensionPixels {
            current /= 2
            candidates.append(current)
        }
        return candidates
    }

    /// Produces an already-upright (EXIF orientation applied/baked in),
    /// resized-to-fit thumbnail. ImageIO never upscales beyond the
    /// source's own size, so small originals pass through unscaled.
    private static func makeOrientedThumbnail(source: CGImageSource, maxDimensionPixels: CGFloat) -> CGImage? {
        let options: [CFString: Any] = [
            kCGImageSourceCreateThumbnailFromImageAlways: true,
            kCGImageSourceThumbnailMaxPixelSize: maxDimensionPixels,
            // Bakes the source's EXIF orientation into the thumbnail's
            // pixel data, guaranteeing an upright output regardless of the
            // original orientation tag.
            kCGImageSourceCreateThumbnailWithTransform: true,
            kCGImageSourceShouldCacheImmediately: true,
        ]
        return CGImageSourceCreateThumbnailAtIndex(source, 0, options as CFDictionary)
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
