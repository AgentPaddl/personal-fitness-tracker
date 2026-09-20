import Foundation
import SwiftData
import FoodAnalysisKit

@Model
final class FoodEntry {
    var date: Date
    var name: String
    var calories: Int
    var proteinGrams: Double
    var carbsGrams: Double
    var fatGrams: Double
    var notes: String?
    var valueOrigin: String?
    var consumedQuantity: String?
    var consumedUnit: String?

    init(
        date: Date = Date(),
        name: String,
        calories: Int,
        proteinGrams: Double,
        carbsGrams: Double,
        fatGrams: Double,
        notes: String? = nil,
        valueOrigin: String? = nil,
        consumedQuantity: String? = nil,
        consumedUnit: String? = nil
    ) {
        self.date = date
        self.name = name
        self.calories = calories
        self.proteinGrams = proteinGrams
        self.carbsGrams = carbsGrams
        self.fatGrams = fatGrams
        self.notes = notes
        self.valueOrigin = valueOrigin
        self.consumedQuantity = consumedQuantity
        self.consumedUnit = consumedUnit
    }

    var originTitle: String {
        valueOrigin.flatMap(FoodProductOrigin.init(rawValue:))?.title ?? "Herkunft unbekannt"
    }

    func invalidateOriginIfEdited(name: String, calories: Int, protein: Double, carbs: Double, fat: Double) {
        if self.name != name || self.calories != calories || proteinGrams != protein
            || carbsGrams != carbs || fatGrams != fat {
            if valueOrigin != nil { valueOrigin = FoodProductOrigin.manual.rawValue }
            consumedQuantity = nil
            consumedUnit = nil
        }
    }
}
