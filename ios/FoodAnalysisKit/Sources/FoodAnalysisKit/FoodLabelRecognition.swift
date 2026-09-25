import Foundation

public struct FoodLabelText: Codable, Equatable, Sendable {
    public let text: String
    public let x: Double
    public let y: Double
    public let width: Double
    public let height: Double
    public let numberIsAmbiguous: Bool?
    public let lineID: Int?
    public let lineSlope: Double?
    public let alternatives: [String]?

    public init(text: String, x: Double, y: Double, width: Double, height: Double, numberIsAmbiguous: Bool? = nil,
                lineID: Int? = nil, lineSlope: Double? = nil, alternatives: [String]? = nil) {
        self.text = text
        self.x = x
        self.y = y
        self.width = width
        self.height = height
        self.numberIsAmbiguous = numberIsAmbiguous
        self.lineID = lineID
        self.lineSlope = lineSlope
        self.alternatives = alternatives
    }

    var centerX: Double { x + width / 2 }
    var centerY: Double { y + height / 2 }
    public func clippedToImageBounds() -> FoodLabelText {
        guard [x, y, width, height, x + width, y + height].allSatisfy(\.isFinite),
              width > 0, height > 0 else { return self }
        let left = max(0, x)
        let top = max(0, y)
        let right = min(1, x + width)
        let bottom = min(1, y + height)
        guard right > left, bottom > top else { return self }
        guard left != x || top != y || right != x + width || bottom != y + height else { return self }
        return FoodLabelText(text: text, x: left, y: top, width: right - left, height: bottom - top,
                             numberIsAmbiguous: true, lineID: lineID, lineSlope: lineSlope, alternatives: alternatives)
    }

    var isValid: Bool {
        [x, y, width, height].allSatisfy(\.isFinite) && x >= 0 && y >= 0
            && width > 0 && height > 0 && x + width <= 1.001 && y + height <= 1.001
            && !text.isEmpty && text.count <= 200
            && (lineID.map { $0 >= 0 && $0 < 2048 } ?? true)
            && (lineSlope?.isFinite ?? true)
            && (alternatives.map { $0.count <= 8 && $0.allSatisfy { $0.count <= 200 } } ?? true)
    }
}

public struct FoodLabelColumn: Equatable, Identifiable {
    public let id: Int
    public let heading: String
    public let quantity: Decimal?
    public let unit: FoodProductUnit?
    public let calories: Decimal?
    public let protein: Decimal?
    public let carbs: Decimal?
    public let fat: Decimal?

    public var hasValues: Bool { [calories, protein, carbs, fat].contains { $0 != nil } }
}

public struct FoodLabelAnalysis {
    public let columns: [FoodLabelColumn]
    public let issues: [FoodLabelIssue]
}

public struct FoodLabelIssue: Equatable {
    public enum Reason: String {
        case noText, invalidInput, noNutrientLabels, missingOrConflictingHeader, tooManyColumns
        case missingRow, repeatedRows, missingValueOrUnit, ambiguousValues, outsideColumn, outOfRange
        case ambiguousOCRNumber, nonExactValue
    }
    public let columnID: Int?
    public let field: String?
    public let reason: Reason
}

public enum FoodLabelRecognition {
    public static let supportedLabels = ["Energie", "Energy", "Brennwert", "Kalorien", "Calories",
        "Fett", "Fat", "Total fat", "Eiweiss", "Eiweiß", "Protein", "Kohlenhydrate", "Carbohydrate", "Carbohydrates",
        "Zucker", "Sugar", "Sugars", "Saturates", "Saturated fat", "Gesättigte Fettsäuren",
        "Ballaststoffe", "Fibre", "Fiber", "Salz", "Salt", "Sodium"]

    public static func isSupportedLabel(_ text: String) -> Bool {
        supportedLabels.contains { normalized($0) == normalized(text) }
    }

    private enum Nutrient: String, CaseIterable { case calories, protein, carbs, fat }
    private struct Measurement {
        let value: Decimal
        let unit: String
        let centerX: Double
        let numberIsAmbiguous: Bool
        let nonExact: Bool
    }
    private struct Header {
        var centerX: Double
        var quantity: Decimal?
        var unit: FoodProductUnit?
        var portion: Bool
        var numberIsAmbiguous = false
    }

