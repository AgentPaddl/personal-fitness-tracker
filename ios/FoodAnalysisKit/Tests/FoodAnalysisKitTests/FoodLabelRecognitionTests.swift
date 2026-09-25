import XCTest
@testable import FoodAnalysisKit

final class FoodLabelRecognitionTests: XCTestCase {
    private func token(_ text: String, _ x: Double, _ y: Double, width: Double = 0.08) -> FoodLabelText {
        .init(text: text, x: x, y: y, width: width, height: 0.025)
    }

    private func table() -> [FoodLabelText] {
        [token("pro", 0.48, 0.10), token("100", 0.58, 0.10), token("g", 0.67, 0.10, width: 0.02),
         token("Brennwert", 0.10, 0.20), token("840kJ", 0.43, 0.20), token("200kcal", 0.60, 0.20),
         token("Fett", 0.10, 0.26), token("4,5g", 0.60, 0.26),
         token("gesättigte Fettsäuren", 0.10, 0.31, width: 0.30), token("1,2g", 0.60, 0.31),
         token("Kohlenhydrate", 0.10, 0.37), token("30g", 0.60, 0.37),
         token("Eiweiß", 0.10, 0.43), token("8,2g", 0.60, 0.43)]
    }

    func testGermanDecimalCommaEnergyAndSaturatedFat() throws {
        let column = try XCTUnwrap(FoodLabelRecognition.columns(from: table()).first)
        XCTAssertEqual(column.quantity, 100)
        XCTAssertEqual(column.unit, .grams)
        XCTAssertEqual(column.calories, 200)
        XCTAssertEqual(column.fat, Decimal(string: "4.5"))
        XCTAssertEqual(column.carbs, 30)
        XCTAssertEqual(column.protein, Decimal(string: "8.2"))
    }

    func testTwoColumnsAreKeptSeparateAndPortionDoesNotBecome100Grams() throws {
        let tokens = [token("100g", 0.48, 0.10), token("Portion", 0.77, 0.06), token("30g", 0.77, 0.10),
                      token("Fett", 0.10, 0.20), token("10g", 0.48, 0.20), token("3g", 0.77, 0.20),
                      token("Eiweiß", 0.10, 0.26), token("20g", 0.48, 0.26), token("6g", 0.77, 0.26)]
        let columns = FoodLabelRecognition.columns(from: tokens.reversed())
        XCTAssertEqual(columns.count, 2)
        XCTAssertEqual(columns[0].quantity, 100)
        XCTAssertEqual(columns[0].fat, 10)
        XCTAssertEqual(columns[1].quantity, 30)
        XCTAssertEqual(columns[1].fat, 3)
        XCTAssertEqual(columns[1].protein, 6)
        XCTAssertTrue(columns[1].heading.contains("Portion"))
    }

    func testMissingValuesAndKilojoulesNeverBecomeZeroOrCalories() throws {
        let tokens = [token("100ml", 0.60, 0.10), token("Energie", 0.10, 0.20), token("800kJ", 0.60, 0.20),
                      token("Fett", 0.10, 0.26), token("0g", 0.60, 0.26)]
        let column = try XCTUnwrap(FoodLabelRecognition.columns(from: tokens).first)
        XCTAssertEqual(column.unit, .milliliters)
        XCTAssertNil(column.calories)
        XCTAssertEqual(column.fat, 0)
        XCTAssertNil(column.protein)
        XCTAssertNil(column.carbs)
    }

    func testUnknownPortionQuantityRemainsOpen() throws {
        let column = try XCTUnwrap(FoodLabelRecognition.columns(from: [token("Portion", 0.60, 0.10),
            token("Fett", 0.10, 0.20), token("3g", 0.60, 0.20)]).first)
        XCTAssertNil(column.quantity)
        XCTAssertNil(column.unit)
        XCTAssertEqual(column.fat, 3)
    }

    func testAmbiguousDuplicateRowsAndColumnBoundaryRemainOpen() throws {
        var tokens = table()
        tokens += [token("Eiweiß", 0.10, 0.50), token("5g", 0.60, 0.50)]
        XCTAssertNil(FoodLabelRecognition.columns(from: tokens).first?.protein)
        let columns = FoodLabelRecognition.columns(from: [token("100g", 0.45, 0.10), token("30g", 0.75, 0.10),
            token("Portion", 0.75, 0.06), token("Fett", 0.10, 0.20), token("3g", 0.60, 0.20)])
        XCTAssertEqual(columns.count, 2)
        XCTAssertTrue(columns.allSatisfy { $0.fat == nil })
    }

