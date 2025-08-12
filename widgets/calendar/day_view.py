from __future__ import annotations
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import List, Dict, Tuple
from PyQt6 import QtCore, QtGui, QtWidgets
from PyQt6.QtCore import QDate
from theme.colors import COLOR_PRIMARY_BG, COLOR_SECONDARY_BG, COLOR_TEXT, COLOR_TEXT_MUTED, COLOR_ACCENT

@dataclass
class EventBlock:
    task_id: int
    start: datetime
    end: datetime
    title: str = ""

class CalendarDayView(QtWidgets.QWidget):
    blockCreated = QtCore.pyqtSignal(object)
    blockMoved   = QtCore.pyqtSignal(object)
    blockResized = QtCore.pyqtSignal(object)
    conflict     = QtCore.pyqtSignal(object)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._date = QDate.currentDate()
        self._header_h = 28
        self._hour_h = 48
        self._left_timebar = 56
        self._snap_minutes = 15
        self._events: List[EventBlock] = []
        self._event_rects: Dict[int, QtCore.QRect] = {}
        self._z_order: List[int] = []
        self._drag_mode = None
        self._active_index = -1
        self._drag_offset_minutes = 0
        self.setMouseTracking(True)
        self.setAcceptDrops(True)

    def sizeHint(self):
        return QtCore.QSize(800, self._header_h + 24 * self._hour_h)

    def setDate(self, date: QDate):
        self._date = date
        self.update()

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
        start_dt = datetime(self._date.year(), self._date.month(), self._date.day(), hour, minute)
        end_dt = start_dt + timedelta(minutes=60)
        ev = EventBlock(task_id=task_id, start=start_dt, end=end_dt, title=f"Task #{task_id}")
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
        if idx == -1: return
        self._active_index = idx
        r = self._event_rects.get(idx)
        if not r: return
        if r.bottom()-6 <= e.position().y() <= r.bottom()+6:
            self._drag_mode = 'resize'
        else:
            self._drag_mode = 'move'
            evb = self._events[idx]
            hour, minute = self._time_for_y(e.position().y())
            click_minutes = hour*60 + minute
            start_minutes = evb.start.hour*60 + evb.start.minute
            self._drag_offset_minutes = click_minutes - start_minutes
        self.setCursor(QtCore.Qt.CursorShape.ClosedHandCursor)

    def _start_external_drag(self, idx: int):
        evb = self._events[idx]
        mime = QtCore.QMimeData()
        mime.setData('application/x-task-id', str(evb.task_id).encode('utf-8'))
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

        evb = self._events[self._active_index]
        if self._drag_mode == 'resize':
            hour, minute = self._time_for_y(pos.y())
            tz = getattr(evb.end, 'tzinfo', None)
            new_end = datetime(evb.end.year, evb.end.month, evb.end.day, hour, minute, tzinfo=tz)
            if new_end <= evb.start:
                new_end = evb.start + timedelta(minutes=self._snap_minutes)
            evb.end = new_end
            self.blockResized.emit(evb)
        elif self._drag_mode == 'move':
            hour, minute = self._time_for_y(pos.y())
            target_minutes = hour * 60 + minute
            start_minutes = max(0, min(24*60 - self._snap_minutes, target_minutes - self._drag_offset_minutes))
            dur = int((evb.end - evb.start).total_seconds() // 60)
            tz = getattr(evb.start, 'tzinfo', None)
            new_start = datetime(evb.start.year, evb.start.month, evb.start.day, start_minutes//60, start_minutes%60, tzinfo=tz)
            evb.start = new_start
            evb.end = new_start + timedelta(minutes=dur)
            self.blockMoved.emit(evb)
        self.update()

    def mouseReleaseEvent(self, e: QtGui.QMouseEvent):
        self._drag_mode = None
        self._active_index = -1
        self._drag_offset_minutes = 0
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
        p.drawText(header.adjusted(8, 0, -8, 0),
                   QtCore.Qt.AlignmentFlag.AlignVCenter | QtCore.Qt.AlignmentFlag.AlignLeft,
                   self._date.toString("ddd dd MMM"))

        for h in range(25):
            y = self._header_h + h * self._hour_h
            p.setPen(QtGui.QPen(QtGui.QColor('#303030')))
            p.drawLine(self._left_timebar, y, self.width(), y)
            if h < 24:
                p.setPen(QtGui.QPen(QtGui.QColor(COLOR_TEXT_MUTED)))
                p.drawText(6, y + 14, f"{h:02d}:00")
        p.setPen(QtGui.QPen(QtGui.QColor('#3a3a3a')))
        p.drawLine(self._left_timebar, 0, self._left_timebar, self.height())

        infos = []
        self._event_rects.clear()
        for idx, evb in enumerate(self._events):
            start_y = self._header_h + int((evb.start.hour + evb.start.minute/60) * self._hour_h)
            end_y   = self._header_h + int((evb.end.hour   + evb.end.minute/60)   * self._hour_h)
            r = QtCore.QRect(self._left_timebar+4, start_y+2, self.width()-self._left_timebar-8, max(18, end_y-start_y-4))
            self._event_rects[idx] = r
            infos.append({"idx": idx, "rect": r, "height": r.height(), "is_small": False})

        n = len(infos)
        for i in range(n):
            for j in range(i+1, n):
                ri = infos[i]["rect"]; rj = infos[j]["rect"]
                if ri.intersects(rj):
                    if infos[i]["height"] < infos[j]["height"]:
                        infos[i]["is_small"] = True
                    elif infos[j]["height"] < infos[i]["height"]:
                        infos[j]["is_small"] = True

        draw_list = sorted(infos, key=lambda d: (d["is_small"], -d["height"]))
        self._z_order = [d["idx"] for d in draw_list]

        for item in draw_list:
            r = item["rect"]
            fill = QtGui.QColor(COLOR_ACCENT) if item["is_small"] else QtGui.QColor(COLOR_SECONDARY_BG)
            p.fillRect(r, fill)
            p.setPen(QtGui.QPen(QtGui.QColor("#5a5a5a")))
            p.drawRect(r)
            p.setPen(QtGui.QPen(QtGui.QColor(COLOR_TEXT)))
            title = self._events[item["idx"]].title
            p.drawText(r.adjusted(6, 2, -6, 0),
                       QtCore.Qt.AlignmentFlag.AlignTop | QtCore.Qt.AlignmentFlag.AlignLeft, title)
