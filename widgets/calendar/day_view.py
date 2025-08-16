from __future__ import annotations
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import List, Dict, Tuple, Iterable
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
    meta: str = ""
    due: str = ""

class CalendarDayView(QtWidgets.QWidget):
    blockCreated = QtCore.pyqtSignal(object)
    blockMoved   = QtCore.pyqtSignal(object)
    blockResized = QtCore.pyqtSignal(object)
    conflict     = QtCore.pyqtSignal(object)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._anchor_date = QDate.currentDate()
        self._header_h = 28
        self._hour_h = 48
        self._left_timebar = 56
        self._snap_minutes = 15
        self._events: List[EventBlock] = []
        self._all_events: List[dict] = []
        self._event_rects: Dict[int, QtCore.QRect] = {}
        self._z_order: List[int] = []
        self._drag_mode = None
        self._active_index = -1
        self._active_block: EventBlock | None = None
        self._drag_offset_px = 0
        self.setMouseTracking(True)
        self.setAcceptDrops(True)

    def sizeHint(self):
        return QtCore.QSize(800, self._header_h + 24 * self._hour_h)

    def set_date(self, qdate: QDate):
        self._anchor_date = QtCore.QDate(qdate)
        self.reload()

    def setDate(self, date: QDate):  # backward compat
        self.set_date(date)

    def setEvents(self, events: Iterable[dict]):
        self._all_events = list(events)
        self.reload()

    def reload(self):
        self._events.clear()
        for ev in self._all_events:
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
            if start.date() != self._anchor_date.toPyDate():
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
                meta=meta,
                due=ev.get("due", ""),
            )
            self._events.append(block)
        self.update()

    def _layout_columns(self, evs: List[EventBlock]):
        items = sorted(evs, key=lambda e: (e.start, e.end))
        active: List[EventBlock] = []
        for ev in items:
            active = [a for a in active if a.end > ev.start]
            used = {getattr(a, '_col', -1) for a in active}
            col = 0
            while col in used:
                col += 1
            ev._col = col
            active.append(ev)
        max_col = 1 + max((getattr(e, '_col', 0) for e in items), default=0)
        for e in items:
            e._colcount = max_col
        return items

    def _rect_for_event(self, evb: EventBlock) -> QtCore.QRectF:
        start_y = self._header_h + (evb.start.hour + evb.start.minute/60) * self._hour_h
        end_y = self._header_h + (evb.end.hour + evb.end.minute/60) * self._hour_h
        return QtCore.QRectF(
            self._left_timebar + 4,
            start_y + 2,
            self.width() - self._left_timebar - 8,
            max(18, end_y - start_y - 4),
        )

    def _time_for_y(self, y: int) -> Tuple[int, int]:
        y2 = max(self._header_h, y) - self._header_h
        minutes = int(y2 / self._hour_h * 60)
        minutes = (minutes // self._snap_minutes) * self._snap_minutes
        hour = max(0, min(23, minutes // 60))
        minute = minutes % 60
        return hour, minute

    # --- DnD from Kanban ---
    def dragEnterEvent(self, e: QtGui.QDragEnterEvent):
        e.acceptProposedAction() if e.mimeData().hasFormat('application/x-task-id') else e.ignore()

    def dropEvent(self, e: QtGui.QDropEvent):
        if not e.mimeData().hasFormat('application/x-task-id'): e.ignore(); return
        task_id = int(bytes(e.mimeData().data('application/x-task-id')).decode('utf-8'))
        pos = e.position().toPoint()
        hour, minute = self._time_for_y(pos.y())
        start_dt = datetime(
            self._anchor_date.year(),
            self._anchor_date.month(),
            self._anchor_date.day(),
            hour,
            minute,
        )
        end_dt = start_dt + timedelta(minutes=60)
        title = f"Task #{task_id}"
        if e.mimeData().hasFormat('application/x-task-title'):
            try:
                title = bytes(e.mimeData().data('application/x-task-title')).decode('utf-8')
            except Exception:
                title = f"Task #{task_id}"
        meta = ""
        if e.mimeData().hasFormat('application/x-task-meta'):
            try:
                meta = bytes(e.mimeData().data('application/x-task-meta')).decode('utf-8')
            except Exception:
                meta = ""
        due = ""
        if e.mimeData().hasFormat('application/x-task-due'):
            try:
                due = bytes(e.mimeData().data('application/x-task-due')).decode('utf-8')
            except Exception:
                due = ""
        ev = EventBlock(task_id=task_id, start=start_dt, end=end_dt, title=title, meta=meta, due=due)
        self.blockCreated.emit(ev)
        self._events.append(ev)
        self.update()
        e.acceptProposedAction()

    # --- mouse: move/resize & dışa sürükleme (takvim -> kanban) ---
    def mousePressEvent(self, e: QtGui.QMouseEvent):
        if e.button() in (QtCore.Qt.MouseButton.RightButton, QtCore.Qt.MouseButton.LeftButton) and \
           (e.button() == QtCore.Qt.MouseButton.RightButton or
            (e.button() == QtCore.Qt.MouseButton.LeftButton and
             (e.modifiers() & QtCore.Qt.KeyboardModifier.AltModifier))):
            idx = self._hit_test(e.position().toPoint())
            if idx != -1:
                self._start_external_drag(idx)
                return

        if e.button() != QtCore.Qt.MouseButton.LeftButton: return
        idx = self._hit_test(e.position().toPoint())
        if idx == -1:
            return
        self._active_index = idx
        r = self._event_rects.get(idx)
        if not r:
            return
        self._active_block = self._events[idx]
        if r.bottom() - 6 <= e.position().y() <= r.bottom() + 6:
            self._drag_mode = 'resize'
        else:
            self._drag_mode = 'move'
            self._drag_offset_px = int(e.position().y() - r.top())
        self.setCursor(QtCore.Qt.CursorShape.ClosedHandCursor)

    def _start_external_drag(self, idx: int):
        evb = self._events[idx]
        mime = QtCore.QMimeData()
        mime.setData('application/x-task-id', str(evb.task_id).encode('utf-8'))
        mime.setData('application/x-task-title', evb.title.encode('utf-8'))
        mime.setData('application/x-task-meta', evb.meta.encode('utf-8'))
        mime.setData('application/x-task-due', evb.due.encode('utf-8'))
        drag = QtGui.QDrag(self)
        drag.setMimeData(mime)
        result = drag.exec(QtCore.Qt.DropAction.MoveAction)
        if result == QtCore.Qt.DropAction.MoveAction:
            self._events.pop(idx)
            self.update()

    def mouseMoveEvent(self, e: QtGui.QMouseEvent):
        pos = e.position().toPoint()
        idx = self._hit_test(pos)
        if self._drag_mode is None:
            if idx != -1:
                r = self._event_rects.get(idx)
                if r and r.bottom()-6 <= pos.y() <= r.bottom()+6:
                    self.setCursor(QtCore.Qt.CursorShape.SizeVerCursor)
                else:
                    self.setCursor(QtCore.Qt.CursorShape.ArrowCursor)
            else:
                self.setCursor(QtCore.Qt.CursorShape.ArrowCursor)
            return

        evb = self._active_block
        if not evb:
            return
        if self._drag_mode == 'resize':
            hour, minute = self._time_for_y(pos.y())
            tz = getattr(evb.end, 'tzinfo', None)
            new_end = datetime(evb.end.year, evb.end.month, evb.end.day, hour, minute, tzinfo=tz)
            if new_end <= evb.start:
                new_end = evb.start + timedelta(minutes=self._snap_minutes)
            evb.end = new_end
        elif self._drag_mode == 'move':
            target_y = pos.y() - self._drag_offset_px
            hour, minute = self._time_for_y(target_y)
            start_minutes = hour * 60 + minute
            start_minutes = max(0, min(24*60 - self._snap_minutes, start_minutes))
            dur = int((evb.end - evb.start).total_seconds() // 60)
            tz = getattr(evb.start, 'tzinfo', None)
            new_start = datetime(evb.start.year, evb.start.month, evb.start.day, start_minutes//60, start_minutes%60, tzinfo=tz)
            evb.start = new_start
            evb.end = new_start + timedelta(minutes=dur)
        self.update()

    def mouseReleaseEvent(self, e: QtGui.QMouseEvent):
        if self._drag_mode == 'move' and self._active_block is not None:
            try:
                self.blockMoved.emit(self._active_block)
            except Exception:
                pass
        elif self._drag_mode == 'resize' and self._active_block is not None:
            try:
                self.blockResized.emit(self._active_block)
            except Exception:
                pass
        self._drag_mode = None
        self._active_index = -1
        self._active_block = None
        self._drag_offset_px = 0
        self.setCursor(QtCore.Qt.CursorShape.ArrowCursor)

    def _hit_test(self, pt: QtCore.QPoint) -> int:
        for idx in reversed(self._z_order):
            r = self._event_rects.get(idx)
            if r and r.contains(pt):
                return idx
        return -1

    def paintEvent(self, e):
        p = QtGui.QPainter(self)
        p.fillRect(self.rect(), QtGui.QColor(COLOR_PRIMARY_BG))
        header = QtCore.QRect(0, 0, self.width(), self._header_h)
        p.fillRect(header, QtGui.QColor(COLOR_SECONDARY_BG))
        p.setPen(QtGui.QPen(QtGui.QColor(COLOR_TEXT_MUTED)))
        p.drawText(
            header.adjusted(8, 0, -8, 0),
            QtCore.Qt.AlignmentFlag.AlignVCenter | QtCore.Qt.AlignmentFlag.AlignLeft,
            self._anchor_date.toString("ddd dd MMM"),
        )

        for h in range(25):
            y = self._header_h + h * self._hour_h
            p.setPen(QtGui.QPen(QtGui.QColor('#303030')))
            p.drawLine(self._left_timebar, y, self.width(), y)
            if h < 24:
                p.setPen(QtGui.QPen(QtGui.QColor(COLOR_TEXT_MUTED)))
                p.drawText(6, y + 14, f"{h:02d}:00")
        p.setPen(QtGui.QPen(QtGui.QColor('#3a3a3a')))
        p.drawLine(self._left_timebar, 0, self._left_timebar, self.height())

        events = self._layout_columns(self._events)
        self._event_rects.clear()
        self._z_order = []
        for ev in events:
            idx = self._events.index(ev)
            base_r = self._rect_for_event(ev)
            col_w = base_r.width() / max(1, ev._colcount)
            r = QtCore.QRectF(base_r.x() + ev._col * col_w, base_r.y(), col_w - 3, base_r.height())
            self._event_rects[idx] = QtCore.QRect(int(r.x()), int(r.y()), int(r.width()), int(r.height()))
            self._z_order.append(idx)
            fill = QtGui.QColor(
                COLOR_PRIMARY_BG if ev._colcount > 1 else COLOR_SECONDARY_BG
            )
            if (ev.end - ev.start).total_seconds() <= _SMALL_BLOCK_MIN * 60:
                fill = QtGui.QColor(fill).lighter(150)
            p.setPen(QtGui.QPen(QtGui.QColor(COLOR_ACCENT)))
            p.setBrush(QtGui.QBrush(fill))
            p.drawRoundedRect(r.adjusted(0.5, 0.5, -0.5, -0.5), _ROUNDED_RADIUS, _ROUNDED_RADIUS)
            fm = p.fontMetrics()
            text_x = r.x() + 6
            text_y = r.y() + fm.ascent() + 2
            p.setPen(QtGui.QPen(QtGui.QColor(COLOR_TEXT)))
            p.drawText(int(text_x), int(text_y), ev.title)
            if ev.meta:
                text_y += fm.height()
                p.setPen(QtGui.QPen(QtGui.QColor(COLOR_TEXT_MUTED)))
                p.drawText(int(text_x), int(text_y), ev.meta)