    func testInequalityUnsupportedUnitsAndUnitlessCellsStayOpen() {
        for text in ["<0,5g", "-2g", "2mg", "2", "1.234g", "5%", "NaNg"] {
            let columns = FoodLabelRecognition.columns(from: [token("100g", 0.60, 0.10),
                token("Fett", 0.10, 0.20), token(text, 0.60, 0.20)])
            XCTAssertNil(columns.first?.fat, text)
        }
    }

    func testExplicitRowUnitAndSplitValueUnit() throws {
        let column = try XCTUnwrap(FoodLabelRecognition.columns(from: [token("100g", 0.60, 0.10),
            token("Energie (kcal)", 0.10, 0.20), token("200", 0.60, 0.20),
            token("Fett", 0.10, 0.26), token("4,5", 0.58, 0.26), token("g", 0.67, 0.26)]).first)
        XCTAssertEqual(column.calories, 200)
        XCTAssertEqual(column.fat, Decimal(string: "4.5"))
    }

    func testInvalidGeometryAndUnheadedTableAreRejected() {
        XCTAssertTrue(FoodLabelRecognition.columns(from: [token("100g", -0.1, 0.1)]).isEmpty)
        XCTAssertTrue(FoodLabelRecognition.columns(from: [token("Fett", 0.1, 0.2), token("3g", 0.6, 0.2)]).isEmpty)
    }

    func testMultipleColumnsRequireExplicitSelection() throws {
        let columns = FoodLabelRecognition.columns(from: [token("100g", 0.48, 0.10),
            token("Portion", 0.77, 0.10), token("Fett", 0.10, 0.20),
            token("10g", 0.48, 0.20), token("3g", 0.77, 0.20)])
        XCTAssertEqual(columns.count, 2)
        XCTAssertNil(FoodLabelRecognition.selectedColumn(from: columns, id: nil))
        XCTAssertNil(FoodLabelRecognition.selectedColumn(from: columns, id: 8))
        XCTAssertEqual(FoodLabelRecognition.selectedColumn(from: columns, id: 1)?.fat, 3)
        XCTAssertNotNil(FoodLabelRecognition.selectedColumn(from: Array(columns.prefix(1)), id: nil))
    }

    func testSwitchingColumnsKeepsMissingAndZeroValuesWithTheirOwnBasis() throws {
        let columns = FoodLabelRecognition.columns(from: [token("100ml", 0.48, 0.10),
            token("Portion", 0.77, 0.06), token("250ml", 0.77, 0.10),
            token("Energie", 0.10, 0.20), token("40kcal", 0.48, 0.20), token("100kcal", 0.77, 0.20),
            token("Fett", 0.10, 0.26), token("0g", 0.48, 0.26),
            token("Eiweiß", 0.10, 0.32), token("5g", 0.77, 0.32)])
        let reference = try XCTUnwrap(FoodLabelRecognition.selectedColumn(from: columns, id: 0))
        let portion = try XCTUnwrap(FoodLabelRecognition.selectedColumn(from: columns, id: 1))
        XCTAssertEqual(reference.quantity, 100)
        XCTAssertEqual(reference.unit, .milliliters)
        XCTAssertEqual(reference.calories, 40)
        XCTAssertEqual(reference.fat, 0)
        XCTAssertNil(reference.protein)
        XCTAssertEqual(portion.quantity, 250)
        XCTAssertEqual(portion.unit, .milliliters)
        XCTAssertEqual(portion.calories, 100)
        XCTAssertEqual(portion.protein, 5)
        XCTAssertNil(portion.fat)
        XCTAssertNil(FoodLabelRecognition.selectedColumn(from: columns, id: nil))
        XCTAssertEqual(FoodLabelRecognition.selectedColumn(from: columns, id: 0), reference)
    }

    func testSecondRecognitionDoesNotReusePreviousValuesOrBasis() throws {
        var columns = FoodLabelRecognition.columns(from: table())
        XCTAssertNotNil(FoodLabelRecognition.selectedColumn(from: columns, id: nil)?.protein)
        columns = FoodLabelRecognition.columns(from: [token("Portion", 0.60, 0.10),
            token("Fett", 0.10, 0.20), token("0g", 0.60, 0.20)])
        let replacement = try XCTUnwrap(FoodLabelRecognition.selectedColumn(from: columns, id: nil))
        XCTAssertNil(replacement.quantity)
        XCTAssertNil(replacement.unit)
        XCTAssertNil(replacement.calories)
        XCTAssertNil(replacement.protein)
        XCTAssertNil(replacement.carbs)
        XCTAssertEqual(replacement.fat, 0)
        columns = FoodLabelRecognition.columns(from: [])
        XCTAssertNil(FoodLabelRecognition.selectedColumn(from: columns, id: 0))
    }