    public static func columns(from input: [FoodLabelText]) -> [FoodLabelColumn] {
        analyze(input).columns
    }

    public static func hasConflictingNumbers(in candidates: [String]) -> Bool {
        let expression = try! NSRegularExpression(pattern: #"[<>≤≥~≈−+-]?\s*[0-9]+(?:[,.][0-9]+)?"#)
        let readings = candidates.map { candidate -> [String] in
            let text = normalized(candidate)
            return expression.matches(in: text, range: NSRange(text.startIndex..., in: text)).compactMap { match in
                guard let range = Range(match.range, in: text) else { return nil }
                return text[range].filter { !$0.isWhitespace }.replacingOccurrences(of: ",", with: ".")
            }
        }
        guard let first = readings.first else { return false }
        return readings.dropFirst().contains { $0 != first }
    }

    public static func analyze(_ input: [FoodLabelText]) -> FoodLabelAnalysis {
        func rejected(_ reason: FoodLabelIssue.Reason) -> FoodLabelAnalysis {
            FoodLabelAnalysis(columns: [], issues: [.init(columnID: nil, field: nil, reason: reason)])
        }
        guard !input.isEmpty else { return rejected(.noText) }
        guard input.count <= 2048, input.allSatisfy(\.isValid) else { return rejected(.invalidInput) }
        let input = input.map { token -> FoodLabelText in
            guard !isSupportedLabel(token.text), !contains(#"[0-9]"#, in: token.text) else { return token }
            let labels = Set((token.alternatives ?? []).filter(isSupportedLabel).map(normalized))
            guard labels.count == 1, let label = labels.first else { return token }
            return FoodLabelText(text: label, x: token.x, y: token.y, width: token.width, height: token.height,
                                 numberIsAmbiguous: token.numberIsAmbiguous, lineID: token.lineID, lineSlope: token.lineSlope)
        }
        if let panels = verticalPanelAnalysis(input) { return panels }
        let rows = makeRows(input)
        guard let firstNutrient = rows.firstIndex(where: { nutrient(in: $0) != nil }) else { return rejected(.noNutrientLabels) }
        let headerRows = Array(rows[..<firstNutrient]).filter {
            (rows[firstNutrient].first?.y ?? 0) - ($0.first?.y ?? 0) < 0.22
        }
        guard var headers = findHeaders(headerRows) else { return rejected(.missingOrConflictingHeader) }
        if headers.isEmpty {
            let headerText = normalized(headerRows.flatMap { $0 }.map(\.text).joined(separator: " "))
            guard !contains(#"[0-9]"#, in: headerText) else { return rejected(.missingOrConflictingHeader) }
            let candidateRows = rows.compactMap { row -> [Measurement]? in
                guard let kind = nutrient(in: row) else { return nil }
                return measurements(in: row, implicitUnit: implicitUnit(in: row, kind: kind))
                    .filter { $0.unit == (kind == .calories ? "kcal" : "g") }
            }
            guard candidateRows.allSatisfy({ $0.count <= 1 }) else { return rejected(.missingOrConflictingHeader) }
            let candidates = candidateRows.compactMap(\.first)
            if let first = candidates.first, candidates.allSatisfy({ abs($0.centerX - first.centerX) < 0.045 }) {
                headers = [Header(centerX: first.centerX, quantity: nil, unit: nil, portion: false)]
            }
        }
        guard !headers.isEmpty else { return rejected(.missingOrConflictingHeader) }
        guard headers.count <= 6 else { return rejected(.tooManyColumns) }
        let pairedRows = pairedVisionRows(input, rows: rows, columnCount: headers.count)
        let pairedIDs = Set(pairedRows.flatMap { $0 }.compactMap(\.lineID))
        let nutrientRows = rows.map { row -> [FoodLabelText] in
            guard let kind = nutrient(in: row),
                  let anchor = row.first(where: { nutrient(in: [$0]) == kind }),
                  kind != .calories || contains(#"\b(brennwert|energie|energy|kalorien|calories)\b"#, in: normalized(anchor.text)) else { return row }
            let existing = measurements(in: row, implicitUnit: implicitUnit(in: row, kind: kind))
                .filter { $0.unit == (kind == .calories ? "kcal" : "g") }
            if existing.count >= headers.count { return row }
            let boundaries = input.filter { token in
                if isExcludedLabel(token.text) { return true }
                return nutrient(in: [token]).map { $0 != kind } ?? false
            }
            let nearby = input.filter { token in
                token.x >= anchor.x && abs(token.centerY - anchor.centerY) <= max(token.height, anchor.height)
                    && boundaries.allSatisfy { boundary in
                        abs(token.centerY - anchor.centerY) + min(token.height, boundary.height) * 0.1
                            < abs(token.centerY - boundary.centerY)
                    }
            }.sorted { $0.x < $1.x }
            return nutrient(in: nearby) == kind ? nearby : row
        }
        var issues: [FoodLabelIssue] = []
        let columns = headers.enumerated().map { index, header in
            if header.numberIsAmbiguous || header.quantity == nil || header.unit == nil {
                issues.append(.init(columnID: index, field: "basis",
                                    reason: header.numberIsAmbiguous ? .ambiguousOCRNumber : .missingValueOrUnit))
            }
            var values: [Nutrient: Decimal] = [:]
            for kind in Nutrient.allCases {
                func reject(_ reason: FoodLabelIssue.Reason) {
                    issues.append(.init(columnID: index, field: kind.rawValue, reason: reason))
                }
                var matchingRows = nutrientRows.enumerated().compactMap { rowIndex, row -> [FoodLabelText]? in
                    guard !row.contains(where: { $0.lineID.map { pairedIDs.contains($0) } == true }) else { return nil }
                    guard nutrient(in: row) == kind else { return nil }
                    if kind == .calories {
                        let label = normalized(row.prefix { !contains(#"[0-9]"#, in: $0.text) }.map(\.text).joined(separator: " "))
                        let explicit = contains(#"\b(brennwert|energie|energy|kalorien|calories|kcal)\b"#, in: label)
                        let previous = rowIndex > 0 ? rows[rowIndex - 1] : []
                        let previousText = normalized(previous.map(\.text).joined(separator: " "))
                        let continuation = contains(#"\b(brennwert|energie|energy)\b"#, in: previousText)
                            && contains(#"(?:^|[^a-z])kj\b"#, in: previousText)
                            && !contains(#"kcal"#, in: previousText)
                            && (row.first?.centerY ?? 1) - (previous.first?.centerY ?? 0)
                                <= 3 * min(row.first?.height ?? 0, previous.first?.height ?? 0)
                        guard explicit || continuation,
                              measurements(in: row, implicitUnit: implicitUnit(in: row, kind: kind))
                                .contains(where: { $0.unit == "kcal" }) else { return nil }
                    }
                    return row
                }
                matchingRows += pairedRows.filter { nutrient(in: $0) == kind }
                guard matchingRows.count == 1, let row = matchingRows.first else {
                    reject(matchingRows.isEmpty ? .missingRow : .repeatedRows)
                    continue
                }
                let readings = measurements(in: row, implicitUnit: implicitUnit(in: row, kind: kind))
                    .filter { $0.unit == (kind == .calories ? "kcal" : "g") }
                guard !readings.isEmpty else { reject(.missingValueOrUnit); continue }
                guard headers.count != 1 || readings.count <= 1 else { reject(.ambiguousValues); continue }
                let assigned = readings.filter { reading in
                    let distances = headers.map { abs($0.centerX - reading.centerX) }
                    guard let nearest = distances.min(), nearest <= 0.15,
                          distances[index] == nearest,
                          distances.filter({ abs($0 - nearest) < 0.025 }).count == 1 else { return false }
                    return true
                }
                if assigned.contains(where: \.nonExact) {
                    reject(.nonExactValue)
                } else if assigned.contains(where: \.numberIsAmbiguous) {
                    reject(.ambiguousOCRNumber)
                } else if assigned.count == 1, let value = assigned.first?.value,
                   value <= (kind == .calories ? 10000 : 1000) {
                    values[kind] = value
                } else {
                    reject(assigned.isEmpty ? .outsideColumn : assigned.count > 1 ? .ambiguousValues : .outOfRange)
                }
            }
            let quantity = header.numberIsAmbiguous ? nil : header.quantity
            let basis = quantity.map { NSDecimalNumber(decimal: $0).stringValue }
            let heading: String
            if let basis, let unit = header.unit {
                heading = header.portion ? "Portion (\(basis) \(unit.rawValue))" : "\(basis) \(unit.rawValue)"
            } else {
                heading = header.portion ? "Portion ohne eindeutige Bezugsmenge" : "Bezugsmenge nicht eindeutig"
            }
            return FoodLabelColumn(id: index, heading: heading, quantity: quantity, unit: header.unit,
                calories: values[.calories], protein: values[.protein], carbs: values[.carbs], fat: values[.fat])
        }
            return FoodLabelAnalysis(columns: columns, issues: issues)
    }

    public static func selectedColumn(from columns: [FoodLabelColumn], id: Int?) -> FoodLabelColumn? {
        if columns.count == 1, id == nil { return columns.first }
        guard let id else { return nil }
        return columns.first { $0.id == id }
    }

    private static func normalized(_ text: String) -> String {
        text.lowercased().folding(options: [.diacriticInsensitive, .widthInsensitive], locale: Locale(identifier: "de_DE"))
            .replacingOccurrences(of: "ß", with: "ss")
            .trimmingCharacters(in: .whitespacesAndNewlines)
    }

    private static func makeRows(_ input: [FoodLabelText]) -> [[FoodLabelText]] {
        var rows: [[FoodLabelText]] = []
        for token in input.sorted(by: { $0.centerY < $1.centerY }) {
            if let index = rows.indices.last, let anchor = rows[index].first,
               abs(anchor.centerY - token.centerY) <= min(anchor.height, token.height) * 0.45 {
                rows[index].append(token)
            } else {
                rows.append([token])
            }
        }
        return rows.map { $0.sorted { $0.x < $1.x } }
    }

    private static func verticalPanelAnalysis(_ input: [FoodLabelText]) -> FoodLabelAnalysis? {
        let lines = Dictionary(grouping: input.filter { $0.lineID != nil }, by: { $0.lineID! })
            .values.map { $0.sorted { $0.x < $1.x } }
        let references = lines.filter { contains(#"\b(serving|portion)\b"#, in: normalized($0.map(\.text).joined(separator: " "))) }
        guard references.count == 1, let reference = references.first, let origin = reference.first,
              let slope = origin.lineSlope, slope.isFinite else { return nil }
        func position(_ token: FoodLabelText) -> Double { token.centerY - slope * token.centerX }
        func textHeight(_ token: FoodLabelText) -> Double { max(0, token.height - abs(slope) * token.width) }
        let referenceY = position(origin)
        let labels = input.filter { token in
            guard isSupportedLabel(token.text), let lineID = token.lineID,
                  let line = lines.first(where: { $0.first?.lineID == lineID }),
                  !contains(#"\b(high|rich|source|reich|quelle)\b"#, in: normalized(line.map(\.text).joined(separator: " "))) else { return false }
            return position(token) > referenceY && position(token) - referenceY < 0.22 && textHeight(token) > 0
        }.sorted { position($0) < position($1) }
        guard let firstLabel = labels.first else { return nil }
        let band = labels.filter { abs(position($0) - position(firstLabel)) <= min(textHeight($0), textHeight(firstLabel)) * 0.45 }
            .sorted { $0.centerX < $1.centerX }
        guard band.count >= 2, band.contains(where: { nutrient(in: [$0]) != nil }),
              zip(band, band.dropFirst()).allSatisfy({ $0.centerX + 0.025 < $1.centerX }) else { return nil }
        let otherReferences = lines.filter { line in
            guard let first = line.first, first.lineID != origin.lineID else { return false }
            let quantities = measurements(in: line).filter { ["g", "ml"].contains($0.unit) }
            return !quantities.isEmpty
                && (contains(#"\b(per|pro|je|portion|serving)\b"#, in: normalized(line.map(\.text).joined(separator: " ")))
                    || position(first) < position(firstLabel) && quantities.contains { $0.value == 100 })
        }
        let quantities = measurements(in: reference).filter { ["g", "ml"].contains($0.unit) }
        guard otherReferences.isEmpty, quantities.count <= 1 else {
            return FoodLabelAnalysis(columns: [], issues: [.init(columnID: nil, field: "basis", reason: .missingOrConflictingHeader)])
        }
        let reading = quantities.first
        let validBasis = reading.map { !$0.numberIsAmbiguous && !$0.nonExact && $0.value > 0 && $0.value <= 1_000_000 } ?? false
        let quantity = validBasis ? reading?.value : nil
        let unit: FoodProductUnit? = validBasis ? (reading?.unit == "ml" ? .milliliters : .grams) : nil
        var issues: [FoodLabelIssue] = []
        if quantity == nil { issues.append(.init(columnID: 0, field: "basis", reason: .missingValueOrUnit)) }
        var values: [Nutrient: Decimal] = [:]
        for kind in Nutrient.allCases {
            func reject(_ reason: FoodLabelIssue.Reason) { issues.append(.init(columnID: 0, field: kind.rawValue, reason: reason)) }
            let anchors = band.filter { token in
                guard nutrient(in: [token]) == kind else { return false }
                return kind != .fat || !lines.contains { line in
                    line.first?.lineID == token.lineID
                        && contains(#"gesattigt|fettsaur|saturat"#, in: normalized(line.map(\.text).joined(separator: " ")))
                }
            }
            guard anchors.count == 1, let anchor = anchors.first else { reject(anchors.isEmpty ? .missingRow : .repeatedRows); continue }
            let cells = lines.filter { line in
                line.allSatisfy { token in
                    let distances = band.map { abs($0.centerX - token.centerX) }
                    let distance = abs(anchor.centerX - token.centerX)
                    let delta = position(token) - position(anchor)
                    return distance <= 0.15 && distances.min() == distance
                        && distances.filter({ abs($0 - distance) < 0.025 }).count == 1
                        && delta > textHeight(anchor) * 0.45
                        && delta <= 3 * max(textHeight(anchor), textHeight(token))
                }
            }
            let readings = cells.flatMap { measurements(in: $0, implicitUnit: implicitUnit(in: [anchor], kind: kind)) }
                .filter { $0.unit == (kind == .calories ? "kcal" : "g") }
            guard readings.count == 1, let value = readings.first else { reject(readings.isEmpty ? .missingValueOrUnit : .ambiguousValues); continue }
            if value.nonExact { reject(.nonExactValue) }
            else if value.numberIsAmbiguous || anchor.numberIsAmbiguous == true { reject(.ambiguousOCRNumber) }
            else if value.value > (kind == .calories ? 10000 : 1000) { reject(.outOfRange) }
            else { values[kind] = value.value }
        }
        let heading = quantity.flatMap { amount in unit.map { "Portion (\(NSDecimalNumber(decimal: amount).stringValue) \($0.rawValue))" } }
            ?? "Portion ohne eindeutige Bezugsmenge"
        return FoodLabelAnalysis(columns: [FoodLabelColumn(id: 0, heading: heading, quantity: quantity, unit: unit,
            calories: values[.calories], protein: values[.protein], carbs: values[.carbs], fat: values[.fat])], issues: issues)
    }

    private static func pairedVisionRows(_ input: [FoodLabelText], rows: [[FoodLabelText]], columnCount: Int) -> [[FoodLabelText]] {
        let groups = Dictionary(grouping: input.filter { $0.lineID != nil }, by: { $0.lineID! })
        return groups.keys.sorted().compactMap { lineID in
            let label = groups[lineID]!.sorted { $0.x < $1.x }
            guard let kind = nutrient(in: label), !label.contains(where: { contains(#"[0-9]"#, in: $0.text) }),
                  !rows.contains(where: { row in
                      row.contains(where: { $0.lineID == lineID }) && nutrient(in: row) == kind
                          && row.allSatisfy { token in
                              guard let slope = token.lineSlope, let first = row.first, let last = row.last else { return false }
                              return abs(slope) * (last.x + last.width - first.x) <= token.height * 0.45
                          }
                          && measurements(in: row, implicitUnit: implicitUnit(in: row, kind: kind))
                              .filter { $0.unit == (kind == .calories ? "kcal" : "g") }.count >= columnCount
                  }),
                  let next = groups[lineID + 1]?.sorted(by: { $0.x < $1.x }),
                  let anchor = label.first, let firstValue = next.first,
                  let labelRight = label.map({ $0.x + $0.width }).max(), firstValue.x >= labelRight,
                  firstValue.centerY >= anchor.centerY - min(anchor.height, firstValue.height) * 0.45,
                  abs(firstValue.centerY - anchor.centerY) <= max(anchor.height, firstValue.height),
                  nutrient(in: next) == nil || kind == .calories,
                  !isExcludedLabel(next.map(\.text).joined(separator: " ")) else { return nil }
            let unit = implicitUnit(in: label, kind: kind)
            let readings = measurements(in: next, implicitUnit: unit)
            guard readings.contains(where: { $0.unit == (kind == .calories ? "kcal" : "g") }) else { return nil }
            return label + next
        }
    }

    private static func contains(_ pattern: String, in text: String) -> Bool {
        text.range(of: pattern, options: .regularExpression) != nil
    }

    private static func isExcludedLabel(_ text: String) -> Bool {
        contains(#"gesattigt|fettsaur|zucker|ballaststoff|salz|saturate|sugars?|fib(re|er)|salt|sodium"#, in: normalized(text))
    }

    private static func nutrient(in row: [FoodLabelText]) -> Nutrient? {
        let text = normalized(row.map(\.text).joined(separator: " "))
        guard !isExcludedLabel(text), !contains(#"\b(high|rich|source|reich|quelle)\b"#, in: text) else { return nil }
        var kinds: [Nutrient] = []
        if contains(#"\b(eiweiss|protein)\b"#, in: text) { kinds.append(.protein) }
        if contains(#"\b(kohlenhydrate|carbohydrates?|carbs)\b"#, in: text) { kinds.append(.carbs) }
        if contains(#"\b(fett|fat)\b"#, in: text) { kinds.append(.fat) }
        if contains(#"\b(brennwert|energie|energy|kalorien|calories)\b"#, in: text) || kinds.isEmpty && contains(#"(?:^|[^a-z])kcal\b"#, in: text) {
            kinds.append(.calories)
        }
        return kinds.count == 1 ? kinds.first : nil
    }

    private static func implicitUnit(in row: [FoodLabelText], kind: Nutrient) -> String? {
        let label = normalized(row.prefix { !contains(#"[0-9]"#, in: $0.text) }.map(\.text).joined(separator: " "))
        if kind == .calories {
            return contains(#"\b(kcal|calories)\b"#, in: label) && !contains(#"\bkj\b"#, in: label) ? "kcal" : nil
        }
        return contains(#"\bg\b"#, in: label) ? "g" : nil
    }

    private static func measurements(in row: [FoodLabelText], implicitUnit: String? = nil) -> [Measurement] {
        var result: [Measurement] = []
        guard !row.contains(where: { contains(#"[~≈−]|^[+-]$"#, in: $0.text) }) else { return [] }
        let expression = try! NSRegularExpression(pattern: #"^[<>≤≥]?\s*([0-9]+(?:[,.][0-9]+)?)\s*(kcal|kj|ml|g|г)?$"#)
        for (index, token) in row.enumerated() {
            let text = normalized(token.text).trimmingCharacters(in: CharacterSet(charactersIn: "()/:"))
            guard let match = expression.firstMatch(in: text, range: NSRange(text.startIndex..., in: text)),
                  let numberRange = Range(match.range(at: 1), in: text) else { continue }
            let number = String(text[numberRange])
            guard !contains(#"^[1-9][0-9]*[.,][0-9]{3}$"#, in: number),
                  let value = FoodProductBasis.parseNumber(number) else { continue }
            let previous = index > 0 ? row[index - 1] : nil
                var nonExact = contains(#"[<>≤≥]"#, in: text)
            if let previous, token.x - previous.x - previous.width < 0.04,
                    contains(#"^[~≈−-]$|^[0-9]+$"#, in: previous.text) { continue }
                if let previous, token.x - previous.x - previous.width < 0.04,
                    contains(#"^[<>≤≥]$"#, in: previous.text) { nonExact = true }
            let next = index + 1 < row.count ? row[index + 1] : nil
            if let next, next.x - token.x - token.width < 0.04,
               contains(#"^[0-9]+$|^%$"#, in: normalized(next.text)) { continue }
            var unit = Range(match.range(at: 2), in: text).flatMap { canonicalUnit(String(text[$0])) }
            var endX = token.x + token.width
            var numberIsAmbiguous = token.numberIsAmbiguous == true
            if unit == nil, let next, next.x - endX < 0.04 {
                let nextText = normalized(next.text).trimmingCharacters(in: CharacterSet(charactersIn: "()/:"))
                if let nextUnit = canonicalUnit(nextText) {
                    unit = nextUnit
                    endX = next.x + next.width
                    numberIsAmbiguous = numberIsAmbiguous || next.numberIsAmbiguous == true
                } else if contains(#"[a-z%]"#, in: nextText) {
                    continue
                }
            }
            if let unit = unit ?? implicitUnit {
                if implicitUnit != nil, row.prefix(while: { !contains(#"[0-9]"#, in: $0.text) })
                    .contains(where: { $0.numberIsAmbiguous == true }) { numberIsAmbiguous = true }
                result.append(Measurement(value: value, unit: unit, centerX: (token.x + endX) / 2,
                                          numberIsAmbiguous: numberIsAmbiguous, nonExact: nonExact))
            }
        }
        return result
    }

    private static func canonicalUnit(_ text: String) -> String? {
        let parts = text.split(separator: "/").map(String.init)
        if !parts.isEmpty, parts.allSatisfy({ $0 == "g" || $0 == "г" }) { return "g" }
        return ["ml", "kcal", "kj"].contains(text) ? text : nil
    }

    private static func findHeaders(_ rows: [[FoodLabelText]]) -> [Header]? {
        let portions = rows.flatMap { $0 }.filter { contains(#"\b(portion|serving)\b"#, in: normalized($0.text)) }
        var headers: [Header] = []
        for row in rows {
            let text = normalized(row.map(\.text).joined(separator: " "))
            guard !contains(#"netto|inhalt|zutaten"#, in: text) else { continue }
            for reading in measurements(in: row) where ["g", "ml"].contains(reading.unit) {
                let portion = portions.contains { abs($0.centerX - reading.centerX) < 0.13
                    && abs($0.centerY - (row.first?.centerY ?? 0)) < 0.08 }
                    guard !reading.nonExact, reading.value > 0, reading.value <= 1_000_000,
                        reading.value == 100 || portion || contains(#"\b(pro|je|per)\b"#, in: text) else { continue }
                let unit: FoodProductUnit = reading.unit == "g" ? .grams : .milliliters
                if let existing = headers.firstIndex(where: { abs($0.centerX - reading.centerX) < 0.045 }) {
                    if headers[existing].quantity != reading.value || headers[existing].unit != unit {
                        return nil
                    }
                    headers[existing].numberIsAmbiguous = headers[existing].numberIsAmbiguous || reading.numberIsAmbiguous
                } else {
                    headers.append(Header(centerX: reading.centerX, quantity: reading.value, unit: unit,
                                          portion: portion, numberIsAmbiguous: reading.numberIsAmbiguous))
                }
            }
        }
        for portion in portions where !headers.contains(where: { abs($0.centerX - portion.centerX) < 0.13 }) {
            headers.append(Header(centerX: portion.centerX, quantity: nil, unit: nil, portion: true))
        }
        return headers.sorted { $0.centerX < $1.centerX }
    }
}