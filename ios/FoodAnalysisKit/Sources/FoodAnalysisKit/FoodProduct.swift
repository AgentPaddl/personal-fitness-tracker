import Foundation

public enum FoodProductUnit: String, Codable, CaseIterable, Identifiable {
    case grams = "g", milliliters = "ml", piece = "piece"
    public var id: String { rawValue }
    public var title: String { self == .piece ? "Stueck" : rawValue }
}

public enum FoodProductOrigin: String, Codable, CaseIterable, Identifiable {
    case packaging, aiEstimate, manual
    public var id: String { rawValue }
    public var title: String {
        switch self {
        case .packaging: return "Verpackungswerte"
        case .aiEstimate: return "KI-Schaetzung"
        case .manual: return "Manuell / unbekannt"
        }
    }
}

public struct FoodProductNutrition: Equatable {
    public let calories: Decimal
    public let protein: Decimal
    public let carbs: Decimal
    public let fat: Decimal

    public init(calories: Decimal, protein: Decimal, carbs: Decimal, fat: Decimal) {
        self.calories = calories
        self.protein = protein
        self.carbs = carbs
        self.fat = fat
    }

    public var isValid: Bool {
        [calories, protein, carbs, fat].allSatisfy { !$0.isNaN && $0 >= 0 }
            && calories <= 10000 && protein <= 1000 && carbs <= 1000 && fat <= 1000
    }

    public var roundedCalories: Int { NSDecimalNumber(decimal: calories).rounding(accordingToBehavior:
        NSDecimalNumberHandler(roundingMode: .plain, scale: 0, raiseOnExactness: false,
                               raiseOnOverflow: false, raiseOnUnderflow: false, raiseOnDivideByZero: false)).intValue }
}

public struct FoodProductBasis: Equatable {
    public let quantity: Decimal
    public let unit: FoodProductUnit
    public let origin: FoodProductOrigin
    public let nutrition: FoodProductNutrition

    public init?(quantity: Decimal, unit: FoodProductUnit, origin: FoodProductOrigin,
                 nutrition: FoodProductNutrition) {
        guard !quantity.isNaN, quantity > 0, quantity <= 1_000_000, nutrition.isValid else { return nil }
        self.quantity = quantity
        self.unit = unit
        self.origin = origin
        self.nutrition = nutrition
    }

    public func scaled(to amount: Decimal, unit requestedUnit: FoodProductUnit) -> FoodProductNutrition? {
        guard requestedUnit == unit, !amount.isNaN, amount > 0, amount <= 1_000_000 else { return nil }
        let factor = amount / quantity
        let result = FoodProductNutrition(calories: nutrition.calories * factor,
            protein: nutrition.protein * factor, carbs: nutrition.carbs * factor, fat: nutrition.fat * factor)
        return result.isValid ? result : nil
    }

    public static func parseQuantity(_ text: String) -> Decimal? {
        guard let value = parseNumber(text), value > 0, value <= 1_000_000 else { return nil }
        return value
    }

    public static func parseNumber(_ text: String) -> Decimal? {
        let normalized = text.trimmingCharacters(in: .whitespacesAndNewlines).replacingOccurrences(of: ",", with: ".")
        guard normalized.range(of: #"^[0-9]+(?:\.[0-9]+)?$"#, options: .regularExpression) != nil,
              let value = Decimal(string: normalized, locale: Locale(identifier: "en_US_POSIX")),
              !value.isNaN, value >= 0 else { return nil }
        return value
    }
}