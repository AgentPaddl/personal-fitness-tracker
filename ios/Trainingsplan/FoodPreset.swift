import Foundation
import SwiftData
import FoodAnalysisKit

@Model
final class FoodPreset {
    var name: String
    var calories: Int
    var proteinGrams: Double
    var carbsGrams: Double
    var fatGrams: Double
    var createdAt: Date
    var baseQuantity: String?
    var baseUnit: String?
    var valueOrigin: String?
    var baseCalories: String?

    init(
        name: String,
        calories: Int,
        proteinGrams: Double,
        carbsGrams: Double,
        fatGrams: Double,
        createdAt: Date = Date(),
        baseQuantity: String? = nil,
        baseUnit: String? = nil,
        valueOrigin: String? = nil,
        baseCalories: String? = nil
    ) {
        self.name = name
        self.calories = calories
        self.proteinGrams = proteinGrams
        self.carbsGrams = carbsGrams
        self.fatGrams = fatGrams
        self.createdAt = createdAt
        self.baseQuantity = baseQuantity
        self.baseUnit = baseUnit
        self.valueOrigin = valueOrigin
        self.baseCalories = baseCalories
    }

    var productBasis: FoodProductBasis? {
        guard let baseQuantity, let quantity = FoodProductBasis.parseQuantity(baseQuantity),
              let baseUnit, let unit = FoodProductUnit(rawValue: baseUnit),
              let valueOrigin, let origin = FoodProductOrigin(rawValue: valueOrigin),
              let caloriesValue = FoodProductBasis.parseNumber(baseCalories ?? String(calories)),
              proteinGrams.isFinite, carbsGrams.isFinite, fatGrams.isFinite else { return nil }
        return FoodProductBasis(quantity: quantity, unit: unit, origin: origin,
            nutrition: FoodProductNutrition(calories: caloriesValue, protein: Decimal(proteinGrams),
                                             carbs: Decimal(carbsGrams), fat: Decimal(fatGrams)))
    }
}
