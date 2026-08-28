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
    /// Validates the current (possibly user-edited) values.
    ///
    /// Returns `nil` if any field is missing or unparsable, mirroring the
    /// existing app's manual food-entry validation rules (see
    /// `NutritionView`/`EditFoodEntryView`), including accepting a comma as
    /// a decimal separator.
    public func validated() -> ValidatedFoodEntryInput? {
        let trimmedName = name.trimmingCharacters(in: .whitespacesAndNewlines)
        guard
            !trimmedName.isEmpty,
            let calories = Int(calories.trimmingCharacters(in: .whitespacesAndNewlines)),
            let protein = Self.parseDecimal(protein),
            let carbs = Self.parseDecimal(carbs),
            let fat = Self.parseDecimal(fat)
        else {
            return nil
        }
        return ValidatedFoodEntryInput(
            name: trimmedName,
            calories: calories,
            proteinGrams: protein,
            carbsGrams: carbs,
            fatGrams: fat
        )
    }

    private static func parseDecimal(_ text: String) -> Double? {
        Double(text.trimmingCharacters(in: .whitespacesAndNewlines).replacingOccurrences(of: ",", with: "."))
    }
}
