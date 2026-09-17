import SwiftUI
import SwiftData

struct NoteEditor: View {
    @Environment(\.modelContext) private var context
    @Environment(\.dismiss) private var dismiss
    let session: Session
    @State private var note: String
    @State private var errorMessage: String?
    @State private var confirmingDelete = false
    @FocusState private var focused: Bool

    init(session: Session) {
        self.session = session
        _note = State(initialValue: session.note)
    }

    var body: some View {
        VStack(alignment: .leading, spacing: 16) {
            Text(session.completed ? "Edit session" : "What did you do?")
                .font(.title2.weight(.semibold))
            Text(session.startDate.formatted(date: .abbreviated, time: .shortened) + " · 20 minutes")
                .font(.subheadline).foregroundStyle(.secondary)
            TextEditor(text: $note)
                .font(.body)
                .padding(8)
                .background(.background, in: RoundedRectangle(cornerRadius: 8))
                .overlay(RoundedRectangle(cornerRadius: 8).stroke(.quaternary))
                .frame(height: 180)
                .focused($focused)
                .accessibilityLabel("Session note")
            if let errorMessage {
                Text(errorMessage).font(.callout).foregroundStyle(.red)
            }
            HStack {
                if session.completed {
                    Button("Delete…", role: .destructive) { confirmingDelete = true }
                }
                Spacer()
                if session.completed {
                    Button("Cancel") { dismiss() }.keyboardShortcut(.cancelAction)
                }
                Button("Save", action: save)
                    .keyboardShortcut(.defaultAction)
                    .buttonStyle(.borderedProminent)
            }
        }
        .padding(24)
        .frame(width: 460)
        .interactiveDismissDisabled(!session.completed)
        .onAppear { focused = true }
        .confirmationDialog("Delete this session?", isPresented: $confirmingDelete, titleVisibility: .visible) {
            Button("Delete Session", role: .destructive, action: delete)
            Button("Cancel", role: .cancel) { }
        } message: {
            Text("The session and its note will be permanently removed.")
        }
    }

    private func save() {
        session.note = note
        session.endDate = session.deadline
        session.completed = true
        do {
            try context.save()
            Notifications.shared.remove(id: session.id)
            dismiss()
        } catch {
            context.rollback()
            errorMessage = "Couldn’t save your note: \(error.localizedDescription)"
        }
    }

    private func delete() {
        let id = session.id
        context.delete(session)
        do {
            try context.save()
            Notifications.shared.remove(id: id)
            dismiss()
        } catch {
            context.rollback()
            errorMessage = "Couldn’t delete this session: \(error.localizedDescription)"
        }
    }
}
