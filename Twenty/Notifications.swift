import AppKit
import UserNotifications

final class NotificationDelegate: NSObject, UNUserNotificationCenterDelegate {
    func userNotificationCenter(
        _ center: UNUserNotificationCenter,
        willPresent notification: UNNotification,
        withCompletionHandler completionHandler: @escaping (UNNotificationPresentationOptions) -> Void
    ) {
        completionHandler([.banner, .sound])
    }

    func userNotificationCenter(
        _ center: UNUserNotificationCenter,
        didReceive response: UNNotificationResponse,
        withCompletionHandler completionHandler: @escaping () -> Void
    ) {
        DispatchQueue.main.async {
            NSApp.activate(ignoringOtherApps: true)
            NSApp.windows.first(where: { $0.canBecomeMain })?.makeKeyAndOrderFront(nil)
        }
        completionHandler()
    }
}

@MainActor
final class Notifications {
    static let shared = Notifications()
    private let delegate = NotificationDelegate()
    private let center = UNUserNotificationCenter.current()
    private var generation = UUID()
    private var scheduledID: UUID?

    private init() {
        center.delegate = delegate
    }

    func schedule(id: UUID, deadline: Date) async throws -> Bool {
        let token = UUID()
        generation = token
        scheduledID = id
        let allowed = try await center.requestAuthorization(options: [.alert, .sound])
        guard generation == token, !Task.isCancelled else { return true }
        guard allowed else { return false }
        let interval = deadline.timeIntervalSinceNow
        guard interval > 0 else { return true }
        let content = UNMutableNotificationContent()
        content.title = "Twenty minutes, well spent."
        content.body = "What did you do? Open Twenty to save your note."
        content.sound = .default
        let request = UNNotificationRequest(
            identifier: id.uuidString,
            content: content,
            trigger: UNTimeIntervalNotificationTrigger(timeInterval: max(1, interval), repeats: false)
        )
        try await center.add(request)
        if generation != token || Task.isCancelled {
            center.removePendingNotificationRequests(withIdentifiers: [id.uuidString])
        }
        return true
    }

    func remove(id: UUID) {
        if scheduledID == id { generation = UUID() }
        center.removePendingNotificationRequests(withIdentifiers: [id.uuidString])
        center.removeDeliveredNotifications(withIdentifiers: [id.uuidString])
    }
}
