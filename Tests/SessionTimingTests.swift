import Foundation

@main
struct SessionTimingTests {
    static func main() {
        let start = Date(timeIntervalSince1970: 1_700_000_000)
        precondition(SessionTiming.remaining(from: start, at: start) == 1_200)
        precondition(SessionTiming.remaining(from: start, at: start.addingTimeInterval(735)) == 465)
        precondition(SessionTiming.remaining(from: start, at: start.addingTimeInterval(1_200)) == 0)
        precondition(SessionTiming.remaining(from: start, at: start.addingTimeInterval(8_000)) == 0)
        precondition(SessionTiming.deadline(for: start) == start.addingTimeInterval(1_200))
        precondition(SessionTiming.display(1_200) == "20:00")
        precondition(SessionTiming.display(59.2) == "01:00")
        precondition(SessionTiming.display(0) == "00:00")
        // Reconstruct the stored date after a simulated relaunch; no ticks are replayed.
        let restored = Date(timeIntervalSince1970: start.timeIntervalSince1970)
        precondition(SessionTiming.remaining(from: restored, at: start.addingTimeInterval(900)) == 300)
        print("SessionTiming: 9 checks passed")
    }
}
