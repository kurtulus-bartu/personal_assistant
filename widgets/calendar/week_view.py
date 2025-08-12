from __future__ import annotations
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import List, Tuple
from PyQt6 import QtCore, QtGui, QtWidgets
from PyQt6.QtCore import QDate, QRect
from theme.colors import COLOR_PRIMARY_BG, COLOR_SECONDARY_BG, COLOR_TEXT, COLOR_TEXT_MUTED, COLOR_ACCENT


@dataclass
class EventBlock:
    task_id: int
    start: datetime
    end: datetime
    title: str = ""


class CalendarWeekView(QtWidgets.QWidget):
    blockCreated = QtCore.pyqtSignal(object)  # EventBlock
    blockMoved = QtCore.pyqtSignal(object)
    blockResized = QtCore.pyqtSignal(object)
    conflict = QtCore.pyqtSignal(object)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAcceptDrops(True)
        self._anchor_monday = self._monday_of(QDate.currentDate())
        self._hour_height = 48
        self._snap_minutes = 15
        self._header_height = 28
        self._left_timebar = 56
        self._events: List[EventBlock] = []
        self.setMinimumHeight(self._header_height + 24 * self._hour_height)
        self.setMouseTracking(True)

    def setAnchorDate(self, date: QDate):
        self._anchor_monday = self._monday_of(date)
        self.update()

    def addEvent(self, ev: EventBlock):
        self._events.append(ev)
        self.update()

    def setEvents(self, events: List[dict]):
        """Replace current events with those from ``events``."""
        self._events.clear()
        for ev in events:
            try:
                start = datetime.fromisoformat(ev["start"])
                end = datetime.fromisoformat(ev["end"])
            except Exception:
                continue
            self._events.append(
                EventBlock(
                    task_id=int(ev.get("task_id") or ev.get("taskId") or 0),
                    start=start,
                    end=end,
                    title=ev.get("title", ""),
                )
            )
        self.update()

    # --- helpers ---
    def _monday_of(self, d: QDate) -> QDate:
        delta = d.dayOfWeek() - 1  # Monday=1
        return d.addDays(-delta)

    def _date_for_x(self, x: int) -> QDate:
        col_width = (self.width() - self._left_timebar) / 7.0
        day_index = int((x - self._left_timebar) // col_width)
        day_index = max(0, min(6, day_index))
        return self._anchor_monday.addDays(day_index)

    def _time_for_y(self, y: int) -> Tuple[int, int]:
        y2 = max(self._header_height, y) - self._header_height
        minutes = int(y2 / self._hour_height * 60)
        snap = self._snap_minutes
        minutes = (minutes // snap) * snap
        hour = max(0, min(23, minutes // 60))
        minute = minutes % 60
        return hour, minute

    # --- DnD ---
    def dragEnterEvent(self, e: QtGui.QDragEnterEvent):
        if e.mimeData().hasFormat('application/x-task-id'):
            e.acceptProposedAction()
        else:
            e.ignore()

    def dropEvent(self, e: QtGui.QDropEvent):
        if not e.mimeData().hasFormat('application/x-task-id'):
            e.ignore(); return
        task_id = int(bytes(e.mimeData().data('application/x-task-id')).decode('utf-8'))
        pos = e.position().toPoint()
        date = self._date_for_x(pos.x())
        hour, minute = self._time_for_y(pos.y())
        start_dt = datetime(date.year(), date.month(), date.day(), hour, minute)
        end_dt = start_dt + timedelta(minutes=30)
        ev = EventBlock(task_id=task_id, start=start_dt, end=end_dt, title=f"Task #{task_id}")
        self.blockCreated.emit(ev)
        self.addEvent(ev)
        e.acceptProposedAction()

    # --- paint ---
    def paintEvent(self, ev):
        p = QtGui.QPainter(self)
        p.fillRect(self.rect(), QtGui.QColor(COLOR_PRIMARY_BG))
        header_rect = QRect(0, 0, self.width(), self._header_height)
        p.fillRect(header_rect, QtGui.QColor(COLOR_SECONDARY_BG))
        col_width = (self.width() - self._left_timebar) / 7.0
        grid_color = QtGui.QColor(255, 255, 255, 40)
        # left time bar label
        p.setPen(QtGui.QPen(QtGui.QColor(COLOR_TEXT_MUTED)))
        p.drawText(8, 18, "Week")
        # day headers + vertical grid
        for i in range(7):
            x = int(self._left_timebar + i * col_width)
            r = QtCore.QRect(x, 0, int(col_width), self._header_height)
            label_date = self._anchor_monday.addDays(i)
            txt = label_date.toString('ddd dd')
            p.drawText(
                r.adjusted(8, 0, -8, 0),
                QtCore.Qt.AlignmentFlag.AlignVCenter | QtCore.Qt.AlignmentFlag.AlignLeft,
                txt,
            )
            p.setPen(QtGui.QPen(grid_color))
            p.drawLine(x, self._header_height, x, self.height())
            p.setPen(QtGui.QPen(QtGui.QColor(COLOR_TEXT_MUTED)))
        # hours horizontal
        for h in range(25):
            y = self._header_height + int(h * self._hour_height)
            p.setPen(QtGui.QPen(grid_color))
            p.drawLine(self._left_timebar, y, self.width(), y)
            if h < 24:
                p.setPen(QtGui.QPen(QtGui.QColor(COLOR_TEXT_MUTED)))
                p.drawText(6, y + 14, f"{h:02d}:00")
        # left divider
        p.setPen(QtGui.QPen(grid_color))
        p.drawLine(self._left_timebar, 0, self._left_timebar, self.height())
        # events
        for evb in self._events:
            day_idx = self._anchor_monday.daysTo(QDate(evb.start.year, evb.start.month, evb.start.day))
            if 0 <= day_idx <= 6:
                x = int(self._left_timebar + day_idx * col_width) + 2
                start_y = self._header_height + int((evb.start.hour + evb.start.minute/60) * self._hour_height)
                end_y = self._header_height + int((evb.end.hour + evb.end.minute/60) * self._hour_height)
                r = QtCore.QRect(x + 2, start_y + 2, int(col_width) - 6, max(18, end_y - start_y - 4))
                p.fillRect(r, QtGui.QColor(COLOR_ACCENT))
                p.setPen(QtGui.QPen(QtGui.QColor(COLOR_TEXT)))
                p.drawText(
                    r.adjusted(6, 0, -6, 0),
                    QtCore.Qt.AlignmentFlag.AlignVCenter | QtCore.Qt.AlignmentFlag.AlignLeft,
                    evb.title,
                )
