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

public enum FoodAnalysisSourceKind: String, Codable, Equatable, Sendable {
    case text
    case image
    case textAndImage = "text_and_image"
}

public struct FoodAnalysisRefinementCurrentEstimateDTO: Encodable, Equatable, Sendable {
    public let foodName: String
    public let calories: Double
    public let proteinGrams: Double
    public let carbohydrateGrams: Double
    public let fatGrams: Double
    public let confidence: Double
    public let warnings: [String]
    public let assumptions: [String]

    public init(
        foodName: String,
        calories: Double,
        proteinGrams: Double,
        carbohydrateGrams: Double,
        fatGrams: Double,
        confidence: Double,
        warnings: [String],
        assumptions: [String]
    ) {
        self.foodName = foodName
        self.calories = calories
        self.proteinGrams = proteinGrams
        self.carbohydrateGrams = carbohydrateGrams
        self.fatGrams = fatGrams
        self.confidence = confidence
        self.warnings = warnings
        self.assumptions = assumptions
    }

    private enum CodingKeys: String, CodingKey {
        case foodName = "food_name"
        case calories
        case proteinGrams = "protein_grams"
        case carbohydrateGrams = "carbohydrate_grams"
        case fatGrams = "fat_grams"
        case confidence
        case warnings
        case assumptions
    }
}

public struct FoodAnalysisRefinementDTO: Encodable, Equatable, Sendable {
    public let correctionText: String
    public let currentEstimate: FoodAnalysisRefinementCurrentEstimateDTO
    public let sourceKind: FoodAnalysisSourceKind
    public let iteration: Int

    public init(
        correctionText: String,
        currentEstimate: FoodAnalysisRefinementCurrentEstimateDTO,
        sourceKind: FoodAnalysisSourceKind,
        iteration: Int
    ) {
        self.correctionText = correctionText
        self.currentEstimate = currentEstimate
        self.sourceKind = sourceKind
        self.iteration = iteration
    }

    private enum CodingKeys: String, CodingKey {
        case correctionText = "correction_text"
        case currentEstimate = "current_estimate"
        case sourceKind = "source_kind"
        case iteration
    }
}

/// JSON-only request for a stateless refinement. It deliberately has no
/// image field, so image bytes cannot be represented or transmitted here.
public struct FoodAnalysisRefinementRequestDTO: Encodable, Equatable, Sendable {
    public let foodDescription: String?
    public let refinement: FoodAnalysisRefinementDTO

    public init(foodDescription: String?, refinement: FoodAnalysisRefinementDTO) {
        self.foodDescription = foodDescription
        self.refinement = refinement
    }

    private enum CodingKeys: String, CodingKey {
        case foodDescription = "food_description"
        case refinement
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
        public let assumptions: [String]

        public init(
            foodName: String,
            calories: Double,
            proteinGrams: Double,
            carbohydrateGrams: Double,
            fatGrams: Double,
            confidence: Double,
            warnings: [String] = [],
            assumptions: [String] = []
        ) {
            self.foodName = foodName
            self.calories = calories
            self.proteinGrams = proteinGrams
            self.carbohydrateGrams = carbohydrateGrams
            self.fatGrams = fatGrams
            self.confidence = confidence
            self.warnings = warnings
            self.assumptions = assumptions
        }

        public init(from decoder: Decoder) throws {
            let container = try decoder.container(keyedBy: CodingKeys.self)
            foodName = try container.decode(String.self, forKey: .foodName)
            calories = try container.decode(Double.self, forKey: .calories)
            proteinGrams = try container.decode(Double.self, forKey: .proteinGrams)
            carbohydrateGrams = try container.decode(Double.self, forKey: .carbohydrateGrams)
            fatGrams = try container.decode(Double.self, forKey: .fatGrams)
            confidence = try container.decode(Double.self, forKey: .confidence)
            warnings = try container.decode([String].self, forKey: .warnings)
            assumptions = try container.decodeIfPresent([String].self, forKey: .assumptions) ?? []
        }

        private enum CodingKeys: String, CodingKey {
            case foodName = "food_name"
            case calories
            case proteinGrams = "protein_grams"
            case carbohydrateGrams = "carbohydrate_grams"
            case fatGrams = "fat_grams"
            case confidence
            case warnings
            case assumptions
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
