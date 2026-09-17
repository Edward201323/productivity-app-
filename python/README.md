# lock in no gooning — Python

A native macOS app written in Python, with AppKit controls through PyObjC and a local SQLite database. Supports macOS 14+, with no backend, account, or network requests while running.

## Run

Double-click **`dist/lock in no gooning.app`**, or run:

```sh
./run.command
```

The included app is built for Apple Silicon and includes Python and its dependencies. Xcode and a separate Python installation are not required to run it. You can copy `lock in no gooning.app` to Applications.

If the app bundle is missing, `run.command` builds it first. Rebuilding requires an existing Python 3 installation and an internet connection to download the build tools. The script downloads a portable Python 3.13 runtime into this directory to avoid inheriting a newer macOS requirement from Homebrew Python. All build environments stay inside the project.

```sh
./build.command
```

Build on an Intel Mac to produce an Intel app. The bundle uses local ad-hoc signing for personal use.

## Use

- Above **Start**, the app shows the current local clock time, including seconds (for example, **9:45:08 PM**), and keeps it updated. While a session is running, this becomes the countdown.
- **Start** begins and immediately persists a 20-minute session. **End Session** stops it early and opens the note sheet. **Save** logs the actual time spent; **Discard…** removes the session after confirmation. Ending early cancels the scheduled notification.
- The countdown is always `startDate + 1200 - time.time()`. The UI timer only refreshes the display; sleep and missed ticks do not lengthen a session.
- When the 20 minutes are up, lock in no gooning sounds an alarm while it is running — the system Glass sound, three times. It does not depend on notification permission, so it is still audible when notifications are denied or held by Focus. Ending a session early does not sound it, and neither does reopening the app long after a session expired.
- Allow notifications when starting the first session. macOS schedules the alert independently of the running app. Focus, notification permissions, and sleep can affect when the system displays it.
- At completion, a sheet asks **What did you do?** Enter a multiline note and choose **Save**. Blank notes are allowed.
- Quitting during a session preserves its start time. Reopening after the deadline brings back the completion sheet. Ending early also saves the stop time immediately, so reopening brings back the note sheet with the same duration. A note draft is only persisted when saved.
- Use the month grid to select a day. A dot marks days with saved sessions or goals. In the **Sessions** tab, click a session to edit its note or delete it, with confirmation.
- Switch to **Daily Goals** and click **Add Goal** to write your own goal for the selected date. Save it, check it off when finished, or click its text to edit or delete it. You can plan goals for any calendar date; goals do not repeat or move to another day automatically. Saved goals and checkbox changes persist immediately. Unsaved goal drafts are only kept until you quit or cancel editing.
- Closing the main window keeps the app running. Use its Dock icon or **Window → Show lock in no gooning** to reopen it. **⌘Q** quits.

Dates are grouped by session start time in the Mac’s current local time zone. The calendar starts on Sunday. Native controls and semantic system colors follow light and dark appearance. The palette follows macOS Calendar and uses a single accent: red marks today, logged entries, and the running clock, while the selected day takes a neutral fill, so the only saturated color carries meaning. The clock itself is primary text — white in dark appearance. Session and goal rows sit on a recessed card rather than a lit bezel, and a completed goal is marked with a red symbol instead of a system-accent checkbox.

## Data

The database is stored at:

```text
~/Library/Application Support/Twenty Python/sessions.sqlite3
```

lock in no gooning retains the original “Twenty Python” data folder and app identifier so renaming it preserves existing sessions, goals, and notification identity.

The model contains `id`, `startDate`, `endDate`, `note`, and `completed`. Dates are absolute Unix timestamps. Running sessions have no `endDate`; ending early persists the actual stop time, while a full session records its original 20-minute deadline. The session remains unfinished until its note is saved. lock in no gooning totals use actual durations. A unique index permits only one unfinished session, and a process lock prevents two copies of lock in no gooning from editing the database simultaneously.

Sessions are stored only in this database. The data folder is created with `700` permissions and the database, WAL, and shared-memory files with `600`, so only your account can read your notes and goals. Nothing is sent anywhere, and the repository's `.gitignore` refuses `*.sqlite3`, `*.db`, `*.log`, and lock files.

Daily goals use a separate `goals` table in the same database, with a stable calendar date, text, completion state, and creation time. Existing session databases are upgraded automatically without changing their saved sessions.

## Validation

```sh
.app-venv/bin/python -m unittest test_core -v
.app-venv/bin/python test_ui.py
```

The twenty core tests cover session timing and persistence, calendar boundaries, early logging, goal storage, per-date isolation, editing, completion, deletion, blank-input validation, and upgrading existing databases. The native UI smoke check covers sessions and goals, switching tabs and dates, checkboxes, editing and deletion, appearance changes, and timer completion while a goal editor is open. It uses temporary data and never schedules notifications or touches your sessions.

The app bundle has also been built and its code signature and bundled Mach-O deployment targets checked. Runtime testing was on macOS 26; a physical macOS 14 run and delivery of a real 20-minute notification have not been tested.

Implementation references: [PyObjC](https://pyobjc.readthedocs.io/en/latest/), [Apple local notifications](https://developer.apple.com/documentation/usernotifications/unusernotificationcenter), [PyInstaller packaging](https://pyinstaller.org/en/stable/usage.html), and [uv managed Python](https://docs.astral.sh/uv/concepts/python-versions/).
