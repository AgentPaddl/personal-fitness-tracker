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
        let clippedWordCount: Int
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
        let recoveredLabels = labels(in: image)
        let words = try NSRegularExpression(pattern: #"\S+?(?:(?<=[kK][jJ])/(?=[0-9])|(?=\s|$))"#)
        var tokens: [FoodLabelText] = []
        var lines: [String] = []
        var lowConfidenceCount = 0
        var clippedWordCount = 0
        for (lineID, observation) in (request.results ?? []).enumerated() {
            let candidates = observation.topCandidates(3)
            guard let candidate = candidates.first else { continue }
            let conflictingNumbers = FoodLabelRecognition.hasConflictingNumbers(in: candidates.map(\.string))
            let text = candidate.string
            let alternativeWords = candidates.dropFirst().map { $0.string.split(whereSeparator: \.isWhitespace).map(String.init) }
            let primaryWords = text.split(whereSeparator: \.isWhitespace)
            let horizontal = observation.topRight.x - observation.topLeft.x
            let slope = horizontal > 0 ? -(observation.topRight.y - observation.topLeft.y) / horizontal : nil
            lines.append(text)
            if candidate.confidence < 0.5 { lowConfidenceCount += 1 }
            let matches = words.matches(in: text, range: NSRange(text.startIndex..., in: text))
            for (wordIndex, match) in matches.enumerated() {
                guard let range = Range(match.range, in: text),
                      let word = try candidate.boundingBox(for: range) else { continue }
                let box = word.boundingBox
                let hasDigits = text[range].range(of: "[0-9]", options: .regularExpression) != nil
                var alternatives = matches.count == primaryWords.count && !hasDigits
                    ? alternativeWords.filter { $0.count == primaryWords.count }.map { $0[wordIndex] } : []
                if !hasDigits, !FoodLabelRecognition.isSupportedLabel(String(text[range])) {
                    alternatives += recoveredLabels.compactMap { label, labelBox in
                        let intersection = box.intersection(labelBox)
                        let overlap = intersection.isNull ? 0 : intersection.width * intersection.height
                        let union = box.width * box.height + labelBox.width * labelBox.height - overlap
                        return union > 0 && overlap / union >= 0.8 ? label : nil
                    }
                }
                let token = FoodLabelText(text: String(text[range]), x: box.minX, y: 1 - box.maxY,
                                          width: box.width, height: box.height,
                                          numberIsAmbiguous: conflictingNumbers && hasDigits,
                                          lineID: lineID, lineSlope: slope.map(Double.init), alternatives: alternatives)
                let clipped = token.clippedToImageBounds()
                if clipped != token { clippedWordCount += 1 }
                tokens.append(clipped)
                guard tokens.count <= 2048 else { throw Failure.tooMuchText }
            }
        }
        let cropCandidates = tokens.indices.filter { index in
            let token = tokens[index]
            return token.text.count >= 3 && !FoodLabelRecognition.isSupportedLabel(token.text)
                && !(token.alternatives ?? []).contains(where: FoodLabelRecognition.isSupportedLabel)
                && token.text.range(of: "[0-9]", options: .regularExpression) == nil
                && tokens.contains { value in
                    value.x > token.x + token.width
                        && abs(value.y + value.height / 2 - token.y - token.height / 2) < max(value.height, token.height)
                        && value.text.range(of: "[0-9]", options: .regularExpression) != nil
                }
        }
        for index in cropCandidates.prefix(32) {
            try Task.checkCancellation()
            let token = tokens[index]
            let rect = CGRect(x: token.x * Double(image.width), y: token.y * Double(image.height),
                width: token.width * Double(image.width), height: token.height * Double(image.height))
            let cropRect = rect.insetBy(dx: -rect.width * 0.15, dy: -rect.height * 0.35).integral
                .intersection(CGRect(x: 0, y: 0, width: image.width, height: image.height))
            guard let crop = image.cropping(to: cropRect) else { continue }
            let recovered = labels(in: crop).compactMap { label, box -> String? in
                let labelRect = CGRect(x: cropRect.minX + box.minX * cropRect.width,
                    y: cropRect.minY + (1 - box.maxY) * cropRect.height,
                    width: box.width * cropRect.width, height: box.height * cropRect.height)
                let intersection = rect.intersection(labelRect)
                let overlap = intersection.isNull ? 0 : intersection.width * intersection.height
                let union = rect.width * rect.height + labelRect.width * labelRect.height - overlap
                return union > 0 && overlap / union >= 0.8 ? label : nil
            }
            guard !recovered.isEmpty else { continue }
            tokens[index] = FoodLabelText(text: token.text, x: token.x, y: token.y, width: token.width, height: token.height,
                numberIsAmbiguous: token.numberIsAmbiguous, lineID: token.lineID, lineSlope: token.lineSlope,
                alternatives: (token.alternatives ?? []) + recovered)
        }
        return Result(image: image, tokens: tokens, lines: lines, lowConfidenceCount: lowConfidenceCount,
                  clippedWordCount: clippedWordCount)
    }

    nonisolated private static func labels(in image: CGImage) -> [(String, CGRect)] {
        let request = VNRecognizeTextRequest()
        request.revision = VNRecognizeTextRequestRevision3
        request.recognitionLevel = .accurate
        request.usesLanguageCorrection = true
        request.recognitionLanguages = ["de-DE", "en-US"].filter { (try? request.supportedRecognitionLanguages().contains($0)) == true }
        guard !request.recognitionLanguages.isEmpty else { return [] }
        request.customWords = FoodLabelRecognition.supportedLabels
        do { try VNImageRequestHandler(cgImage: image, options: [:]).perform([request]) }
        catch { return [] }
        return (request.results ?? []).compactMap { observation in
            guard let candidate = observation.topCandidates(1).first, candidate.confidence >= 0.8,
                  FoodLabelRecognition.isSupportedLabel(candidate.string) else { return nil }
            return (candidate.string, observation.boundingBox)
        }
    }
}