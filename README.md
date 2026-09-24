# lock in no gooning

A small, offline macOS 14+ app: one window, a 20-minute timer, daily goals, and a calendar of what you did. Written in Python with native AppKit controls through PyObjC and a local SQLite database. No backend, account, or network requests.

## Run

Open [`python/dist/lock in no gooning.app`](python/dist/lock in no gooning.app), or double-click [`python/run.command`](python/run.command). The bundle includes its own Python runtime, so neither Xcode nor a separate Python installation is needed to run it. If the bundle is missing, `run.command` builds it first.

See the [Python README](python/README.md) for building, usage, data, and tests.

## Behavior

- Above **Start**, the app shows the current local clock time with seconds. While a session runs, this becomes the countdown.
- **Start** begins and immediately persists a 20-minute session. **End Session** stops it early and opens the note sheet.
- The countdown is always `startDate + 1200 - time.time()`. The UI timer only refreshes the display; sleep and missed ticks do not lengthen a session.
- At completion, a sheet asks **What did you do?** Blank notes are allowed.
- At the deadline the app sounds an alarm (the system Glass sound, three times) whenever it is running, independent of notifications.
- A local notification is scheduled with macOS when a session starts, so delivery does not depend on the app staying open. Focus, notification permission, and sleep can affect when it appears.
- The month grid marks days with saved sessions or goals. Select a day to edit or delete its sessions, or switch to **Daily Goals** to plan and check off goals for any date.
- Quitting during a session preserves its start time; reopening after the deadline brings back the completion sheet.

## Data

```text
~/Library/Application Support/Twenty Python/sessions.sqlite3
```

Sessions and daily goals live in the same database. Dates are absolute Unix timestamps, grouped by session start time in the Mac's current local time zone. A day runs 8am to 8am, so work done at 4am is filed under the previous date rather than starting a new one; change `DAY_START_HOUR` in `python/core.py` to move that boundary.

Your notes and goals stay private. They are written outside this repository, the folder and database are created owner-only (`700` / `600`), and nothing is ever uploaded — the app makes no network requests. `.gitignore` also blocks `*.sqlite3`, `*.db`, `*.log`, and lock files, so a database copied into the project cannot be committed by accident.
