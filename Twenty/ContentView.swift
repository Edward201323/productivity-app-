import SwiftUI
import SwiftData
import Combine

struct ContentView: View {
    @Environment(\.modelContext) private var context
    @Environment(\.scenePhase) private var scenePhase
    @Query(sort: \Session.startDate, order: .reverse) private var sessions: [Session]
    @State private var now = Date()
    @State private var editing: Session?
    @State private var selectedDate = Date()
    @State private var errorMessage: String?
    @State private var notificationMessage: String?
    private let ticker = Timer.publish(every: 0.5, on: .main, in: .common).autoconnect()

    private var active: Session? { sessions.last(where: { !$0.completed }) }
    private var history: [Session] { sessions.filter(\.completed) }

    var body: some View {
        VStack(spacing: 0) {
            timerPanel.padding(28)
            Divider()
            CalendarView(sessions: history, selectedDate: $selectedDate) { editing = $0 }
                .padding(24)
        }
        .frame(minWidth: 720, minHeight: 640)
        .background(.background)
        .onReceive(ticker) { refresh(at: $0) }
        .onChange(of: scenePhase) { _, phase in
            if phase == .active { refresh(at: .now) }
        }
        .task(id: active?.id) {
            refresh(at: .now)
            guard let session = active, session.deadline > Date() else { return }
            do {
                let allowed = try await Notifications.shared.schedule(id: session.id, deadline: session.deadline)
                notificationMessage = allowed ? nil : "Notifications are off. Allow Twenty in System Settings → Notifications for completion alerts."
            } catch {
                notificationMessage = "Couldn’t schedule the completion alert: \(error.localizedDescription)"
            }
        }
        .sheet(item: $editing, onDismiss: { refresh(at: .now) }) { session in
            NoteEditor(session: session)
        }
        .alert("Couldn’t save the change", isPresented: Binding(
            get: { errorMessage != nil },
            set: { if !$0 { errorMessage = nil } }
        )) {
            Button("OK", role: .cancel) { errorMessage = nil }
        } message: {
            Text(errorMessage ?? "")
        }
    }

    private var timerPanel: some View {
        VStack(spacing: 12) {
            Text("Twenty").font(.largeTitle.weight(.semibold))
            if let active {
                let remaining = SessionTiming.remaining(from: active.startDate, at: now)
                Text(SessionTiming.display(remaining))
                    .font(.system(size: 64, weight: .light, design: .rounded).monospacedDigit())
                    .accessibilityLabel("Time remaining")
                    .accessibilityValue(SessionTiming.display(remaining))
                if remaining > 0 {
                    Button("Cancel", role: .cancel) { cancel(active) }
                        .controlSize(.large)
                } else {
                    Button("What did you do?") { editing = active }
                        .buttonStyle(.borderedProminent)
                        .controlSize(.large)
                }
            } else {
                Text("One session. Twenty minutes.").foregroundStyle(.secondary)
                Button(action: start) {
                    Text("Start").font(.title2.weight(.semibold))
                        .frame(width: 180, height: 44)
                }
                .buttonStyle(.borderedProminent)
                .controlSize(.large)
                .padding(.top, 8)
            }
            if let notificationMessage {
                Text(notificationMessage).font(.caption).foregroundStyle(.secondary)
                    .multilineTextAlignment(.center).frame(maxWidth: 560)
            }
        }
        .frame(maxWidth: .infinity, minHeight: 194)
    }

    private func refresh(at date: Date) {
        now = date
        if let active, active.deadline <= date, editing == nil {
            selectedDate = active.startDate
            editing = active
        }
    }

    private func start() {
        guard active == nil else { return }
        let session = Session()
        context.insert(session)
        do {
            try context.save()
            now = .now
            notificationMessage = nil
        } catch {
            context.rollback()
            errorMessage = error.localizedDescription
        }
    }

    private func cancel(_ session: Session) {
        let id = session.id
        context.delete(session)
        do {
            try context.save()
            Notifications.shared.remove(id: id)
        } catch {
            context.rollback()
            errorMessage = error.localizedDescription
        }
    }
}
