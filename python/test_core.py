from datetime import date, datetime
from pathlib import Path
import sqlite3
import tempfile
import unittest

from core import (DAY_START_HOUR, DURATION, Store, countdown, current_day, duration_text,
                  local_day, month_cells, set_day_start_hour, shifted_month)


class StoreTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.path = Path(self.temp.name) / "sessions.sqlite3"
        self.store = Store(self.path)
        self.start = 1_700_000_000.0

    def tearDown(self):
        self.store.close()
        self.temp.cleanup()

    def test_countdown_uses_absolute_time_after_reopening(self):
        session = self.store.start(self.start)
        self.store.close()
        self.store = Store(self.path)
        restored = self.store.active()
        self.assertEqual(restored.id, session.id)
        self.assertEqual(restored.remaining(self.start + 735), 465)
        self.assertEqual(restored.remaining(self.start + 1200), 0)
        self.assertEqual(restored.remaining(self.start + 86400), 0)

    def test_expired_session_stays_pending_until_note_saved(self):
        session = self.store.start(self.start)
        self.assertEqual(session.remaining(self.start + 2000), 0)
        self.assertFalse(self.store.active().completed)
        self.assertEqual(self.store.history(), [])
        self.store.complete(session, "Made a thing.\nThen tested it.", self.start + 2000)
        self.assertIsNone(self.store.active())
        saved = self.store.history()[0]
        self.assertEqual(saved.endDate, self.start + DURATION)
        self.assertEqual(saved.note, "Made a thing.\nThen tested it.")

    def test_cannot_complete_early(self):
        session = self.store.start(self.start)
        with self.assertRaises(ValueError):
            self.store.complete(session, "Too soon", self.start + 60)
        self.assertIsNotNone(self.store.active())

    def test_stop_early_survives_relaunch_and_delayed_note(self):
        session = self.store.start(self.start)
        stopped = self.store.stop(session, self.start + 175)
        self.assertEqual(stopped.remaining(self.start + 200), 0)
        self.assertEqual(stopped.duration, 175)
        self.store.close()
        self.store = Store(self.path)
        restored = self.store.active()
        self.assertEqual(restored.endDate, self.start + 175)
        self.assertFalse(restored.completed)
        self.store.complete(restored, "Finished early", self.start + 3000)
        saved = self.store.history()[0]
        self.assertEqual(saved.duration, 175)
        self.store.edit(saved.id, "Edited later")
        self.assertEqual(self.store.history()[0].duration, 175)

    def test_stopping_twice_preserves_first_end_and_stale_save_uses_it(self):
        session = self.store.start(self.start)
        self.store.stop(session, self.start + 30)
        self.store.stop(session, self.start + 60)
        self.store.complete(session, "", self.start + 90)
        self.assertEqual(self.store.history()[0].duration, 30)

    def test_stop_after_deadline_caps_duration(self):
        session = self.store.start(self.start)
        stopped = self.store.stop(session, self.start + 9000)
        self.assertEqual(stopped.duration, DURATION)

    def test_stopped_session_can_be_discarded(self):
        stopped = self.store.stop(self.store.start(self.start), self.start + 60)
        self.store.delete(stopped.id)
        self.assertIsNone(self.store.active())
        self.assertEqual(self.store.history(), [])

    def test_only_one_active_session_even_with_second_connection(self):
        session = self.store.start(self.start)
        other = Store(self.path)
        try:
            with self.assertRaises(sqlite3.IntegrityError):
                other.start(self.start + 1)
        finally:
            other.close()
        self.assertEqual(self.store.active().id, session.id)

    def test_cancel_deletes_persisted_session(self):
        self.store.delete(self.store.start(self.start).id)
        self.store.close()
        self.store = Store(self.path)
        self.assertIsNone(self.store.active())
        self.assertEqual(self.store.history(), [])

    def test_edit_blank_note_and_delete(self):
        session = self.store.start(self.start)
        self.store.complete(session, "", self.start + DURATION)
        self.store.edit(session.id, "Updated ✓\nSecond line")
        self.assertEqual(self.store.history()[0].note, "Updated ✓\nSecond line")
        self.store.delete(session.id)
        self.assertEqual(self.store.history(), [])

    def test_multiple_completed_sessions_and_local_day(self):
        for offset in (0, 2000, 90000):
            session = self.store.start(self.start + offset)
            self.store.complete(session, str(offset), session.deadline)
        history = self.store.history()
        self.assertEqual([s.note for s in history], ["90000", "2000", "0"])
        self.assertNotEqual(local_day(history[0].startDate), local_day(history[-1].startDate))


