"""Calendar: a native, single-window macOS app written in Python."""
from __future__ import annotations

from collections import Counter
from datetime import date, datetime
import fcntl
from pathlib import Path
import sqlite3
import sys
import time

import AppKit as A
import Foundation as F
import UserNotifications as UN
import objc
from PyObjCTools import AppHelper

from core import Store, countdown, duration_text, local_day, month_cells, shifted_month


def label(parent, text, x, y, width, height=24, size=14, secondary=False, centered=False):
    field = A.NSTextField.labelWithString_(text)
    field.setFrame_(((x, y), (width, height)))
    field.setFont_(A.NSFont.systemFontOfSize_(size))
    field.setTextColor_(A.NSColor.secondaryLabelColor() if secondary else A.NSColor.labelColor())
    if centered:
        field.setAlignment_(A.NSTextAlignmentCenter)
    parent.addSubview_(field)
    return field


def button(parent, title, x, y, width, height, target, action):
    control = A.NSButton.buttonWithTitle_target_action_(title, target, action)
    control.setFrame_(((x, y), (width, height)))
    control.setBezelStyle_(A.NSBezelStyleRounded)
    parent.addSubview_(control)
    return control


# Calendar's palette, in a single accent: red marks today, logged entries, and
# the running clock. A selected day takes a neutral fill so it never competes.
def accent():
    return A.NSColor.systemRedColor()


def confirm_color():
    """Save is affirmative; red would read as destructive next to Delete."""
    return A.NSColor.systemPurpleColor()


def selection_color():
    return A.NSColor.unemphasizedSelectedContentBackgroundColor()


def tinted(color, alpha):
    """Catalog colors need a concrete color space before they accept an alpha."""
    try:
        resolved = color.colorUsingColorSpace_(A.NSColorSpace.sRGBColorSpace())
        return (resolved or color).colorWithAlphaComponent_(alpha)
    except (ValueError, AttributeError):
        return None


def highlight(parent, size):
    box = A.NSBox.alloc().initWithFrame_(((0, 0), size))
    box.setBoxType_(A.NSBoxCustom)
    box.setTitlePosition_(A.NSNoTitle)
    box.setBorderWidth_(0)
    box.setCornerRadius_(7)
    box.setHidden_(True)
    parent.addSubview_(box)
    return box


def card(parent, frame):
    box = A.NSBox.alloc().initWithFrame_(frame)
    box.setBoxType_(A.NSBoxCustom)
    box.setTitlePosition_(A.NSNoTitle)
    box.setBorderWidth_(0)
    box.setCornerRadius_(8)
    box.setFillColor_(A.NSColor.controlBackgroundColor())
    parent.addSubview_(box)
    return box


ROW_INSET = 14


def styled(text, color, font, wrap=False, centered=False, struck=False, indent=0):
    paragraph = A.NSMutableParagraphStyle.alloc().init()
    paragraph.setAlignment_(A.NSTextAlignmentCenter if centered else A.NSTextAlignmentLeft)
    if wrap:
        paragraph.setLineBreakMode_(A.NSLineBreakByWordWrapping)
    if indent:
        paragraph.setFirstLineHeadIndent_(indent)
        paragraph.setHeadIndent_(indent)
        paragraph.setTailIndent_(-indent)
    attributes = {A.NSForegroundColorAttributeName: color,
                  A.NSFontAttributeName: font,
                  A.NSParagraphStyleAttributeName: paragraph}
    if struck:
        attributes[A.NSStrikethroughStyleAttributeName] = A.NSUnderlineStyleSingle
    return F.NSMutableAttributedString.alloc().initWithString_attributes_(text, attributes)


def day_title(number, marked, color, dot_color, bold):
    font = A.NSFont.boldSystemFontOfSize_(14) if bold else A.NSFont.systemFontOfSize_(14)
    title = styled(f"{number}", color, font, centered=True)
    if marked:
        title.appendAttributedString_(styled(" •", dot_color, font, centered=True))
    return title


def row_title(heading, body, struck=False):
    title = styled(heading + "\n", accent(),
                   A.NSFont.systemFontOfSize_weight_(13, A.NSFontWeightMedium),
                   wrap=True, indent=ROW_INSET)
    title.appendAttributedString_(styled(body, A.NSColor.secondaryLabelColor(),
                                         A.NSFont.systemFontOfSize_(13), wrap=True,
                                         struck=struck, indent=ROW_INSET))
    return title


