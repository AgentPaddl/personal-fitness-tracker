import XCTest
@testable import FoodAnalysisKit

final class FoodProductTests: XCTestCase {
    func testScalingKeepsBasisAndRejectsDifferentUnits() throws {
        let values = FoodProductNutrition(calories: 123, protein: 10, carbs: 15, fat: 4)
        let basis = try XCTUnwrap(FoodProductBasis(quantity: 100, unit: .grams, origin: .packaging, nutrition: values))
        let portion = try XCTUnwrap(basis.scaled(to: 250, unit: .grams))
        XCTAssertEqual(portion.calories, Decimal(string: "307.5"))
        XCTAssertEqual(portion.roundedCalories, 308)
        XCTAssertEqual(portion.protein, 25)
        XCTAssertEqual(basis.quantity, 100)
        XCTAssertEqual(basis.nutrition, values)
        XCTAssertEqual(basis.scaled(to: 100, unit: .grams), values)
        XCTAssertNil(basis.scaled(to: 100, unit: .milliliters))
        XCTAssertNil(basis.scaled(to: 1, unit: .piece))
    }

    func testMissingAndInvalidQuantitiesAndOverflowAreRejected() throws {
        for text in ["", "0", "-1", "NaN", "Infinity", "1e2", "2 g", "1.2.3", "1000001"] {
            XCTAssertNil(FoodProductBasis.parseQuantity(text), text)
        }
        XCTAssertEqual(FoodProductBasis.parseQuantity(" 12,5 "), Decimal(string: "12.5"))
        let values = FoodProductNutrition(calories: 10000, protein: 1000, carbs: 0, fat: 0)
        XCTAssertNil(FoodProductBasis(quantity: 0, unit: .grams, origin: .manual, nutrition: values))
        let basis = try XCTUnwrap(FoodProductBasis(quantity: 1, unit: .piece, origin: .aiEstimate, nutrition: values))
        XCTAssertNil(basis.scaled(to: Decimal(string: "1.00000000000001")!, unit: .piece))
        XCTAssertNil(basis.scaled(to: 0, unit: .piece))
        XCTAssertEqual(basis.origin, .aiEstimate)
    }
}