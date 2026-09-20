import Foundation
import SwiftData
import FoodAnalysisKit

@MainActor
final class FoodProductPersistence {
    private let coordinator = FoodEntryPersistenceCoordinator()

    func saveProduct(name: String, basis: FoodProductBasis, in context: ModelContext,
                     save: (ModelContext) throws -> Void = { try $0.save() }) -> FoodEntrySaveResult {
        let name = name.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !name.isEmpty else { return .skipped }
        let isolated = ModelContext(context.container)
        isolated.autosaveEnabled = false
        let nutrition = basis.nutrition
        let preset = FoodPreset(name: name, calories: nutrition.roundedCalories,
            proteinGrams: NSDecimalNumber(decimal: nutrition.protein).doubleValue,
            carbsGrams: NSDecimalNumber(decimal: nutrition.carbs).doubleValue,
            fatGrams: NSDecimalNumber(decimal: nutrition.fat).doubleValue,
            baseQuantity: NSDecimalNumber(decimal: basis.quantity).stringValue, baseUnit: basis.unit.rawValue,
            valueOrigin: basis.origin.rawValue, baseCalories: NSDecimalNumber(decimal: nutrition.calories).stringValue)
        return coordinator.save(insert: { isolated.insert(preset) }, persist: { try save(isolated) },
                                rollback: { isolated.rollback() })
    }

    func savePortion(of preset: FoodPreset, quantity: Decimal, in context: ModelContext,
                     save: (ModelContext) throws -> Void = { try $0.save() }) -> FoodEntrySaveResult {
        guard let basis = preset.productBasis,
              let nutrition = basis.scaled(to: quantity, unit: basis.unit),
              !preset.name.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty else { return .skipped }
        let isolated = ModelContext(context.container)
        isolated.autosaveEnabled = false
        let entry = FoodEntry(name: preset.name, calories: nutrition.roundedCalories,
            proteinGrams: NSDecimalNumber(decimal: nutrition.protein).doubleValue,
            carbsGrams: NSDecimalNumber(decimal: nutrition.carbs).doubleValue,
            fatGrams: NSDecimalNumber(decimal: nutrition.fat).doubleValue,
            valueOrigin: basis.origin.rawValue, consumedQuantity: NSDecimalNumber(decimal: quantity).stringValue,
            consumedUnit: basis.unit.rawValue)
        return coordinator.save(insert: { isolated.insert(entry) }, persist: { try save(isolated) },
                                rollback: { isolated.rollback() })
    }
}