def row_height(title, width, padding, minimum):
    """Rows fit their own text, so a one-line note does not sit in a tall empty card."""
    bounds = title.boundingRectWithSize_options_(
        (width, 10000), A.NSStringDrawingUsesLineFragmentOrigin)
    return max(minimum, int(bounds.size.height) + 1 + padding)


class BackgroundView(A.NSView):
    def drawRect_(self, rect):
        A.NSColor.windowBackgroundColor().setFill()
        A.NSRectFill(rect)


class CalendarDelegate(F.NSObject):
    @objc.python_method
    def initialize(self, data_dir: Path, notifications=True):
        self.store = Store(data_dir / "sessions.sqlite3")
        self.active = self.store.active()
        self.selected = date.today()
        self.month = self.selected.replace(day=1)
        self.editor = None
        self.editing = None
        self.goal_editor = None
        self.goal_editing = None
        self.center = UN.UNUserNotificationCenter.currentNotificationCenter() if notifications else None
        if self.center:
            self.center.setDelegate_(self)
        self.build_menu()
        style = A.NSWindowStyleMaskTitled | A.NSWindowStyleMaskClosable | A.NSWindowStyleMaskMiniaturizable
        self.window = A.NSWindow.alloc().initWithContentRect_styleMask_backing_defer_(
            ((0, 0), (840, 720)), style, A.NSBackingStoreBuffered, False)
        self.window.setTitle_("Calendar")
        self.window.setReleasedWhenClosed_(False)
        self.window.center()
        self.window.setContentView_(BackgroundView.alloc().initWithFrame_(((0, 0), (840, 720))))
        content = self.window.contentView()
        self.clock_label = label(content, "", 30, 600, 780, 36, 24, True, True)
        self.primary = button(content, "Start", 320, 547, 200, 36, self, "primaryAction:")
        self.primary.setControlSize_(A.NSControlSizeLarge)
        self.primary.setFont_(A.NSFont.systemFontOfSize_(
            A.NSFont.systemFontSizeForControlSize_(A.NSControlSizeLarge)))
        separator = A.NSBox.alloc().initWithFrame_(((24, 459), (792, 1)))
        separator.setBoxType_(A.NSBoxSeparator)
        content.addSubview_(separator)
        self.month_label = label(content, "", 30, 409, 245, 30, 19)
        button(content, "‹", 279, 410, 38, 30, self, "previousMonth:")
        button(content, "Today", 319, 410, 72, 30, self, "today:")
        button(content, "›", 393, 410, 38, 30, self, "nextMonth:")
        for index, name in enumerate(["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"]):
            label(content, name, 30 + index * 58, 375, 56, 22, 12, True, True)
        self.selection_box = highlight(content, (56, 44))
        self.today_box = highlight(content, (56, 44))
        self.day_buttons = []
        for index in range(42):
            row, col = divmod(index, 7)
            control = button(content, "", 30 + col * 58, 321 - row * 47, 56, 44, self, "selectDay:")
            control.setTag_(index)
            control.setButtonType_(A.NSButtonTypePushOnPushOff)
            # Flat cells, like Calendar's grid: a bezel would hide the fill behind it.
            control.setBordered_(False)
            self.day_buttons.append(control)
        self.day_heading = label(content, "", 466, 408, 345, 30, 18)
        self.day_tabs = A.NSSegmentedControl.alloc().initWithFrame_(((466, 371), (342, 28)))
        self.day_tabs.setSegmentCount_(2)
        self.day_tabs.setTrackingMode_(A.NSSegmentSwitchTrackingSelectOne)
        for index, title in enumerate(("Sessions", "Daily Goals")):
            self.day_tabs.setLabel_forSegment_(title, index)
            self.day_tabs.setWidth_forSegment_(167, index)
        self.day_tabs.setSelectedSegment_(0)
        self.day_tabs.setTarget_(self)
        self.day_tabs.setAction_("changeDayTab:")
        content.addSubview_(self.day_tabs)
        self.day_summary = label(content, "", 466, 342, 345, 22, 12, True)
        self.add_goal_button = button(content, "Add Goal", 466, 32, 342, 32, self, "addGoal:")
        self.add_goal_button.setHidden_(True)
        self.session_scroll = A.NSScrollView.alloc().initWithFrame_(((462, 32), (350, 300)))
        self.session_scroll.setHasVerticalScroller_(True)
        self.session_scroll.setDrawsBackground_(False)
        content.addSubview_(self.session_scroll)
        self.reload_history()
        self.refresh()
        self.timer = F.NSTimer.timerWithTimeInterval_target_selector_userInfo_repeats_(
            0.5, self, "tick:", None, True)
        F.NSRunLoop.mainRunLoop().addTimer_forMode_(self.timer, F.NSRunLoopCommonModes)
        self.window.makeKeyAndOrderFront_(None)
        A.NSApplication.sharedApplication().activateIgnoringOtherApps_(True)
        if self.active and self.active.remaining() > 0:
            self.schedule_notification(self.active)

    @objc.python_method
    def build_menu(self):
        menubar = A.NSMenu.alloc().init()
        app_item = A.NSMenuItem.alloc().init()
        menubar.addItem_(app_item)
        app_menu = A.NSMenu.alloc().initWithTitle_("Calendar")
        app_menu.addItemWithTitle_action_keyEquivalent_("About Calendar", "orderFrontStandardAboutPanel:", "")
        app_menu.addItem_(A.NSMenuItem.separatorItem())
        app_menu.addItemWithTitle_action_keyEquivalent_("Hide Calendar", "hide:", "h")
        app_menu.addItemWithTitle_action_keyEquivalent_("Quit Calendar", "terminate:", "q")
        app_item.setSubmenu_(app_menu)
        edit_item = A.NSMenuItem.alloc().init()
        menubar.addItem_(edit_item)
        edit_menu = A.NSMenu.alloc().initWithTitle_("Edit")
        for title, action, key in [("Undo", "undo:", "z"), ("Cut", "cut:", "x"),
                                   ("Copy", "copy:", "c"), ("Paste", "paste:", "v"),
                                   ("Select All", "selectAll:", "a")]:
            edit_menu.addItemWithTitle_action_keyEquivalent_(title, action, key)
        edit_item.setSubmenu_(edit_menu)
        window_item = A.NSMenuItem.alloc().init()
        menubar.addItem_(window_item)
        window_menu = A.NSMenu.alloc().initWithTitle_("Window")
        show = window_menu.addItemWithTitle_action_keyEquivalent_("Show Calendar", "showWindow:", "0")
        show.setTarget_(self)
        window_menu.addItemWithTitle_action_keyEquivalent_("Minimize", "performMiniaturize:", "m")
        window_item.setSubmenu_(window_menu)
        A.NSApplication.sharedApplication().setMainMenu_(menubar)

    def applicationDidFinishLaunching_(self, notification):
        try:
            self.initialize(Path.home() / "Library" / "Application Support" / "Twenty Python")
        except Exception as error:
            alert = A.NSAlert.alloc().init()
            alert.setMessageText_("Couldn’t open Calendar")
            alert.setInformativeText_(f"Your data has not been reset.\n\n{error}")
            alert.runModal()
            A.NSApplication.sharedApplication().terminate_(None)

    def applicationShouldHandleReopen_hasVisibleWindows_(self, app, visible):
        self.showWindow_(None)
        return True

    def applicationDidBecomeActive_(self, notification):
        if hasattr(self, "window"):
            self.refresh()

    def applicationWillTerminate_(self, notification):
        if hasattr(self, "timer"):
            self.timer.invalidate()
        if hasattr(self, "store"):
            self.store.close()

    def showWindow_(self, sender):
        self.window.makeKeyAndOrderFront_(None)
        A.NSApplication.sharedApplication().activateIgnoringOtherApps_(True)
        self.refresh()

    @objc.python_method
    def show_error(self, error):
        alert = A.NSAlert.alloc().init()
        alert.setMessageText_("Couldn’t save the change")
        alert.setInformativeText_(str(error))
        alert.beginSheetModalForWindow_completionHandler_(self.goal_editor or self.editor or self.window, None)

    def primaryAction_(self, sender):
        try:
            if self.active is None:
                self.active = self.store.start()
                self.schedule_notification(self.active)
            elif self.active.remaining() > 0:
                self.active = self.store.stop(self.active)
                self.remove_notification(self.active.id)
            else:
                self.open_editor(self.active)
            self.refresh()
        except (sqlite3.Error, ValueError) as error:
            self.show_error(error)

    def tick_(self, timer):
        self.refresh()

    @objc.python_method
    def refresh(self):
        if self.active:
            remaining = self.active.remaining()
            self.clock_label.setFrame_(((30, 593), (780, 75)))
            self.clock_label.setStringValue_(countdown(remaining))
            self.clock_label.setFont_(A.NSFont.monospacedDigitSystemFontOfSize_weight_(60, A.NSFontWeightLight))
            self.clock_label.setTextColor_(accent())
            self.primary.setTitle_("End Session" if remaining > 0 else "Save a note")
            if remaining <= 0 and self.editor is None and self.goal_editor is None and self.window.attachedSheet() is None:
                self.selected = local_day(self.active.startDate)
                self.month = self.selected.replace(day=1)
                self.render_calendar()
                self.open_editor(self.active)
        else:
            self.clock_label.setFrame_(((30, 600), (780, 36)))
            self.clock_label.setStringValue_(datetime.now().strftime("%I:%M:%S %p").lstrip("0"))
            self.clock_label.setFont_(A.NSFont.systemFontOfSize_(24))
            self.clock_label.setTextColor_(A.NSColor.labelColor())
            self.primary.setTitle_("Start")

    @objc.python_method
    def reload_history(self):
        self.history = self.store.history()
        self.render_calendar()

    @objc.python_method
    def render_calendar(self):
        self.month_label.setStringValue_(self.month.strftime("%B %Y"))
        self.cells = month_cells(self.month.year, self.month.month)
        counts = Counter(local_day(session.startDate) for session in self.history)
        goal_counts = self.store.goal_counts()
        today = date.today()
        self.place_highlights(today)
        for index, control in enumerate(self.day_buttons):
            day = self.cells[index] if index < len(self.cells) else None
            control.setHidden_(day is None)
            if day:
                goals = goal_counts.get(day.isoformat(), 0)
                marked = bool(counts[day] or goals)
                is_today = day == today
                selected = day == self.selected
                # Selection is drawn behind the cells, so today keeps its red
                # treatment whether or not it is also the selected day.
                control.setState_(A.NSControlStateValueOff)
                if is_today and selected:
                    number = dot = A.NSColor.whiteColor()
                elif is_today:
                    number, dot = accent(), accent()
                else:
                    number, dot = A.NSColor.labelColor(), accent()
                control.setFont_(A.NSFont.boldSystemFontOfSize_(14) if is_today
                                 else A.NSFont.systemFontOfSize_(14))
                control.setAttributedTitle_(day_title(day.day, marked, number, dot, is_today))
                control.setAccessibilityLabel_(
                    f"{day:%B %d, %Y}{', today' if is_today else ''}"
                    f"{', selected' if selected else ''}, {counts[day]} sessions, {goals} goals")
        self.day_heading.setStringValue_(self.selected.strftime("%A, %b %d"))
        self.render_day_panel()

    @objc.python_method
    def place_highlights(self, today):
        """Today is a red fill, the selected day a neutral one, as Calendar draws them."""
        selected_today = self.selected == today
        for box, day, color in (
                (self.today_box, today,
                 accent() if selected_today else tinted(accent(), 0.16)),
                (self.selection_box, None if selected_today else self.selected,
                 selection_color())):
            if day is not None and day in self.cells and color is not None:
                box.setFrame_(self.day_buttons[self.cells.index(day)].frame())
                box.setFillColor_(color)
                box.setHidden_(False)
            else:
                box.setHidden_(True)

    def changeDayTab_(self, sender):
        self.render_day_panel()

    @objc.python_method
    def render_day_panel(self):
        showing_goals = self.day_tabs.selectedSegment() == 1
        self.add_goal_button.setHidden_(not showing_goals)
        if showing_goals:
            self.render_goals()
            return
        self.session_scroll.setFrame_(((462, 32), (350, 300)))
        self.day_sessions = [s for s in self.history if local_day(s.startDate) == self.selected]
        count = len(self.day_sessions)
        total = duration_text(sum(session.duration for session in self.day_sessions))
        self.day_summary.setStringValue_(f"{count} {'session' if count == 1 else 'sessions'} · {total}")
        rows = []
        for session in self.day_sessions:
            start = datetime.fromtimestamp(session.startDate).strftime("%H:%M")
            end = datetime.fromtimestamp(session.endDate).strftime("%H:%M")
            preview = " ".join(session.note.split()) or "No note"
            if len(preview) > 130:
                preview = preview[:127] + "…"
            title = row_title(f"{start} – {end}", preview)
            rows.append((title, row_height(title, 322, 22, 56)))
        height = max(300, sum(row + 8 for _, row in rows))
        document = A.NSView.alloc().initWithFrame_(((0, 0), (330, height)))
        if not self.day_sessions:
            label(document, "No sessions this day", 10, height - 100, 310, 30, 15, True, True)
        y = height
        for index, (title, row) in enumerate(rows):
            y -= row + 8
            card(document, ((4, y), (322, row)))
            control = button(document, "", 4, y, 322, row, self, "editSession:")
            control.setBordered_(False)
            control.setAlignment_(A.NSTextAlignmentLeft)
            control.cell().setWraps_(True)
            control.setAttributedTitle_(title)
            control.setTag_(index)
            control.setToolTip_("Edit note or delete session")
        self.session_scroll.setDocumentView_(document)
        document.scrollPoint_((0, height))

    @objc.python_method
    def render_goals(self):
        self.day_goals = self.store.goals(self.selected)
        done = sum(goal.completed for goal in self.day_goals)
        self.day_summary.setStringValue_(f"{done} of {len(self.day_goals)} goals completed")
        self.session_scroll.setFrame_(((462, 78), (350, 254)))
        rows = []
        for goal in self.day_goals:
            preview = " ".join(goal.text.split())
            if len(preview) > 120:
                preview = preview[:117] + "…"
            title = styled(preview,
                           A.NSColor.secondaryLabelColor() if goal.completed else A.NSColor.labelColor(),
                           A.NSFont.systemFontOfSize_(13), wrap=True, struck=goal.completed,
                           indent=ROW_INSET)
            rows.append((goal, title, row_height(title, 290, 20, 44)))
        height = max(254, sum(row + 8 for _, _, row in rows))
        document = A.NSView.alloc().initWithFrame_(((0, 0), (330, height)))
        if not self.day_goals:
            label(document, "No goals for this day", 10, height - 85, 310, 26, 15, True, True)
            label(document, "Add something you want to do.", 10, height - 112, 310, 24, 13, True, True)
        y = height
        for index, (goal, title, row) in enumerate(rows):
            y -= row + 8
            mark = A.NSImage.imageWithSystemSymbolName_accessibilityDescription_(
                "checkmark.circle.fill" if goal.completed else "circle", goal.text)
            check = A.NSButton.buttonWithImage_target_action_(mark, self, "toggleGoal:")
            check.setBordered_(False)
            check.setImagePosition_(A.NSImageOnly)
            check.setContentTintColor_(accent() if goal.completed else A.NSColor.tertiaryLabelColor())
            check.setFrame_(((6, y + (row - 24) / 2), (24, 24)))
            check.setTag_(index)
            check.setAccessibilityLabel_(goal.text)
            document.addSubview_(check)
            card(document, ((36, y), (290, row)))
            control = button(document, "", 36, y, 290, row, self, "editGoal:")
            control.setBordered_(False)
            control.setAlignment_(A.NSTextAlignmentLeft)
            control.cell().setWraps_(True)
            control.setAttributedTitle_(title)
            control.setTag_(index)
            control.setToolTip_("Edit goal: " + goal.text)
        self.session_scroll.setDocumentView_(document)
        document.scrollPoint_((0, height))

    def addGoal_(self, sender):
        self.open_goal_editor()

    def editGoal_(self, sender):
        self.open_goal_editor(self.day_goals[sender.tag()])

    def toggleGoal_(self, sender):
        try:
            goal = self.day_goals[sender.tag()]
            self.store.set_goal_completed(goal.id, not goal.completed)
            self.render_day_panel()
        except sqlite3.Error as error:
            self.render_day_panel()
            self.show_error(error)

    @objc.python_method
    def open_goal_editor(self, goal=None):
        if self.editor is not None or self.goal_editor is not None:
            return
        self.goal_editing = goal
        self.goal_day = date.fromisoformat(goal.day) if goal else self.selected
        self.goal_editor = A.NSWindow.alloc().initWithContentRect_styleMask_backing_defer_(
            ((0, 0), (520, 320)), A.NSWindowStyleMaskTitled, A.NSBackingStoreBuffered, False)
        self.goal_editor.setReleasedWhenClosed_(False)
        self.goal_editor.setTitle_("Edit goal" if goal else "Add daily goal")
        view = self.goal_editor.contentView()
        label(view, "Edit goal" if goal else "Add daily goal", 24, 270, 472, 30, 22)
        label(view, self.goal_day.strftime("%A, %B %d, %Y"), 24, 240, 472, 24, 13, True)
        scroll = A.NSScrollView.alloc().initWithFrame_(((24, 70), (472, 155)))
        scroll.setHasVerticalScroller_(True)
        scroll.setBorderType_(A.NSBezelBorder)
        self.goal_field = A.NSTextView.alloc().initWithFrame_(((0, 0), (450, 155)))
        self.goal_field.setRichText_(False)
        self.goal_field.setAllowsUndo_(True)
        self.goal_field.setFont_(A.NSFont.systemFontOfSize_(15))
        self.goal_field.setTextColor_(A.NSColor.textColor())
        self.goal_field.setBackgroundColor_(A.NSColor.textBackgroundColor())
        self.goal_field.setTextContainerInset_((8, 8))
        self.goal_field.setVerticallyResizable_(True)
        self.goal_field.setHorizontallyResizable_(False)
        self.goal_field.setAutoresizingMask_(A.NSViewWidthSizable)
        self.goal_field.textContainer().setWidthTracksTextView_(True)
        self.goal_field.setString_(goal.text if goal else "")
        self.goal_field.setAccessibilityLabel_("Daily goal")
        scroll.setDocumentView_(self.goal_field)
        view.addSubview_(scroll)
        if goal:
            button(view, "Delete…", 24, 20, 94, 32, self, "deleteGoal:")
        cancel = button(view, "Cancel", 305, 20, 94, 32, self, "cancelGoal:")
        cancel.setKeyEquivalent_("\x1b")
        save = button(view, "Save", 402, 20, 94, 32, self, "saveGoal:")
        save.setKeyEquivalent_("\r")
        save.setBezelColor_(confirm_color())
        self.window.beginSheet_completionHandler_(self.goal_editor, None)
        self.goal_editor.makeFirstResponder_(self.goal_field)

    def saveGoal_(self, sender):
        try:
            text = str(self.goal_field.string())
            if self.goal_editing:
                self.store.edit_goal(self.goal_editing.id, text)
            else:
                self.store.add_goal(self.goal_day, text)
            self.close_goal_editor()
            self.render_calendar()
            self.refresh()
        except (sqlite3.Error, ValueError) as error:
            self.show_error(error)

    def cancelGoal_(self, sender):
        self.close_goal_editor()
        self.refresh()

    def deleteGoal_(self, sender):
        alert = A.NSAlert.alloc().init()
        alert.setMessageText_("Delete this goal?")
        alert.setInformativeText_("This goal will be permanently removed from this day.")
        alert.addButtonWithTitle_("Cancel")
        alert.addButtonWithTitle_("Delete Goal")
        alert.beginSheetModalForWindow_completionHandler_(self.goal_editor, self.delete_goal_response)

    @objc.python_method
    def delete_goal_response(self, response):
        if response != A.NSAlertSecondButtonReturn:
            return
        try:
            self.store.delete_goal(self.goal_editing.id)
            self.close_goal_editor()
            self.render_calendar()
            self.refresh()
        except sqlite3.Error as error:
            self.show_error(error)

    @objc.python_method
    def close_goal_editor(self):
        self.window.endSheet_(self.goal_editor)
        self.goal_editor.orderOut_(None)
        self.goal_editor = None
        self.goal_editing = None

    def previousMonth_(self, sender):
        if self.month.year > 1 or self.month.month > 1:
            self.selected = self.month = shifted_month(self.month, -1)
            self.render_calendar()

    def nextMonth_(self, sender):
        if self.month.year < 9999 or self.month.month < 12:
            self.selected = self.month = shifted_month(self.month, 1)
            self.render_calendar()

    def today_(self, sender):
        self.selected = date.today()
        self.month = self.selected.replace(day=1)
        self.render_calendar()

    def selectDay_(self, sender):
        self.selected = self.cells[sender.tag()]
        self.render_calendar()

    def editSession_(self, sender):
        self.open_editor(self.day_sessions[sender.tag()])

    @objc.python_method
    def open_editor(self, session):
        if self.editor is not None or self.goal_editor is not None:
            return
        self.editing = session
        self.editor = A.NSWindow.alloc().initWithContentRect_styleMask_backing_defer_(
            ((0, 0), (520, 350)), A.NSWindowStyleMaskTitled, A.NSBackingStoreBuffered, False)
        self.editor.setReleasedWhenClosed_(False)
        self.editor.setTitle_("Edit session" if session.completed else "What did you do?")
        view = self.editor.contentView()
        label(view, "Edit session" if session.completed else "What did you do?", 24, 300, 472, 30, 22)
        label(view, datetime.fromtimestamp(session.startDate).strftime("%b %d, %Y at %H:%M") + " · " + duration_text(session.duration),
              24, 270, 472, 24, 13, True)
        scroll = A.NSScrollView.alloc().initWithFrame_(((24, 70), (472, 185)))
        scroll.setHasVerticalScroller_(True)
        scroll.setBorderType_(A.NSBezelBorder)
        self.note_field = A.NSTextView.alloc().initWithFrame_(((0, 0), (450, 185)))
        self.note_field.setRichText_(False)
        self.note_field.setAllowsUndo_(True)
        self.note_field.setFont_(A.NSFont.systemFontOfSize_(15))
        self.note_field.setTextColor_(A.NSColor.textColor())
        self.note_field.setBackgroundColor_(A.NSColor.textBackgroundColor())
        self.note_field.setTextContainerInset_((8, 8))
        self.note_field.setVerticallyResizable_(True)
        self.note_field.setHorizontallyResizable_(False)
        self.note_field.setAutoresizingMask_(A.NSViewWidthSizable)
        self.note_field.textContainer().setWidthTracksTextView_(True)
        self.note_field.setString_(session.note)
        self.note_field.setAccessibilityLabel_("Session note")
        scroll.setDocumentView_(self.note_field)
        view.addSubview_(scroll)
        if session.completed:
            button(view, "Delete…", 24, 20, 94, 32, self, "deleteNote:")
            cancel = button(view, "Cancel", 305, 20, 94, 32, self, "cancelNote:")
            cancel.setKeyEquivalent_("\x1b")
        else:
            button(view, "Discard…", 24, 20, 94, 32, self, "deleteNote:")
        save = button(view, "Save", 402, 20, 94, 32, self, "saveNote:")
        save.setKeyEquivalent_("\r")
        save.setBezelColor_(confirm_color())
        self.window.beginSheet_completionHandler_(self.editor, None)
        self.editor.makeFirstResponder_(self.note_field)

    def saveNote_(self, sender):
        session = self.editing
        try:
            note = str(self.note_field.string())
            if session.completed:
                self.store.edit(session.id, note)
            else:
                self.store.complete(session, note)
                self.active = None
                self.remove_notification(session.id)
            self.close_editor()
            self.reload_history()
            self.refresh()
        except (sqlite3.Error, ValueError) as error:
            self.show_error(error)

    def cancelNote_(self, sender):
        if self.editing.completed:
            self.close_editor()
            self.refresh()

    def deleteNote_(self, sender):
        alert = A.NSAlert.alloc().init()
        alert.setMessageText_("Delete this session?" if self.editing.completed else "Discard this session?")
        alert.setInformativeText_("The session and its note will be permanently removed.")
        alert.addButtonWithTitle_("Cancel")
        alert.addButtonWithTitle_("Delete Session" if self.editing.completed else "Discard Session")
        alert.beginSheetModalForWindow_completionHandler_(self.editor, self.delete_response)

    @objc.python_method
    def delete_response(self, response):
        if response != A.NSAlertSecondButtonReturn:
            return
        try:
            self.store.delete(self.editing.id)
            if self.active and self.active.id == self.editing.id:
                self.remove_notification(self.active.id)
                self.active = None
            self.close_editor()
            self.reload_history()
            self.refresh()
        except sqlite3.Error as error:
            self.show_error(error)

    @objc.python_method
    def close_editor(self):
        self.window.endSheet_(self.editor)
        self.editor.orderOut_(None)
        self.editor = None
        self.editing = None

    @objc.python_method
    def schedule_notification(self, session):
        if not self.center:
            return

        def authorized(allowed, error):
            AppHelper.callAfter(self.add_notification, session, allowed, error)

        self.center.requestAuthorizationWithOptions_completionHandler_(
            UN.UNAuthorizationOptionAlert | UN.UNAuthorizationOptionSound, authorized)

    @objc.python_method
    def add_notification(self, session, allowed, error):
        # Permission callbacks may arrive after Cancel or after another session starts.
        if self.active is None or self.active.id != session.id or self.active.endDate is not None:
            return
        if error or not allowed:
            if error:
                F.NSLog("Calendar notification: %@", error.localizedDescription())
            return
        content = UN.UNMutableNotificationContent.alloc().init()
        content.setTitle_("Session complete")
        content.setBody_("What did you do? Open Calendar to save your note.")
        content.setSound_(UN.UNNotificationSound.defaultSound())
        trigger = UN.UNTimeIntervalNotificationTrigger.triggerWithTimeInterval_repeats_(
            max(1.0, session.deadline - time.time()), False)
        request = UN.UNNotificationRequest.requestWithIdentifier_content_trigger_(session.id, content, trigger)

        def added(error):
            AppHelper.callAfter(self.notification_added, session.id, error)

        self.center.addNotificationRequest_withCompletionHandler_(request, added)

    @objc.python_method
    def notification_added(self, session_id, error):
        if self.active is None or self.active.id != session_id or self.active.endDate is not None:
            self.remove_notification(session_id)
        elif error:
            F.NSLog("Calendar notification: %@", error.localizedDescription())

    @objc.python_method
    def remove_notification(self, session_id):
        if self.center:
            self.center.removePendingNotificationRequestsWithIdentifiers_([session_id])
            self.center.removeDeliveredNotificationsWithIdentifiers_([session_id])

    def userNotificationCenter_willPresentNotification_withCompletionHandler_(self, center, notification, handler):
        handler(UN.UNNotificationPresentationOptionBanner | UN.UNNotificationPresentationOptionSound)

    def userNotificationCenter_didReceiveNotificationResponse_withCompletionHandler_(self, center, response, handler):
        AppHelper.callAfter(self.showWindow_, None)
        handler()


def main():
    if sys.platform != "darwin":
        raise SystemExit("Calendar requires macOS 14 or later.")
    if not getattr(sys, "frozen", False):
        raise SystemExit("Build the macOS app first: run ./run.command (notifications require an app bundle).")
    # Retain the original data location and bundle identity across the app rename.
    data_dir = Path.home() / "Library" / "Application Support" / "Twenty Python"
    data_dir.mkdir(parents=True, exist_ok=True)
    data_dir.chmod(0o700)
    # Also protects the SQLite store when launching a second copy with open -n.
    with (data_dir / "app.lock").open("a") as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            for app in A.NSRunningApplication.runningApplicationsWithBundleIdentifier_("com.twenty.python"):
                if app.processIdentifier() != F.NSProcessInfo.processInfo().processIdentifier():
                    app.activateWithOptions_(A.NSApplicationActivateIgnoringOtherApps)
            return
        app = A.NSApplication.sharedApplication()
        app.setActivationPolicy_(A.NSApplicationActivationPolicyRegular)
        delegate = CalendarDelegate.alloc().init()
        app.setDelegate_(delegate)
        AppHelper.runEventLoop()


if __name__ == "__main__":
    main()
