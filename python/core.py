"""Offline storage and wall-clock timing, independent of the macOS UI."""
from __future__ import annotations

import calendar
from dataclasses import dataclass
from datetime import date, datetime
import math
from pathlib import Path
import sqlite3
import time
import uuid

DURATION = 20 * 60


@dataclass(frozen=True)
class Goal:
    id: str
    day: str
    text: str
    completed: bool
    createdAt: float


@dataclass(frozen=True)
class Session:
    id: str
    startDate: float
    endDate: float | None
    note: str
    completed: bool

    @property
    def deadline(self) -> float:
        return self.startDate + DURATION

    def remaining(self, now: float | None = None) -> float:
        if self.endDate is not None:
            return 0
        return max(0, self.deadline - (time.time() if now is None else now))

    @property
    def duration(self) -> float:
        end = self.deadline if self.endDate is None else self.endDate
        return max(0, end - self.startDate)


def countdown(seconds: float) -> str:
    minutes, seconds = divmod(math.ceil(max(0, seconds)), 60)
    return f"{minutes:02d}:{seconds:02d}"


def duration_text(seconds: float) -> str:
    minutes, seconds = divmod(int(max(0, seconds)), 60)
    if minutes and seconds:
        return f"{minutes}m {seconds}s"
    return f"{minutes} minutes" if minutes else f"{seconds} seconds"


def month_cells(year: int, month: int) -> list[date | None]:
    # Sunday-first, matching a conventional US month calendar.
    weeks = calendar.Calendar(firstweekday=6).monthdayscalendar(year, month)
    return [date(year, month, day) if day else None for week in weeks for day in week]


def shifted_month(day: date, offset: int) -> date:
    year, month = divmod(day.year * 12 + day.month - 1 + offset, 12)
    return date(year, month + 1, 1)


class Store:
    def __init__(self, path: Path):
        path.parent.mkdir(parents=True, exist_ok=True)
        self.db = sqlite3.connect(path)
        self.db.row_factory = sqlite3.Row
        self.db.execute("PRAGMA journal_mode=WAL")
        self.db.execute("PRAGMA synchronous=FULL")
        with self.db:
            self.db.execute("""
                CREATE TABLE IF NOT EXISTS sessions (
                    id TEXT PRIMARY KEY,
                    startDate REAL NOT NULL,
                    endDate REAL,
                    note TEXT NOT NULL DEFAULT '',
                    completed INTEGER NOT NULL DEFAULT 0 CHECK(completed IN (0, 1))
                )
            """)
            self.db.execute("""
                CREATE UNIQUE INDEX IF NOT EXISTS one_active_session
                ON sessions(completed) WHERE completed = 0
            """)
            self.db.execute("""
                CREATE TABLE IF NOT EXISTS goals (
                    id TEXT PRIMARY KEY,
                    day TEXT NOT NULL,
                    text TEXT NOT NULL CHECK(length(trim(text)) > 0),
                    completed INTEGER NOT NULL DEFAULT 0 CHECK(completed IN (0, 1)),
                    createdAt REAL NOT NULL
                )
            """)
            self.db.execute("CREATE INDEX IF NOT EXISTS goals_by_day ON goals(day, createdAt)")

    def _sessions(self, sql: str, args: tuple = ()) -> list[Session]:
        return [Session(**dict(row)) for row in self.db.execute(sql, args)]

    def active(self) -> Session | None:
        rows = self._sessions("SELECT * FROM sessions WHERE completed = 0")
        return rows[0] if rows else None

    def start(self, now: float | None = None) -> Session:
        session = Session(str(uuid.uuid4()), time.time() if now is None else now, None, "", False)
        with self.db:
            self.db.execute("INSERT INTO sessions(id, startDate) VALUES (?, ?)",
                            (session.id, session.startDate))
        return session

    def stop(self, session: Session, now: float | None = None) -> Session:
        end = min(session.deadline, max(session.startDate, time.time() if now is None else now))
        with self.db:
            self.db.execute("""UPDATE sessions SET endDate = COALESCE(endDate, ?)
                               WHERE id = ? AND completed = 0""", (end, session.id))
        stopped = self.active()
        if stopped is None or stopped.id != session.id:
            raise ValueError("This session is no longer active.")
        return stopped

    def complete(self, session: Session, note: str, now: float | None = None) -> None:
        current = self.active()
        if current is None or current.id != session.id:
            raise ValueError("This session is no longer active.")
        session = current
        if session.remaining(now) > 0:
            raise ValueError("This session is still running.")
        with self.db:
            self.db.execute("""UPDATE sessions SET note = ?, endDate = ?, completed = 1
                               WHERE id = ? AND completed = 0""",
                            (note, session.deadline if session.endDate is None else session.endDate, session.id))

    def edit(self, session_id: str, note: str) -> None:
        with self.db:
            self.db.execute("UPDATE sessions SET note = ? WHERE id = ? AND completed = 1",
                            (note, session_id))

    def delete(self, session_id: str) -> None:
        with self.db:
            self.db.execute("DELETE FROM sessions WHERE id = ?", (session_id,))

    def history(self) -> list[Session]:
        return self._sessions("SELECT * FROM sessions WHERE completed = 1 ORDER BY startDate DESC")

    def goals(self, day: date) -> list[Goal]:
        return [Goal(**dict(row)) for row in self.db.execute(
            "SELECT * FROM goals WHERE day = ? ORDER BY createdAt, id", (day.isoformat(),))]

    def goal_counts(self) -> dict[str, int]:
        return {row["day"]: row["count"] for row in self.db.execute(
            "SELECT day, COUNT(*) AS count FROM goals GROUP BY day")}

    def add_goal(self, day: date, text: str) -> Goal:
        text = text.strip()
        if not text:
            raise ValueError("Enter a goal before saving.")
        goal = Goal(str(uuid.uuid4()), day.isoformat(), text, False, time.time())
        with self.db:
            self.db.execute("INSERT INTO goals(id, day, text, createdAt) VALUES (?, ?, ?, ?)",
                            (goal.id, goal.day, goal.text, goal.createdAt))
        return goal

    def edit_goal(self, goal_id: str, text: str) -> None:
        text = text.strip()
        if not text:
            raise ValueError("Enter a goal before saving.")
        with self.db:
            self.db.execute("UPDATE goals SET text = ? WHERE id = ?", (text, goal_id))

    def set_goal_completed(self, goal_id: str, completed: bool) -> None:
        with self.db:
            self.db.execute("UPDATE goals SET completed = ? WHERE id = ?", (completed, goal_id))

    def delete_goal(self, goal_id: str) -> None:
        with self.db:
            self.db.execute("DELETE FROM goals WHERE id = ?", (goal_id,))

    def close(self) -> None:
        self.db.close()


def local_day(timestamp: float) -> date:
    return datetime.fromtimestamp(timestamp).date()