class DayBoundaryTests(unittest.TestCase):
    """A day runs 8am to 8am, so a session at 4am belongs to the day before."""

    def at(self, year, month, day, hour, minute=0):
        return datetime(year, month, day, hour, minute).timestamp()

    def test_after_midnight_belongs_to_the_previous_day(self):
        for hour in (0, 2, 4, 7):
            self.assertEqual(local_day(self.at(2026, 9, 18, hour)), date(2026, 9, 17),
                             f"{hour}:00 should still be the 17th")

    def test_the_boundary_itself_starts_the_new_day(self):
        self.assertEqual(local_day(self.at(2026, 9, 18, DAY_START_HOUR - 1, 59)), date(2026, 9, 17))
        self.assertEqual(local_day(self.at(2026, 9, 18, DAY_START_HOUR)), date(2026, 9, 18))

    def test_daytime_and_evening_are_unaffected(self):
        for hour in (9, 12, 17, 23):
            self.assertEqual(local_day(self.at(2026, 9, 18, hour)), date(2026, 9, 18),
                             f"{hour}:00 should be the 18th")

    def test_a_night_session_groups_with_the_evening_before_it(self):
        evening = self.at(2026, 9, 17, 23, 30)
        night = self.at(2026, 9, 18, 4, 30)
        self.assertEqual(local_day(evening), local_day(night))

    def test_current_day_uses_the_same_boundary(self):
        self.assertEqual(current_day(self.at(2026, 9, 18, 3)), date(2026, 9, 17))
        self.assertEqual(current_day(self.at(2026, 9, 18, 10)), date(2026, 9, 18))


class SettingsTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.path = Path(self.temp.name) / "sessions.sqlite3"
        self.store = Store(self.path)
        self.addCleanup(self.temp.cleanup)
        self.addCleanup(self.store.close)
        self.addCleanup(set_day_start_hour, DAY_START_HOUR)

    def test_defaults_when_nothing_has_been_saved(self):
        self.assertEqual(self.store.session_length(), DURATION)
        self.assertEqual(self.store.day_start(), DAY_START_HOUR)

    def test_preferences_survive_reopening(self):
        self.store.save_preferences(45 * 60, 6)
        self.store.close()
        reopened = Store(self.path)
        self.addCleanup(reopened.close)
        self.assertEqual(reopened.session_length(), 45 * 60)
        self.assertEqual(reopened.day_start(), 6)

    def test_saving_a_day_start_moves_the_boundary(self):
        self.store.save_preferences(DURATION, 5)
        self.assertEqual(local_day(datetime(2026, 9, 18, 4, 30).timestamp()), date(2026, 9, 17))
        self.assertEqual(local_day(datetime(2026, 9, 18, 5, 30).timestamp()), date(2026, 9, 18))

    def test_a_new_session_takes_the_configured_length(self):
        self.store.save_preferences(45 * 60, DAY_START_HOUR)
        session = self.store.start(1_700_000_000.0)
        self.assertEqual(session.length, 45 * 60)
        self.assertEqual(session.deadline, 1_700_000_000.0 + 45 * 60)

    def test_changing_the_length_leaves_past_sessions_alone(self):
        old = self.store.start(1_700_000_000.0)
        self.store.complete(old, "twenty", old.deadline)
        self.store.save_preferences(60 * 60, DAY_START_HOUR)
        kept = self.store.history()[0]
        self.assertEqual(kept.length, DURATION)
        self.assertEqual(kept.duration, DURATION)

    def test_out_of_range_values_are_refused(self):
        for length, hour in ((30, DAY_START_HOUR), (10 * 3600, DAY_START_HOUR), (DURATION, 24), (DURATION, -1)):
            with self.assertRaises(ValueError):
                self.store.save_preferences(length, hour)


