import XCTest

@testable import FoodAnalysisKit

final class FoodAnalysisDTOsTests: XCTestCase {
    func testRequestEncodesSnakeCaseKey() throws {
        let dto = FoodAnalysisRequestDTO(foodDescription: "Ein Apfel")

        let data = try JSONEncoder().encode(dto)
        let json = try JSONSerialization.jsonObject(with: data) as? [String: Any]

        XCTAssertEqual(json?["food_description"] as? String, "Ein Apfel")
        XCTAssertEqual(json?.count, 1)
    }

    func testResponseDecodesBackendContract() throws {
        let json = """
            {"estimate": {"food_name": "Apfel", "calories": 95, "protein_grams": 0.5,
            "carbohydrate_grams": 25, "fat_grams": 0.3, "confidence": 0.8, "warnings": []}}
            """.data(using: .utf8)!

        let decoded = try JSONDecoder().decode(FoodAnalysisResponseDTO.self, from: json)

        XCTAssertEqual(decoded.estimate.foodName, "Apfel")
        XCTAssertEqual(decoded.estimate.calories, 95)
        XCTAssertEqual(decoded.estimate.proteinGrams, 0.5)
        XCTAssertEqual(decoded.estimate.carbohydrateGrams, 25)
        XCTAssertEqual(decoded.estimate.fatGrams, 0.3)
        XCTAssertEqual(decoded.estimate.confidence, 0.8)
        XCTAssertEqual(decoded.estimate.warnings, [])
        XCTAssertEqual(decoded.estimate.assumptions, [])
    }

    func testResponseDecodesAssumptionsSeparatelyFromWarnings() throws {
        let json = """
            {"estimate": {"food_name": "Apfel", "calories": 95, "protein_grams": 0.5,
            "carbohydrate_grams": 25, "fat_grams": 0.3, "confidence": 0.8,
            "warnings": ["Warnung"], "assumptions": ["Annahme"]}}
            """.data(using: .utf8)!

        let decoded = try JSONDecoder().decode(FoodAnalysisResponseDTO.self, from: json)

        XCTAssertEqual(decoded.estimate.warnings, ["Warnung"])
        XCTAssertEqual(decoded.estimate.assumptions, ["Annahme"])
    }

    func testRefinementRequestEncodesExactSnakeCaseContractWithoutImage() throws {
        let dto = makeRefinementRequest(sourceKind: .text)

        let data = try JSONEncoder().encode(dto)
        let json = try XCTUnwrap(JSONSerialization.jsonObject(with: data) as? [String: Any])
        let refinement = try XCTUnwrap(json["refinement"] as? [String: Any])
        let estimate = try XCTUnwrap(refinement["current_estimate"] as? [String: Any])

        XCTAssertEqual(Set(json.keys), ["food_description", "refinement"])
        XCTAssertNil(json["image"])
        XCTAssertEqual(
            Set(refinement.keys), ["correction_text", "current_estimate", "source_kind", "iteration"]
        )
        XCTAssertEqual(refinement["correction_text"] as? String, "Nur die Hälfte gegessen")
        XCTAssertEqual(refinement["source_kind"] as? String, "text")
        XCTAssertEqual(refinement["iteration"] as? Int, 2)
        XCTAssertEqual(
            Set(estimate.keys),
            [
                "food_name", "calories", "protein_grams", "carbohydrate_grams", "fat_grams",
                "confidence", "warnings", "assumptions",
            ]
        )
    }

    func testEverySourceKindUsesPublicWireValue() throws {
        let cases: [(FoodAnalysisSourceKind, String)] = [
            (.text, "text"), (.image, "image"), (.textAndImage, "text_and_image"),
        ]

        for (sourceKind, expected) in cases {
            let data = try JSONEncoder().encode(makeRefinementRequest(sourceKind: sourceKind))
            let json = try XCTUnwrap(JSONSerialization.jsonObject(with: data) as? [String: Any])
            let refinement = try XCTUnwrap(json["refinement"] as? [String: Any])
            XCTAssertEqual(refinement["source_kind"] as? String, expected)
        }
    }

    private func makeRefinementRequest(
        sourceKind: FoodAnalysisSourceKind
    ) -> FoodAnalysisRefinementRequestDTO {
        FoodAnalysisRefinementRequestDTO(
            foodDescription: sourceKind == .image ? nil : "Eine Schüssel Reis",
            refinement: FoodAnalysisRefinementDTO(
                correctionText: "Nur die Hälfte gegessen",
                currentEstimate: FoodAnalysisRefinementCurrentEstimateDTO(
                    foodName: "Reisschüssel",
                    calories: 620,
                    proteinGrams: 24,
                    carbohydrateGrams: 86,
                    fatGrams: 18,
                    confidence: 0.72,
                    warnings: ["Portion unsicher"],
                    assumptions: ["Reis gekocht"]
                ),
                sourceKind: sourceKind,
                iteration: 2
            )
        )
    }

    func testResponseDecodingFailsForMissingRequiredField() {
        let json = #"{"estimate": {"food_name": "Apfel"}}"#.data(using: .utf8)!

        XCTAssertThrowsError(try JSONDecoder().decode(FoodAnalysisResponseDTO.self, from: json))
    }

    func testResponseDecodingFailsForMissingEstimate() {
        let json = #"{}"#.data(using: .utf8)!

        XCTAssertThrowsError(try JSONDecoder().decode(FoodAnalysisResponseDTO.self, from: json))
    }
}
