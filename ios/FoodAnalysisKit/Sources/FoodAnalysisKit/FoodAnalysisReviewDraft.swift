import Foundation

/// Editable, non-persisted review state derived from an AI estimate.
///
/// This is never written to SwiftData directly: the user must review and
/// can correct it, and it only becomes persistable food-entry data after
/// explicit confirmation via ``validated()``.
public struct FoodAnalysisReviewDraft: Identifiable, Equatable, Sendable {
    public let id: UUID
    public var name: String
    public var calories: String
    public var protein: String
    public var carbs: String
    public var fat: String
    /// Estimate metadata shown for review only; intentionally not part of
    /// ``ValidatedFoodEntryInput`` so it never reaches SwiftData.
    public let confidence: Double
    public let warnings: [String]

    public init(id: UUID = UUID(), estimate: FoodAnalysisResponseDTO.Estimate) {
        self.id = id
        self.name = estimate.foodName
        self.calories = String(Int(estimate.calories.rounded()))
        self.protein = Self.formatted(estimate.proteinGrams)
        self.carbs = Self.formatted(estimate.carbohydrateGrams)
        self.fat = Self.formatted(estimate.fatGrams)
        self.confidence = estimate.confidence
        self.warnings = estimate.warnings
    }

    private static func formatted(_ value: Double) -> String {
        String(format: "%.1f", value)
    }
}

/// A validated, ready-to-persist food entry input, kept independent of any
/// SwiftData model so this mapping stays testable without a persistence
/// stack.
public struct ValidatedFoodEntryInput: Equatable, Sendable {
    public let name: String
    public let calories: Int
    public let proteinGrams: Double
    public let carbsGrams: Double
    public let fatGrams: Double
}

extension FoodAnalysisReviewDraft {
    /// Numeric bounds mirrored from the backend's own contract
    /// (`backend/schemas.py::FoodAnalysisPublicEstimate`), applied here as
    /// defense-in-depth. A `ClosedRange` comparison against NaN is always
    /// `false`, so this also rejects non-finite values (NaN/±infinity)
    /// without a separate `isFinite` check.
    private enum Bounds {
        static let calories = 0.0...10_000.0
        static let macroGrams = 0.0...1_000.0
    }

    /// Validates the current (possibly user-edited) values.
    ///
    /// Returns `nil` if any field is missing, unparsable, negative,
    /// non-finite, or out of bounds, mirroring the existing app's manual
    /// food-entry validation rules (see `NutritionView`/`EditFoodEntryView`),
    /// including accepting a comma as a decimal separator.
    ///
    /// Calories rounding rule: the calories field is parsed as a decimal
    /// (like the other fields) and rounded to the nearest whole number,
    /// consistent with the rounding already applied when the estimate is
    /// first shown for review (see `init(estimate:)`). For example, both
    /// `"95.4"` and `"95.6"` are accepted and become `95` and `96`
    /// respectively.
    public func validated() -> ValidatedFoodEntryInput? {
        let trimmedName = name.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !trimmedName.isEmpty else { return nil }

        guard let caloriesValue = Self.parseDecimal(calories), Bounds.calories.contains(caloriesValue) else {
            return nil
        }
        guard let protein = Self.parseDecimal(protein), Bounds.macroGrams.contains(protein) else {
            return nil
        }
        guard let carbs = Self.parseDecimal(carbs), Bounds.macroGrams.contains(carbs) else {
            return nil
        }
        guard let fat = Self.parseDecimal(fat), Bounds.macroGrams.contains(fat) else {
            return nil
        }

        return ValidatedFoodEntryInput(
            name: trimmedName,
            calories: Int(caloriesValue.rounded()),
            proteinGrams: protein,
            carbsGrams: carbs,
            fatGrams: fat
        )
    }

    private static func parseDecimal(_ text: String) -> Double? {
        Double(text.trimmingCharacters(in: .whitespacesAndNewlines).replacingOccurrences(of: ",", with: "."))
    }
}
