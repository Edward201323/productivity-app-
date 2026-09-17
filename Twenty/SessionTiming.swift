import Foundation

enum SessionTiming {
    static let duration: TimeInterval = 1_200

    static func deadline(for startDate: Date) -> Date {
        startDate.addingTimeInterval(duration)
    }

    static func remaining(from startDate: Date, at now: Date) -> TimeInterval {
        max(0, deadline(for: startDate).timeIntervalSince(now))
    }

    static func display(_ remaining: TimeInterval) -> String {
        let seconds = Int(ceil(max(0, remaining)))
        return String(format: "%02d:%02d", seconds / 60, seconds % 60)
    }
}
