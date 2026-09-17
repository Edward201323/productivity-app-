"""Native UI smoke check. Uses temporary data and never schedules notifications."""
from datetime import date
from pathlib import Path
import tempfile
import time
import os

import AppKit as A
import Foundation as F

from calendar_app import CalendarDelegate


def pump():
    F.NSRunLoop.currentRunLoop().runUntilDate_(F.NSDate.dateWithTimeIntervalSinceNow_(0.15))


def main():
    app = A.NSApplication.sharedApplication()
    app.setActivationPolicy_(A.NSApplicationActivationPolicyRegular)
    with tempfile.TemporaryDirectory() as directory:
        delegate = CalendarDelegate.alloc().init()
        delegate.initialize(Path(directory), notifications=False)
        pump()
        assert delegate.primary.title() == "Start"
        delegate.primaryAction_(None)
        assert delegate.active is not None
        assert delegate.primary.title() == "End Session"
        delegate.primaryAction_(None)
        pump()
        assert delegate.editor is not None
        assert delegate.active.endDate is not None
        delegate.note_field.setString_("Finished early")
        delegate.saveNote_(None)
        pump()
        assert delegate.history[0].duration < 20
        delegate.open_editor(delegate.history[0])
        pump()
        delegate.delete_response(A.NSAlertSecondButtonReturn)
        pump()
        delegate.primaryAction_(None)
        delegate.primaryAction_(None)
        pump()
        delegate.delete_response(A.NSAlertFirstButtonReturn)
        assert delegate.store.active() is not None
        delegate.delete_response(A.NSAlertSecondButtonReturn)
        pump()
        assert delegate.store.active() is None
        # Simulate reopening with an expired persisted session.
        delegate.active = delegate.store.start(time.time() - 1300)
        delegate.refresh()
        pump()
        assert delegate.editor is not None
        assert delegate.editor.title() == "What did you do?"
        delegate.note_field.setString_("UI smoke check\nA multiline note.")
        delegate.saveNote_(None)
        pump()
        assert delegate.active is None
        assert len(delegate.history) == 1
        assert delegate.history[0].note == "UI smoke check\nA multiline note."
        delegate.open_editor(delegate.history[0])
        pump()
        delegate.note_field.setString_("Edited")
        delegate.saveNote_(None)
        pump()
        assert delegate.history[0].note == "Edited"
        delegate.nextMonth_(None)
        delegate.previousMonth_(None)
        delegate.today_(None)
        assert delegate.selected == date.today()
        delegate.day_tabs.setSelectedSegment_(1)
        delegate.changeDayTab_(None)
        assert not delegate.add_goal_button.isHidden()
        assert delegate.day_goals == []
        delegate.addGoal_(None)
        pump()
        delegate.goal_field.setString_("Write a first draft")
        delegate.saveGoal_(None)
        pump()
        assert delegate.day_goals[0].text == "Write a first draft"
        checkbox = delegate.session_scroll.documentView().subviews()[0]
        checkbox.performClick_(None)
        assert delegate.store.goals(date.today())[0].completed
        delegate.open_goal_editor(delegate.day_goals[0])
        pump()
        delegate.goal_field.setString_("Write and review the first draft")
        delegate.saveGoal_(None)
        pump()
        assert delegate.day_goals[0].text == "Write and review the first draft"
        delegate.nextMonth_(None)
        assert delegate.day_goals == []
        delegate.addGoal_(None)
        pump()
        delegate.goal_field.setString_("A goal for another day")
        delegate.saveGoal_(None)
        pump()
        future_day = delegate.selected
        delegate.today_(None)
        assert len(delegate.day_goals) == 1
        assert delegate.day_goals[0].completed
        assert len(delegate.store.goals(future_day)) == 1
        delegate.day_tabs.setSelectedSegment_(0)
        delegate.changeDayTab_(None)
        assert delegate.add_goal_button.isHidden()
        assert len(delegate.day_sessions) == 1
        delegate.day_tabs.setSelectedSegment_(1)
        delegate.changeDayTab_(None)
        for appearance in (A.NSAppearanceNameDarkAqua, A.NSAppearanceNameAqua):
            delegate.window.setAppearance_(A.NSAppearance.appearanceNamed_(appearance))
            pump()
            if directory := os.environ.get("TWENTY_TEST_SNAPSHOTS"):
                view = delegate.window.contentView()
                bitmap = view.bitmapImageRepForCachingDisplayInRect_(view.bounds())
                delegate.window.effectiveAppearance().performAsCurrentDrawingAppearance_(
                    lambda: view.cacheDisplayInRect_toBitmapImageRep_(view.bounds(), bitmap))
                image = bitmap.representationUsingType_properties_(A.NSBitmapImageFileTypePNG, {})
                image.writeToFile_atomically_(str(Path(directory) / f"calendar-{appearance}.png"), True)
        delegate.open_editor(delegate.history[0])
        pump()
        delegate.delete_response(A.NSAlertFirstButtonReturn)
        assert len(delegate.store.history()) == 1
        delegate.delete_response(A.NSAlertSecondButtonReturn)
        pump()
        assert delegate.store.history() == []
        delegate.open_goal_editor(delegate.day_goals[0])
        pump()
        delegate.delete_goal_response(A.NSAlertFirstButtonReturn)
        assert len(delegate.store.goals(date.today())) == 1
        delegate.delete_goal_response(A.NSAlertSecondButtonReturn)
        pump()
        assert delegate.store.goals(date.today()) == []
        delegate.addGoal_(None)
        pump()
        delegate.goal_field.setString_("Keep this goal draft while the timer finishes")
        delegate.active = delegate.store.start(time.time() - 1300)
        delegate.refresh()
        assert delegate.goal_editor is not None
        assert delegate.editor is None
        delegate.saveGoal_(None)
        pump()
        delegate.refresh()
        assert delegate.editor is not None
        assert delegate.store.goals(date.today())[0].text == "Keep this goal draft while the timer finishes"
        delegate.note_field.setString_("Session finished while editing a goal")
        delegate.saveNote_(None)
        pump()
        delegate.timer.invalidate()
        delegate.window.orderOut_(None)
        delegate.store.close()
    print("Native UI smoke check passed: sessions, goals, date isolation, checkboxes, editing, deletion, tabs, appearances, and timer completion during goal editing.")


if __name__ == "__main__":
    main()
