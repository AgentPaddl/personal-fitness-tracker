import Foundation

/// Request body for `POST /api/food-analysis` on the Fitness API backend.
/// Mirrors only the backend's public contract (`backend/schemas.py`) - never
/// any gateway/provider-specific field.
public struct FoodAnalysisRequestDTO: Encodable, Equatable, Sendable {
    public let foodDescription: String

    public init(foodDescription: String) {
        self.foodDescription = foodDescription
    }

    private enum CodingKeys: String, CodingKey {
        case foodDescription = "food_description"
    }
}

/// Successful response body from `POST /api/food-analysis`.
public struct FoodAnalysisResponseDTO: Decodable, Equatable, Sendable {
    public struct Estimate: Decodable, Equatable, Sendable {
        public let foodName: String
        public let calories: Double
        public let proteinGrams: Double
        public let carbohydrateGrams: Double
        public let fatGrams: Double
        public let confidence: Double
        public let warnings: [String]

        public init(
            foodName: String,
            calories: Double,
            proteinGrams: Double,
            carbohydrateGrams: Double,
            fatGrams: Double,
            confidence: Double,
            warnings: [String] = []
        ) {
            self.foodName = foodName
            self.calories = calories
            self.proteinGrams = proteinGrams
            self.carbohydrateGrams = carbohydrateGrams
            self.fatGrams = fatGrams
            self.confidence = confidence
            self.warnings = warnings
        }

        private enum CodingKeys: String, CodingKey {
            case foodName = "food_name"
            case calories
            case proteinGrams = "protein_grams"
            case carbohydrateGrams = "carbohydrate_grams"
            case fatGrams = "fat_grams"
            case confidence
            case warnings
        }
    }

    public let estimate: Estimate

    public init(estimate: Estimate) {
        self.estimate = estimate
    }
}

/// The backend's normalized `{"error": {"code": ..., "message": ...}}`
/// envelope. Only `code` is used for classification; `message` is never
/// shown to the user verbatim (see `FoodAnalysisError`).
struct BackendErrorEnvelope: Decodable {
    struct ErrorBody: Decodable {
        let code: String
        let message: String
    }
    let error: ErrorBody
}
