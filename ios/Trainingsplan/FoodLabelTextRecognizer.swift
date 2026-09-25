import Foundation
import ImageIO
import Vision
import FoodAnalysisKit

enum FoodLabelTextRecognizer {
    enum Failure: Error { case unsupported, invalidImage, tooMuchText }

    struct Result: Sendable {
        let image: CGImage
        let tokens: [FoodLabelText]
        let lines: [String]
        let lowConfidenceCount: Int
    }

    nonisolated static func recognize(_ data: Data) async throws -> [FoodLabelText] {
        try await inspect(data).tokens
    }

    nonisolated static func inspect(_ data: Data) async throws -> Result {
        let worker = Task.detached(priority: .userInitiated) {
            try Task.checkCancellation()
            let result = try autoreleasepool { try perform(data) }
            try Task.checkCancellation()
            return result
        }
        return try await withTaskCancellationHandler {
            try await worker.value
        } onCancel: {
            worker.cancel()
        }
    }

    nonisolated private static func perform(_ data: Data) throws -> Result {
        guard data.count <= 30 * 1024 * 1024,
              let source = CGImageSourceCreateWithData(data as CFData, [kCGImageSourceShouldCache: false] as CFDictionary),
              let image = CGImageSourceCreateThumbnailAtIndex(source, 0, [
                kCGImageSourceCreateThumbnailFromImageAlways: true,
                kCGImageSourceCreateThumbnailWithTransform: true,
                kCGImageSourceThumbnailMaxPixelSize: 3000
              ] as CFDictionary) else { throw Failure.invalidImage }
        let request = VNRecognizeTextRequest()
        request.revision = VNRecognizeTextRequestRevision3
        request.recognitionLevel = .accurate
        request.usesLanguageCorrection = false
        guard try request.supportedRecognitionLanguages().contains("de-DE") else { throw Failure.unsupported }
        request.recognitionLanguages = ["de-DE"]
        try VNImageRequestHandler(cgImage: image, options: [:]).perform([request])
        let words = try NSRegularExpression(pattern: #"\S+"#)
        var tokens: [FoodLabelText] = []
        var lines: [String] = []
        var lowConfidenceCount = 0
        for observation in request.results ?? [] {
            let candidates = observation.topCandidates(3)
            guard let candidate = candidates.first else { continue }
            let conflictingNumbers = FoodLabelRecognition.hasConflictingNumbers(in: candidates.map(\.string))
            let text = candidate.string
            lines.append(text)
            if candidate.confidence < 0.5 { lowConfidenceCount += 1 }
            for match in words.matches(in: text, range: NSRange(text.startIndex..., in: text)) {
                guard let range = Range(match.range, in: text),
                      let word = try candidate.boundingBox(for: range) else { continue }
                let box = word.boundingBox
                let hasDigits = text[range].range(of: "[0-9]", options: .regularExpression) != nil
                tokens.append(.init(text: String(text[range]), x: box.minX, y: 1 - box.maxY,
                                    width: box.width, height: box.height,
                                    numberIsAmbiguous: conflictingNumbers && hasDigits))
                guard tokens.count <= 2048 else { throw Failure.tooMuchText }
            }
        }
        return Result(image: image, tokens: tokens, lines: lines, lowConfidenceCount: lowConfidenceCount)
    }
}