    func testExtraUnheadedColumnDoesNotSilentlySelectOneValue() throws {
        let columns = FoodLabelRecognition.columns(from: [token("100g", 0.48, 0.10),
            token("Fett", 0.10, 0.20), token("10g", 0.48, 0.20), token("3g", 0.77, 0.20)])
        XCTAssertNil(try XCTUnwrap(columns.first).fat)
    }

    func testPercentColumnIsNotANutrientOrPortion() throws {
        let columns = FoodLabelRecognition.columns(from: [token("100g", 0.48, 0.10),
            token("RI%", 0.77, 0.10), token("Fett", 0.10, 0.20),
            token("10g", 0.48, 0.20), token("14%", 0.77, 0.20)])
        XCTAssertEqual(columns.count, 1)
        XCTAssertEqual(columns.first?.fat, 10)
    }

    func testRepeatedValuesWithinOneColumnAndSplitInequalityRemainOpen() {
        for values in [[token("3g", 0.54, 0.20), token("4g", 0.66, 0.20)],
                       [token("<", 0.49, 0.20), token("0,5g", 0.60, 0.20)]] {
            let columns = FoodLabelRecognition.columns(from: [token("100g", 0.60, 0.10), token("Fett", 0.10, 0.20)] + values)
            XCTAssertNil(columns.first?.fat)
        }
    }

    func testStandaloneCaloriesAwayFromEnergyRowAreNotUsed() throws {
        let columns = FoodLabelRecognition.columns(from: [token("100g", 0.60, 0.10),
            token("Energie", 0.10, 0.20), token("840kJ", 0.60, 0.20),
            token("Fett", 0.10, 0.26), token("4g", 0.60, 0.26), token("200kcal", 0.60, 0.70)])
        XCTAssertNil(try XCTUnwrap(columns.first).calories)
        XCTAssertEqual(columns.first?.fat, 4)
    }

    func testOutOfRangeValuesAndUnsupportedBasisAreNotFilled() {
        let columns = FoodLabelRecognition.columns(from: [token("100g", 0.60, 0.10),
            token("Energie", 0.10, 0.20), token("10001kcal", 0.60, 0.20),
            token("Fett", 0.10, 0.26), token("1001g", 0.60, 0.26)])
        XCTAssertNil(columns.first?.calories)
        XCTAssertNil(columns.first?.fat)
        XCTAssertTrue(FoodLabelRecognition.columns(from: [token("1kg", 0.60, 0.10),
            token("Fett", 0.10, 0.20), token("3g", 0.60, 0.20)]).isEmpty)
    }

    func testPortableSyntheticFixtures() throws {
        struct Expected: Decodable {
            let quantity: String?
            let unit: String?
            let calories: String?
            let protein: String?
            let carbs: String?
            let fat: String?
        }
        struct Case: Decodable {
            let id: String
            let tokens: [FoodLabelText]
            let expected: [Expected]
        }
        struct Fixture: Decodable {
            let version: Int
            let coordinates: String
            let cases: [Case]
        }
        let url = try XCTUnwrap(Bundle.module.url(forResource: "nutrition-label-v1", withExtension: "json", subdirectory: "Fixtures"))
        let fixture = try JSONDecoder().decode(Fixture.self, from: Data(contentsOf: url))
        XCTAssertEqual(fixture.version, 1)
        XCTAssertEqual(fixture.coordinates, "normalized-top-left")
        for sample in fixture.cases {
            let columns = FoodLabelRecognition.columns(from: sample.tokens)
            XCTAssertEqual(columns.count, sample.expected.count, sample.id)
            for (column, expected) in zip(columns, sample.expected) {
                func decimal(_ text: String?) -> Decimal? { text.flatMap { Decimal(string: $0, locale: Locale(identifier: "en_US_POSIX")) } }
                XCTAssertEqual(column.quantity, decimal(expected.quantity), sample.id)
                XCTAssertEqual(column.unit?.rawValue, expected.unit, sample.id)
                XCTAssertEqual(column.calories, decimal(expected.calories), sample.id)
                XCTAssertEqual(column.protein, decimal(expected.protein), sample.id)
                XCTAssertEqual(column.carbs, decimal(expected.carbs), sample.id)
                XCTAssertEqual(column.fat, decimal(expected.fat), sample.id)
            }
        }
    }
}