import Foundation
import SwiftData

@Model
final class Session {
    @Attribute(.unique) var id: UUID
    var startDate: Date
    var endDate: Date?
    var note: String
    var completed: Bool

    init(startDate: Date = .now) {
        id = UUID()
        self.startDate = startDate
        endDate = nil
        note = ""
        completed = false
    }

    var deadline: Date { SessionTiming.deadline(for: startDate) }
}
