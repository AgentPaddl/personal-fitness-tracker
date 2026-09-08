import Foundation
import SwiftData

@Model
final class Exercise {
    var id: UUID
    var name: String
    var createdAt: Date
    var isArchived: Bool
    var nextWeightIncreaseMarkedAt: Date?

    init(
        id: UUID = UUID(),
        name: String,
        createdAt: Date = Date(),
        isArchived: Bool = false,
        nextWeightIncreaseMarkedAt: Date? = nil
    ) {
        self.id = id
        self.name = name
        self.createdAt = createdAt
        self.isArchived = isArchived
        self.nextWeightIncreaseMarkedAt = nextWeightIncreaseMarkedAt
    }
}
