import Foundation

public struct FoodAnalysisOperation: Equatable, Sendable {
    public enum Input: Equatable, Sendable {
        case text(String)
        case image(data: Data, mimeType: String, description: String?)
        case refinement(FoodAnalysisRefinementRequestDTO)
    }

    public static let headerName = "X-Operation-Id"
    public let id: UUID
    public let input: Input
    public let contentType: String
    public let body: Data
    let accountBinding = OperationAccountBinding()

    public static func == (lhs: Self, rhs: Self) -> Bool {
        lhs.id == rhs.id && lhs.input == rhs.input && lhs.contentType == rhs.contentType && lhs.body == rhs.body
    }

    public init(input: Input, now: Date = Date()) throws {
        let milliseconds = floor(now.timeIntervalSince1970 * 1_000)
        guard milliseconds.isFinite, milliseconds >= 0, milliseconds < 281_474_976_710_656 else {
            throw CocoaError(.coderInvalidValue)
        }
        let timestamp = UInt64(milliseconds)
        var random = SystemRandomNumberGenerator()
        var bytes = (0..<16).map { _ in UInt8.random(in: .min ... .max, using: &random) }
        for index in 0..<6 {
            bytes[index] = UInt8(truncatingIfNeeded: timestamp >> ((5 - index) * 8))
        }
        bytes[6] = (bytes[6] & 0x0f) | 0x70
        bytes[8] = (bytes[8] & 0x3f) | 0x80
        id = UUID(uuid: (bytes[0], bytes[1], bytes[2], bytes[3], bytes[4], bytes[5], bytes[6], bytes[7],
                         bytes[8], bytes[9], bytes[10], bytes[11], bytes[12], bytes[13], bytes[14], bytes[15]))
        self.input = input
        let encoder = JSONEncoder()
        encoder.outputFormatting = [.sortedKeys]
        switch input {
        case .text(let description):
            contentType = "application/json"
            body = try encoder.encode(FoodAnalysisRequestDTO(foodDescription: description))
        case .refinement(let request):
            contentType = "application/json"
            body = try encoder.encode(request)
        case .image(let data, let mimeType, let description):
            let boundary = "Boundary-\(id.uuidString)"
            contentType = "multipart/form-data; boundary=\(boundary)"
            body = FoodAnalysisService.multipartBody(
                boundary: boundary, imageData: data, mimeType: mimeType, description: description
            )
        }
    }
}

actor OperationAccountBinding {
    private var identifier: String?

    func validate(_ accountIdentifier: String) throws {
        guard !accountIdentifier.isEmpty else { throw FoodAnalysisError.authenticationRequired }
        if let identifier, identifier != accountIdentifier {
            throw FoodAnalysisError.operationAccountChanged
        }
        identifier = accountIdentifier
    }
}
