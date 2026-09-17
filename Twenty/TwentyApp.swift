import SwiftUI
import SwiftData

@main
@MainActor
struct TwentyApp: App {
    private let storage: Result<ModelContainer, Error>

    init() {
        _ = Notifications.shared
        storage = Result {
            try ModelContainer(
                for: Session.self,
                configurations: ModelConfiguration(cloudKitDatabase: .none)
            )
        }
    }

    var body: some Scene {
        Window("Twenty", id: "twenty") {
            switch storage {
            case .success(let container):
                ContentView()
                    .modelContainer(container)
            case .failure(let error):
                ContentUnavailableView {
                    Label("Couldn’t open your sessions", systemImage: "externaldrive.badge.exclamationmark")
                } description: {
                    Text("Your data has not been reset. Quit and reopen Twenty to try again.\n\n\(error.localizedDescription)")
                }
                .padding(32)
            }
        }
        .defaultSize(width: 820, height: 700)
        .windowResizability(.contentMinSize)
        .commands {
            CommandGroup(replacing: .newItem) { }
        }
    }
}
