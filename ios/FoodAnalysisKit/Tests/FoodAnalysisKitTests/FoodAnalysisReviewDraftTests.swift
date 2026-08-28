import XCTest

@testable import FoodAnalysisKit

final class FoodAnalysisReviewDraftTests: XCTestCase {
    private func makeEstimate() -> FoodAnalysisResponseDTO.Estimate {
        FoodAnalysisResponseDTO.Estimate(
            foodName: "Apfel und Vollkornbrot",
            calories: 241,
            proteinGrams: 4.5,
            carbohydrateGrams: 43,
            fatGrams: 5.5,
            confidence: 0.7,
            warnings: ["Portionsgrößen geschätzt"]
        )
    }

    func testDraftIsPrefilledFromEstimate() {
        let draft = FoodAnalysisReviewDraft(estimate: makeEstimate())

        XCTAssertEqual(draft.name, "Apfel und Vollkornbrot")
        XCTAssertEqual(draft.calories, "241")
        XCTAssertEqual(draft.protein, "4.5")
        XCTAssertEqual(draft.carbs, "43.0")
        XCTAssertEqual(draft.fat, "5.5")
        XCTAssertEqual(draft.confidence, 0.7)
        XCTAssertEqual(draft.warnings, ["Portionsgrößen geschätzt"])
    }

    func testValidatedReturnsInputForWellFormedDraft() throws {
        let draft = FoodAnalysisReviewDraft(estimate: makeEstimate())

        let input = try XCTUnwrap(draft.validated())

        XCTAssertEqual(input.name, "Apfel und Vollkornbrot")
        XCTAssertEqual(input.calories, 241)
        XCTAssertEqual(input.proteinGrams, 4.5)
        XCTAssertEqual(input.carbsGrams, 43)
        XCTAssertEqual(input.fatGrams, 5.5)
    }

    func testValidatedAcceptsCommaDecimalSeparator() {
        var draft = FoodAnalysisReviewDraft(estimate: makeEstimate())
        draft.protein = "4,5"

        XCTAssertEqual(draft.validated()?.proteinGrams, 4.5)
    }

    func testValidatedTrimsWhitespaceFromName() {
        var draft = FoodAnalysisReviewDraft(estimate: makeEstimate())
        draft.name = "  Apfel  "

        XCTAssertEqual(draft.validated()?.name, "Apfel")
    }

    func testValidatedRejectsBlankName() {
        var draft = FoodAnalysisReviewDraft(estimate: makeEstimate())
        draft.name = "   "

        XCTAssertNil(draft.validated())
    }

    func testValidatedRejectsUnparsableCalories() {
        var draft = FoodAnalysisReviewDraft(estimate: makeEstimate())
        draft.calories = "viel"

        XCTAssertNil(draft.validated())
    }

    func testValidatedRejectsBlankMacro() {
        var draft = FoodAnalysisReviewDraft(estimate: makeEstimate())
        draft.fat = ""

        XCTAssertNil(draft.validated())
    }

    func testValidatedRejectsUnparsableMacro() {
        var draft = FoodAnalysisReviewDraft(estimate: makeEstimate())
        draft.carbs = "viele"

        XCTAssertNil(draft.validated())
    }
}