class MigrationTests(unittest.TestCase):
    """Databases written before sessions carried their own length must still open."""

    def test_existing_database_gains_the_length_column(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "sessions.sqlite3"
            old = sqlite3.connect(path)
            old.execute("""CREATE TABLE sessions (
                               id TEXT PRIMARY KEY, startDate REAL NOT NULL, endDate REAL,
                               note TEXT NOT NULL DEFAULT '',
                               completed INTEGER NOT NULL DEFAULT 0)""")
            old.execute("INSERT INTO sessions VALUES ('a', 1700000000.0, 1700001200.0, 'before', 1)")
            old.commit()
            old.close()

            store = Store(path)
            self.addCleanup(store.close)
            session = store.history()[0]
            self.assertEqual(session.note, "before")
            self.assertEqual(session.length, DURATION)
            self.assertEqual(session.deadline, 1700000000.0 + DURATION)
            # And it still accepts new sessions afterwards.
            fresh = store.start(1700100000.0)
            self.assertEqual(fresh.length, DURATION)


class CalendarAndTimingTests(unittest.TestCase):
    def test_duration_text_for_short_and_full_sessions(self):
        self.assertEqual(duration_text(12.9), "12 seconds")
        self.assertEqual(duration_text(175), "2m 55s")
        self.assertEqual(duration_text(1200), "20 minutes")
        self.assertEqual(duration_text(1200 + 175), "22m 55s")

    def test_countdown_rounds_up_and_clamps(self):
        self.assertEqual(countdown(1200), "20:00")
        self.assertEqual(countdown(59.2), "01:00")
        self.assertEqual(countdown(0.1), "00:01")
        self.assertEqual(countdown(-2), "00:00")

    def test_leap_february_and_six_week_month(self):
        feb = [d for d in month_cells(2024, 2) if d]
        self.assertEqual(len(feb), 29)
        self.assertEqual(feb[-1], date(2024, 2, 29))
        self.assertEqual(len(month_cells(2026, 5)), 42)
        self.assertEqual(month_cells(2026, 3)[0], date(2026, 3, 1))

    def test_month_navigation_crosses_year(self):
        self.assertEqual(shifted_month(date(2026, 12, 5), 1), date(2027, 1, 1))
        self.assertEqual(shifted_month(date(2026, 1, 5), -1), date(2025, 12, 1))


class GoalTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.path = Path(self.temp.name) / "sessions.sqlite3"
        self.store = Store(self.path)
        self.day = date(2026, 9, 16)
        self.other_day = date(2026, 9, 17)

    def tearDown(self):
        self.store.close()
        self.temp.cleanup()

    def test_goals_belong_to_specific_calendar_days(self):
        today = self.store.add_goal(self.day, "Write a chapter")
        tomorrow = self.store.add_goal(self.other_day, "Read a chapter")
        self.assertEqual([g.id for g in self.store.goals(self.day)], [today.id])
        self.assertEqual([g.id for g in self.store.goals(self.other_day)], [tomorrow.id])
        self.assertEqual(self.store.goal_counts(), {self.day.isoformat(): 1, self.other_day.isoformat(): 1})

    def test_goal_edits_and_completion_survive_relaunch(self):
        goal = self.store.add_goal(self.day, "First draft")
        self.store.edit_goal(goal.id, " Finish the draft ✓\nReview it ")
        self.store.set_goal_completed(goal.id, True)
        self.store.close()
        self.store = Store(self.path)
        saved = self.store.goals(self.day)[0]
        self.assertEqual(saved.text, "Finish the draft ✓\nReview it")
        self.assertTrue(saved.completed)
        self.assertEqual(saved.day, self.day.isoformat())
        self.store.set_goal_completed(goal.id, False)
        self.assertFalse(self.store.goals(self.day)[0].completed)

    def test_delete_goal_leaves_other_goals_and_sessions(self):
        goal = self.store.add_goal(self.day, "Remove me")
        other = self.store.add_goal(self.other_day, "Keep me")
        session = self.store.start(1000)
        self.store.complete(session, "Saved note", session.deadline)
        self.store.delete_goal(goal.id)
        self.assertEqual(self.store.goals(self.day), [])
        self.assertEqual(self.store.goals(self.other_day)[0].id, other.id)
        self.assertEqual(self.store.history()[0].note, "Saved note")

    def test_blank_goals_are_rejected_without_losing_existing_text(self):
        with self.assertRaises(ValueError):
            self.store.add_goal(self.day, " \n\t")
        goal = self.store.add_goal(self.day, "Keep this")
        with self.assertRaises(ValueError):
            self.store.edit_goal(goal.id, " \n\t")
        self.assertEqual(self.store.goals(self.day)[0].text, "Keep this")

    def test_existing_session_database_gains_goals_without_data_loss(self):
        session = self.store.start(1000)
        self.store.complete(session, "Existing history", session.deadline)
        # Recreate the pre-goals schema while retaining its session data.
        with self.store.db:
            self.store.db.execute("DROP TABLE goals")
        self.store.close()
        self.store = Store(self.path)
        self.assertEqual(self.store.history()[0].note, "Existing history")
        self.assertEqual(self.store.goals(self.day), [])
        self.store.add_goal(self.day, "New goal")
        self.assertEqual(len(self.store.goals(self.day)), 1)


if __name__ == "__main__":
    unittest.main()
