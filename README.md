# Calendar

**Python version:** Open [`python/dist/Calendar.app`](python/dist/Calendar.app), or double-click [`python/run.command`](python/run.command). It uses native macOS controls and SQLite, and includes its Python runtime. See the [Python README](python/README.md) for building, usage, and tests.

The original Swift/Xcode version remains below.

A small, offline macOS 14+ app built with SwiftUI and SwiftData. One window, a 20-minute timer, and a calendar of what you did.

## Open and run

1. Open `Twenty.xcodeproj` in Xcode 15 or later.
2. Select the **Twenty** scheme and **My Mac**, then press **⌘R**.
3. Start a session and allow notifications when macOS asks.

The project uses local ad-hoc signing (“Sign to Run Locally”); no development team or backend is required. The app is sandboxed and has no network entitlement or CloudKit integration.

## Behavior

- **Start** immediately saves an unfinished session. The displayed countdown is calculated from `startDate + 1200 - Date()`; the timer only refreshes the view.
- **Cancel** deletes the unfinished session and cancels its notification.
- At the deadline, **What did you do?** opens with a multiline note field. **Save** completes the session. Blank notes are allowed.
- Quitting, closing the window, or sleeping does not reset the deadline. Reopening after the deadline restores the note prompt. An unsaved note draft is not retained across quitting.
- A local notification is scheduled with macOS when a session starts, so delivery does not depend on the app remaining open. Delivery is subject to notification permission, Focus, and system sleep. If permission is denied, the app shows an explanation and the timer still works.
- The calendar groups completed sessions by their start date in the current local time zone. Select a day, then a session to edit its note or delete it. Deletion asks for confirmation.
- SwiftData stores data in the sandbox’s Application Support directory. An unfinished session has `completed = false` and `endDate = nil`; saving its note sets `endDate` to the original 20-minute deadline, even if saved later.

## Validation

In the creation environment, all Swift files passed syntax parsing, the notification code passed type checking, the project and entitlements passed plist validation, and all nine timer checks passed. A full build and UI/notification runtime checks require Xcode: the installed Command Line Tools do not include the SwiftData macro plugin.

Run the independent timer checks with the macOS Swift toolchain:

```sh
swiftc Twenty/SessionTiming.swift Tests/SessionTimingTests.swift -o /tmp/twenty-timing-tests
/tmp/twenty-timing-tests
```

With Xcode installed, build with:

```sh
xcodebuild -project Twenty.xcodeproj -scheme Twenty -configuration Debug -destination 'platform=macOS' build
```

Manual checks: start/cancel; quit and reopen during a session; reopen after its deadline; finish while another app is focused; save/edit/delete notes; navigate months; switch macOS appearance; sleep and wake during a session. The session duration stays 20 minutes in all builds.

Implementation references: Apple’s [SwiftData ModelContainer](https://developer.apple.com/documentation/swiftdata/modelcontainer) and [local notification time triggers](https://developer.apple.com/documentation/usernotifications/untimeintervalnotificationtrigger).
