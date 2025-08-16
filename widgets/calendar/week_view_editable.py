from __future__ import annotations
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import List, Tuple, Dict, Iterable, Any
from PyQt6 import QtCore, QtGui, QtWidgets
from PyQt6.QtCore import QDate
from theme.colors import (
    COLOR_PRIMARY_BG,
    COLOR_SECONDARY_BG,
    COLOR_TEXT,
    COLOR_TEXT_MUTED,
    COLOR_ACCENT,
)

_ROUNDED_RADIUS = 8
_SMALL_BLOCK_MIN = 45  # minutes

@dataclass
class EventBlock:
    task_id: int
    start: datetime
    end: datetime
    title: str = ""
    id: int | None = None
    meta: str = ""
    # opsiyonel not/rrule alanları UI tarafında taşınabilir
    notes: str | None = None
    rrule: str | None = None

class CalendarWeekView(QtWidgets.QWidget):
    blockCreated   = QtCore.pyqtSignal(object)
    blockMoved     = QtCore.pyqtSignal(object)
    blockResized   = QtCore.pyqtSignal(object)
    conflict       = QtCore.pyqtSignal(object)
    blockActivated = QtCore.pyqtSignal(object)
    emptyCellClicked = QtCore.pyqtSignal(object)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._anchor_monday = QDate.currentDate()
        self._anchor_monday = self._anchor_monday.addDays(-(self._anchor_monday.dayOfWeek()-1))
        self._header_height = 24
        self._hour_height   = 56
        self._left_timebar  = 64
        self._snap_minutes  = 15
        self._events: List[EventBlock] = []
        self._event_rects: Dict[int, QtCore.QRect] = {}
        self._drag_index = -1
        self._dragging = False
        self._drag_start_dt: datetime | None = None
        self._drag_block_snapshot: Tuple[datetime, datetime] | None = None
        self.setMouseTracking(True)
        self.setAcceptDrops(True)

    # ---- public helpers ----
    def eventAtPos(self, pt: QtCore.QPoint) -> EventBlock | None:
        idx = self._hit_test_block_index(pt)
        return self._events[idx] if idx != -1 else None

    def dateTimeRangeAtPos(self, pt: QtCore.QPoint, duration_minutes: int = 60) -> tuple[datetime, datetime]:
        """Return (start_dt, end_dt) snapped to grid at the given widget position."""
        day_idx = self._day_index_for_x(pt.x())
        date = self._anchor_monday.addDays(day_idx)
        hour, minute = self._time_for_y(pt.y())
        start_dt = datetime(date.year(), date.month(), date.day(), hour, minute)
        end_dt = start_dt + timedelta(minutes=max(1, duration_minutes))
        return start_dt, end_dt

    def setAnchorDate(self, qdate: QDate):
        delta = qdate.dayOfWeek() - 1
        self._anchor_monday = qdate.addDays(-delta)
        self.update()

    def minimumSizeHint(self) -> QtCore.QSize:
        return QtCore.QSize(600, 400)

    def sizeHint(self) -> QtCore.QSize:
        """Suggest full height so parent scroll area can enable vertical scroll."""
        return QtCore.QSize(800, self._header_height + self._hour_height * 24)

    def setEvents(self, events: Iterable[dict]):
        """Replace current events with those from ``events``.

        Each ``events`` item should contain ISO formatted ``start`` and ``end``
        datetimes and may optionally include ``title``, ``id``, ``notes`` and
        ``rrule`` fields.
        """
        self._events.clear()
        for ev in events:
            try:
                start_raw = (
                    ev.get("start")
                    or ev.get("start_ts")
                    or ev.get("starts_at")
                )
                end_raw = (
                    ev.get("end")
                    or ev.get("end_ts")
                    or ev.get("ends_at")
                )
                if not start_raw or not end_raw:
                    continue
                start = datetime.fromisoformat(str(start_raw).replace("Z", "+00:00"))
                end = datetime.fromisoformat(str(end_raw).replace("Z", "+00:00"))
            except Exception:
                continue
            meta_parts = []
            if ev.get("tag_name"): meta_parts.append(ev["tag_name"])
            if ev.get("project_name"): meta_parts.append(ev["project_name"])
            if ev.get("parent_title"): meta_parts.append(ev["parent_title"])
            meta = ">".join(meta_parts)
            block = EventBlock(
                task_id=int(ev.get("task_id") or ev.get("taskId") or 0),
                start=start,
                end=end,
                title=ev.get("title", ""),
                id=int(ev["id"]) if ev.get("id") is not None else None,
                meta=meta,
                notes=ev.get("notes"),
                rrule=ev.get("rrule"),
            )
            self._events.append(block)
        self.update()

    # ---------- drag & drop (kanban -> takvim) ----------
    def dragEnterEvent(self, e: QtGui.QDragEnterEvent):
        if e.mimeData().hasFormat('application/x-task-id'):
            e.acceptProposedAction()
        else:
            e.ignore()

    def dragMoveEvent(self, e: QtGui.QDragMoveEvent):
        if e.mimeData().hasFormat('application/x-task-id'):
            e.acceptProposedAction()
        else:
            e.ignore()

    def dropEvent(self, e: QtGui.QDropEvent):
        if not e.mimeData().hasFormat('application/x-task-id'):
            e.ignore(); return
        task_id = int(bytes(e.mimeData().data('application/x-task-id')).decode('utf-8'))
        title = f"Task #{task_id}"
        if e.mimeData().hasFormat('application/x-task-title'):
            try:
                title = bytes(e.mimeData().data('application/x-task-title')).decode('utf-8')
            except Exception:
                title = f"Task #{task_id}"
        pos = e.position().toPoint()
        day_idx = self._day_index_for_x(pos.x())
        date = self._anchor_monday.addDays(day_idx)
        hour, minute = self._time_for_y(pos.y())
        start_dt = datetime(date.year(), date.month(), date.day(), hour, minute)
        end_dt = start_dt + timedelta(minutes=60)
        ev = EventBlock(task_id=task_id, start=start_dt, end=end_dt, title=title)
        self.blockCreated.emit(ev)
        self._events.append(ev)
        self.update()
        e.acceptProposedAction()

    # --- mouse: move & double-click ---
    def mousePressEvent(self, e: QtGui.QMouseEvent):
        if e.button() == QtCore.Qt.MouseButton.LeftButton:
            idx = self._hit_test_block_index(e.position().toPoint())
            if idx != -1:
                self._drag_index = idx
                self._dragging = True
                b = self._events[self._drag_index]
                self._drag_start_dt = b.start
                self._drag_block_snapshot = (b.start, b.end)
                self.update()
                return
            else:
                try:
                    start_dt, end_dt = self.dateTimeRangeAtPos(e.position().toPoint())
                    payload = {'start': start_dt, 'end': end_dt}
                    self.emptyCellClicked.emit(payload)
                except Exception:
                    pass
        super().mousePressEvent(e)

    def mouseMoveEvent(self, e: QtGui.QMouseEvent):
        if self._dragging and 0 <= self._drag_index < len(self._events):
            b = self._events[self._drag_index]
            hour, minute = self._time_for_y(e.position().toPoint().y())
            day_idx = self._day_index_for_x(e.position().toPoint().x())
            new_start = datetime(self._anchor_monday.addDays(day_idx).year(),
                                 self._anchor_monday.addDays(day_idx).month(),
                                 self._anchor_monday.addDays(day_idx).day(),
                                 hour, minute)
            dur = b.end - b.start
            b.start = new_start
            b.end = new_start + dur
            try:
                self.blockMoved.emit(b)
            except Exception:
                pass
            self.update()
            return
        super().mouseMoveEvent(e)

    def mouseReleaseEvent(self, e: QtGui.QMouseEvent):
        if self._dragging:
            self._dragging = False
            self._drag_index = -1
            self._drag_block_snapshot = None
            self.update()
            return
        super().mouseReleaseEvent(e)

    def mouseDoubleClickEvent(self, e: QtGui.QMouseEvent):
        idx = self._hit_test_block_index(e.position().toPoint())
        if idx != -1:
            evb = self._events[idx]
            try:
                self.blockActivated.emit(evb)
                return
            except Exception:
                pass
        super().mouseDoubleClickEvent(e)

    # ---------- helpers ----------
    def _date_for_x(self, x: int) -> QDate:
        col_width = max(1.0, (self.width() - self._left_timebar) / 7.0)
        day_index = int((x - self._left_timebar) // col_width)
        day_index = max(0, min(6, day_index))
        return self._anchor_monday.addDays(day_index)

    def _day_index_for_x(self, x: int) -> int:
        col_width = max(1.0, (self.width() - self._left_timebar) / 7.0)
        return max(0, min(6, int((x - self._left_timebar) // col_width)))

    def _time_for_y(self, y: int) -> Tuple[int, int]:
        y2 = max(self._header_height, y) - self._header_height
        minutes = int(y2 / self._hour_height * 60)
        snap = self._snap_minutes
        minutes = (minutes // snap) * snap
        hour = max(0, min(23, minutes // 60))
        minute = minutes % 60
        return hour, minute

    def _duration_minutes(self, b: EventBlock) -> int:
        return max(1, int((b.end - b.start).total_seconds() // 60))

    def _rect_for_block(self, b: EventBlock) -> QtCore.QRectF:
        day_idx = self._anchor_monday.daysTo(QDate(b.start.year, b.start.month, b.start.day))
        if 0 <= day_idx <= 6:
            col_width = (self.width() - self._left_timebar) / 7.0
            x = self._left_timebar + day_idx * col_width + 2
            start_y = self._header_height + (b.start.hour + b.start.minute / 60) * self._hour_height
            end_y = self._header_height + (b.end.hour + b.end.minute / 60) * self._hour_height
            return QtCore.QRectF(x + 2, start_y + 2, col_width - 6, max(18, end_y - start_y - 4))
        return QtCore.QRectF()

    def _hit_test_block_index(self, pt: QtCore.QPoint | QtCore.QPointF) -> int:
        """Return index of the topmost event block under ``pt`` or ``-1``.

        ``QtCore.QRectF.contains`` expects a ``QPointF`` argument, so the
        provided point (which may be ``QPoint`` from mouse events) is converted
        accordingly before testing each block's rectangle.
        """
        ptf = pt if isinstance(pt, QtCore.QPointF) else QtCore.QPointF(pt)
        topmost = -1
        for b in sorted(self._events, key=lambda x: self._duration_minutes(x), reverse=True):
            r = self._rect_for_block(b)
            if r.contains(ptf):
                topmost = self._events.index(b)
        return topmost

    def _paint_blocks(self, p: QtGui.QPainter):
        self._event_rects.clear()
        for b in sorted(self._events, key=lambda x: self._duration_minutes(x), reverse=True):
            r = self._rect_for_block(b)
            if r.isNull():
                continue
            idx = self._events.index(b)
            self._event_rects[idx] = QtCore.QRect(int(r.x()), int(r.y()), int(r.width()), int(r.height()))
            dur = self._duration_minutes(b)
            fill = QtGui.QColor(COLOR_ACCENT)
            if dur <= _SMALL_BLOCK_MIN:
                fill = QtGui.QColor(fill).lighter(120)
            pen = QtGui.QPen(QtGui.QColor(0, 0, 0, 60))
            p.setPen(pen)
            p.setBrush(QtGui.QBrush(fill))
            p.drawRoundedRect(r.adjusted(0.5, 0.5, -0.5, -0.5), _ROUNDED_RADIUS, _ROUNDED_RADIUS)
            p.setPen(QtGui.QPen(QtGui.QColor(COLOR_TEXT)))
            p.drawText(
                r.adjusted(6, 2, -6, 0),
                QtCore.Qt.AlignmentFlag.AlignTop | QtCore.Qt.AlignmentFlag.AlignLeft,
                b.title,
            )
            meta = getattr(b, "meta", "")
            if meta:
                p.setPen(QtGui.QPen(QtGui.QColor(COLOR_TEXT_MUTED)))
                p.drawText(
                    r.adjusted(6, 18, -6, 0),
                    QtCore.Qt.AlignmentFlag.AlignTop | QtCore.Qt.AlignmentFlag.AlignLeft,
                    meta,
                )
                p.setPen(QtGui.QPen(QtGui.QColor(COLOR_TEXT)))

    # ---------- painting ----------
    def paintEvent(self, ev):
        p = QtGui.QPainter(self)
        p.fillRect(self.rect(), QtGui.QColor(COLOR_PRIMARY_BG))

        header_rect = QtCore.QRect(0, 0, self.width(), self._header_height)
        p.fillRect(header_rect, QtGui.QColor(COLOR_SECONDARY_BG))

        grid_color = QtGui.QColor(255, 255, 255, 40)
        col_width = (self.width() - self._left_timebar) / 7.0

        # day headers + vertical grid
        for i in range(7):
            x = int(self._left_timebar + i * col_width)
            r = QtCore.QRect(x, 0, int(col_width), self._header_height)
            label_date = self._anchor_monday.addDays(i)
            txt = label_date.toString('ddd dd')
            p.setPen(QtGui.QPen(QtGui.QColor(COLOR_TEXT_MUTED)))
            p.drawText(r.adjusted(8, 0, -8, 0),
                       QtCore.Qt.AlignmentFlag.AlignVCenter | QtCore.Qt.AlignmentFlag.AlignLeft, txt)
            p.setPen(QtGui.QPen(grid_color))
            p.drawLine(x, self._header_height, x, self.height())

        # hours horizontal + time labels
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

        # event rect hesaplama + çizim
        self._paint_blocks(p)
