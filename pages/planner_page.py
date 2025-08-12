from __future__ import annotations
from PyQt6 import QtCore, QtGui, QtWidgets
from widgets.layout.left_panel import LeftPanel
from widgets.calendar.week_view_editable import CalendarWeekView, EventBlock
from widgets.calendar.day_view import CalendarDayView
from kanban.board_lanes import KanbanBoard
from widgets.layout.navigator import NavIconButton
from utils.icons import make_icon_pm_pair
from theme.colors import (
    COLOR_PRIMARY_BG,
    COLOR_SECONDARY_BG,
    COLOR_TEXT_MUTED,
    COLOR_ACCENT,
)
from services.sync_orchestrator import SyncOrchestrator

# Diyalog (tek ekran – task/event)
try:
    from widgets.dialogs.event_task_dialog import EventTaskDialog, ItemModel
except Exception:
    EventTaskDialog = None
    ItemModel = None


def _to_iso_qdate(qd: QtCore.QDate) -> str:
    return QtCore.QDateTime(qd, QtCore.QTime(0, 0)).toString(QtCore.Qt.DateFormat.ISODate)

def _to_iso_dt(qd: QtCore.QDate, qt: QtCore.QTime) -> str:
    return QtCore.QDateTime(qd, qt).toString(QtCore.Qt.DateFormat.ISODate)

def _next_round_hour(now: QtCore.QTime | None = None) -> tuple[QtCore.QTime, QtCore.QTime]:
    t = now or QtCore.QTime.currentTime()
    if t.minute() == 0 and t.second() == 0:
        start = QtCore.QTime(t.hour(), 0)
    else:
        start = QtCore.QTime(t.hour(), 0).addSecs(3600)
    end = start.addSecs(3600)
    if end <= start:
        end = QtCore.QTime(23, 59, 0)
    return start, end


class PlannerPage(QtWidgets.QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._anchor_date = QtCore.QDate.currentDate()
        self._view_mode = "weekly"
        self._build_ui()
        self._wire_sync()

    # ---------------- UI ----------------
    def _build_ui(self):
        root = QtWidgets.QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # ---- HEADER (3 kolonun üstünde) ----
        header_w = QtWidgets.QWidget()
        header = QtWidgets.QHBoxLayout(header_w)
        header.setContentsMargins(12, 12, 12, 8)
        header.setSpacing(8)
        title = QtWidgets.QLabel("Planner")
        font = title.font()
        font.setPointSize(20); font.setWeight(600); title.setFont(font)
        header.addWidget(title)
        header.addStretch(1)
        pm_n, pm_a = make_icon_pm_pair(
            self.style().standardIcon(QtWidgets.QStyle.StandardPixmap.SP_BrowserReload),
            size=24,
            normal_color=COLOR_TEXT_MUTED,
            active_color=COLOR_ACCENT,
        )
        self.btn_refresh = NavIconButton(pm_n, pm_a, row_width=40, box_w=32, box_h=32, tooltip="Refresh")
        self.btn_refresh.clicked.connect(self._on_refresh_clicked)
        header.addWidget(self.btn_refresh)
        root.addWidget(header_w)

        # ---- 3 KOLON ----
        central = QtWidgets.QWidget()
        h = QtWidgets.QHBoxLayout(central)
        h.setContentsMargins(0, 0, 0, 0)
        h.setSpacing(0)

        # Sol panel
        self.left = LeftPanel()
        self.left.viewChanged.connect(self.on_view_changed)
        self.left.tagsChanged.connect(self.on_tags_changed)
        self.left.dateSelected.connect(self.on_anchor_date_changed)
        h.addWidget(self.left)

        # Orta panel: Takvim
        content = QtWidgets.QWidget()
        content.setStyleSheet(f"background:{COLOR_PRIMARY_BG};")
        content_l = QtWidgets.QVBoxLayout(content)
        content_l.setContentsMargins(12, 12, 12, 12)
        content_l.setSpacing(8)

        class VScrollArea(QtWidgets.QScrollArea):
            def __init__(self, *a, **k):
                super().__init__(*a, **k)
                self.setWidgetResizable(False)
                self.setFrameShape(QtWidgets.QFrame.Shape.NoFrame)
                self.setVerticalScrollBarPolicy(QtCore.Qt.ScrollBarPolicy.ScrollBarAsNeeded)
                self.setHorizontalScrollBarPolicy(QtCore.Qt.ScrollBarPolicy.ScrollBarAsNeeded)
                self.setStyleSheet(
                    f"""
                    QScrollBar:vertical {{
                        background: {COLOR_SECONDARY_BG};
                        width: 10px; margin: 0; border: 0; }}
                    QScrollBar::handle:vertical {{
                        background: #555; min-height: 36px; border-radius: 5px; }}
                    QScrollBar:horizontal {{
                        background: {COLOR_SECONDARY_BG};
                        height: 10px; margin: 0; border: 0; }}
                    QScrollBar::handle:horizontal {{
                        background: #555; min-width: 36px; border-radius: 5px; }}
                    QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical,
                    QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{ height: 0; width: 0; }}
                    QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical,
                    QScrollBar::add-page:horizontal, QScrollBar::sub-page:horizontal {{ background: transparent; }}
                    """
                )

        self.week = CalendarWeekView(); self.week.setFixedHeight(self.week.sizeHint().height())
        self.day  = CalendarDayView();  self.day.setFixedHeight(self.day.sizeHint().height())

        self.week_scroll = VScrollArea(); self.week_scroll.setWidget(self.week)
        self.day_scroll  = VScrollArea(); self.day_scroll.setWidget(self.day)

        self.stacked = QtWidgets.QStackedWidget()
        self.stacked.addWidget(self.week_scroll)  # 0
        self.stacked.addWidget(self.day_scroll)   # 1
        content_l.addWidget(self.stacked)
        h.addWidget(content, 1)

        # Sağ panel: Kanban
        self.kanban = KanbanBoard()
        right = QtWidgets.QWidget(); right.setFixedWidth(360)
        r_l = QtWidgets.QVBoxLayout(right); r_l.setContentsMargins(12, 12, 12, 12); r_l.setSpacing(8)
        r_l.addWidget(self.kanban)
        h.addWidget(right)

        root.addWidget(central, 1)

        # Başlangıç
        if hasattr(self.week, "setAnchorDate"):
            self.week.setAnchorDate(self._anchor_date)
        self.stacked.setCurrentIndex(0)

        # Event sinyalleri (varsa)
        if hasattr(self.week, "blockCreated"):   self.week.blockCreated.connect(self._on_block_created)
        if hasattr(self.week, "blockMoved"):     self.week.blockMoved.connect(self._on_block_moved)
        if hasattr(self.week, "blockResized"):   self.week.blockResized.connect(self._on_block_resized)
        if hasattr(self.week, "blockActivated"): self.week.blockActivated.connect(self._open_event_dialog_from_block)
        if hasattr(self.day,  "blockActivated"): self.day.blockActivated.connect(self._open_event_dialog_from_block)

        # Kanban “kart çift tık” sinyali varsa bağla (opsiyonel)
        if hasattr(self.kanban, "taskActivated"):
            self.kanban.taskActivated.connect(self._open_task_dialog_by_id)
        if hasattr(self.kanban, "itemDoubleClicked"):
            self.kanban.itemDoubleClicked.connect(self._open_task_dialog_by_id)

        # 🔶 Boş alana çift tık için eventFilter
        self.week.installEventFilter(self)
        self.kanban.installEventFilter(self)

    # ---------------- Store ----------------
    def _wire_sync(self):
        self.store = SyncOrchestrator(self)
        self.store.tasksUpdated.connect(self._apply_tasks)
        self.store.eventsUpdated.connect(self._apply_events)
        self.store.tagsUpdated.connect(self._apply_tags)
        if hasattr(self.left, "attachStore"):
            self.left.attachStore(self.store)
        self.store.bootstrap()
        if hasattr(self.kanban, "statusChanged"):
            self.kanban.statusChanged.connect(self.store.set_task_status)

    def _on_refresh_clicked(self):
        self.store.refresh()

    # ---------------- Event Filter: double-click ----------------
    def eventFilter(self, obj: QtCore.QObject, ev: QtCore.QEvent) -> bool:
        if ev.type() == QtCore.QEvent.Type.MouseButtonDblClick:
            me: QtGui.QMouseEvent = ev  # type: ignore
            # WEEK VIEW: yalnız boş alanda yakala (event'e gelirse bırak, week view kendisi açsın)
            if obj is self.week:
                # WeekView'e public eventAtPos ekledik; yoksa private _hit_test'i deneriz
                hit = None
                if hasattr(self.week, "eventAtPos"):
                    hit = self.week.eventAtPos(me.position().toPoint())
                elif hasattr(self.week, "_hit_test"):
                    idx = self.week._hit_test(me.position().toPoint())  # type: ignore
                    hit = None if idx == -1 else True
                if hit:
                    # Dolu – event bloğu: bırak, widget kendi blockActivated ile açsın
                    return False
                # Boş – yeni görev
                date = self._anchor_date
                start, end = _next_round_hour()
                self._open_new_task_dialog(date, start, end, default_has_time=False)
                return True

            # KANBAN: mümkünse kartı bul → düzenleme; bulunamazsa boş/kapsam dışı → yeni görev
            if obj is self.kanban:
                task_id = None
                w = self.kanban.childAt(me.position().toPoint())
                while w is not None:
                    # Birçok Qt widget'ında dynamicProperty kullanılabilir
                    if w.property("task_id") is not None:
                        try:
                            task_id = int(w.property("task_id"))
                            break
                        except Exception:
                            pass
                    if hasattr(w, "task_id"):
                        try:
                            task_id = int(getattr(w, "task_id"))
                            break
                        except Exception:
                            pass
                    w = w.parentWidget()
                if task_id is not None:
                    self._open_task_dialog_by_id(task_id)
                    return True
                # Kart bulunamadı → yeni görev
                date = self._anchor_date
                start, end = _next_round_hour()
                self._open_new_task_dialog(date, start, end, default_has_time=False)
                return True

        return super().eventFilter(obj, ev)

    # ---------------- Diyalog Aç/Kaydet/Sil ----------------
    def _open_new_task_dialog(self, date: QtCore.QDate, start: QtCore.QTime, end: QtCore.QTime, default_has_time: bool):
        if not EventTaskDialog:
            return
        m = ItemModel(kind="task", id=None, title="", notes="")
        m.date = date
        # Varsayılan: görev (saat kapalı)
        if default_has_time:
            m.start = start; m.end = end
        else:
            m.start = None;  m.end = None
        dlg = EventTaskDialog(m, self)
        dlg.saved.connect(self._on_dialog_saved)
        dlg.deleted.connect(self._on_dialog_deleted)
        dlg.exec()

    def _open_task_dialog_by_id(self, task_id: int):
        if not EventTaskDialog:
            return
        # Lokalden oku
        try:
            from services.local_db import LocalDB
            db = getattr(self, "_debug_db_singleton", None) or LocalDB()
            self._debug_db_singleton = db
            t = db.get_task_by_id(int(task_id))
        except Exception:
            t = None
        m = ItemModel(kind="task", id=int(task_id), title=(t or {}).get("title", ""), notes=(t or {}).get("notes", ""))
        # Görev – saat kapalı başlat
        m.date = self._anchor_date
        m.start = None; m.end = None
        dlg = EventTaskDialog(m, self)
        dlg.saved.connect(self._on_dialog_saved)
        dlg.deleted.connect(self._on_dialog_deleted)
        dlg.exec()

    def _open_event_dialog_from_block(self, evb: EventBlock):
        if not EventTaskDialog:
            return
        m = ItemModel(kind="event", id=getattr(evb, "id", None), title=getattr(evb, "title", ""), notes=getattr(evb, "notes", ""))
        d = QtCore.QDate(evb.start.year, evb.start.month, evb.start.day)
        m.date = d
        m.start = QtCore.QTime(evb.start.hour, evb.start.minute)
        m.end   = QtCore.QTime(evb.end.hour, evb.end.minute)
        m.task_id = getattr(evb, "task_id", None)
        m.rrule   = getattr(evb, "rrule", None)
        dlg = EventTaskDialog(m, self)
        dlg.saved.connect(self._on_dialog_saved)
        dlg.deleted.connect(self._on_dialog_deleted)
        dlg.exec()

    def _on_dialog_saved(self, model):
        # --- EVENT mantığı ---
        if model.kind == "event":
            if model.start and model.end:
                start_iso = _to_iso_dt(model.date, model.start)
                end_iso   = _to_iso_dt(model.date, model.end)
                if model.id:  # güncelle
                    self.store.update_event(int(model.id), start_iso, end_iso, title=model.title, notes=model.notes, rrule=model.rrule)
                else:         # yeni event
                    tid = int(model.task_id) if model.task_id else self.store.upsert_task(None, model.title or "Untitled", model.notes or "", _to_iso_qdate(model.date), has_time=False)
                    self.store.create_event(tid, start_iso, end_iso, title=model.title, notes=model.notes, rrule=model.rrule)
            else:
                # saat kaldırıldı → event sil
                if model.id:
                    try: self.store.delete_event(int(model.id))
                    except Exception: pass
            return

        # --- TASK mantığı ---
        if model.kind == "task":
            # 1) her koşulda task'ı upsert et (title/notes/due_date)
            tid = int(model.id) if model.id else self.store.upsert_task(None, model.title or "Untitled", model.notes or "", _to_iso_qdate(model.date), has_time=False)
            if not model.id:
                model.id = tid
            # 2) eğer kullanıcı saat işaretlediyse → event yarat
            if model.start and model.end:
                start_iso = _to_iso_dt(model.date, model.start)
                end_iso   = _to_iso_dt(model.date, model.end)
                self.store.create_event(int(model.id), start_iso, end_iso, title=model.title, notes=model.notes, rrule=model.rrule)

    def _on_dialog_deleted(self, model):
        if model.kind == "event" and model.id:
            self.store.delete_event(int(model.id))
        elif model.kind == "task" and model.id:
            self.store.delete_task(int(model.id))

    # ---------------- Apply data to UI ----------------
    def _apply_tasks(self, tasks: list[dict]):
        # has_time=1 olanları gizle
        filtered = [t for t in tasks if not bool(t.get("has_time", 0))]
        if hasattr(self.kanban, "set_tasks"):
            self.kanban.set_tasks(filtered)

    def _apply_events(self, events: list[dict]):
        if hasattr(self.week, "setEvents"):
            try: self.week.setEvents(events)
            except Exception: pass
        if hasattr(self.day, "setEvents"):
            try: self.day.setEvents(events)
            except Exception: pass

    def _apply_tags(self, tags: list[dict]):
        items = []
        for t in tags:
            try:
                items.append((int(t["id"]), t["name"]))
            except Exception:
                pass
        if hasattr(self.left, "applyServerTags"): self.left.applyServerTags(items)
        elif hasattr(self.left, "applyTags"):     self.left.applyTags(items)

    # ---------------- Sol panel slotları ----------------
    def on_view_changed(self, mode: str):
        self._view_mode = mode
        self.stacked.setCurrentIndex(0 if mode == "weekly" else 1)

    def on_tags_changed(self, s: set):
        pass

    def on_anchor_date_changed(self, qdate: QtCore.QDate):
        self._anchor_date = qdate
        if hasattr(self.week, "setAnchorDate"): self.week.setAnchorDate(qdate)

    # ---------------- Week view block hareketi ----------------
    def _on_block_created(self, ev: EventBlock):
        start_iso = QtCore.QDateTime(QtCore.QDate(ev.start.year, ev.start.month, ev.start.day),
                                     QtCore.QTime(ev.start.hour, ev.start.minute)).toString(QtCore.Qt.DateFormat.ISODate)
        end_iso   = QtCore.QDateTime(QtCore.QDate(ev.end.year, ev.end.month, ev.end.day),
                                     QtCore.QTime(ev.end.hour, ev.end.minute)).toString(QtCore.Qt.DateFormat.ISODate)
        task_id   = int(getattr(ev, "task_id", 0) or 0)
        if task_id and start_iso and end_iso:
            self.store.create_event(task_id, start_iso, end_iso)

    def _on_block_moved(self, ev: EventBlock):
        if getattr(ev, "id", None):
            start_iso = QtCore.QDateTime(QtCore.QDate(ev.start.year, ev.start.month, ev.start.day),
                                         QtCore.QTime(ev.start.hour, ev.start.minute)).toString(QtCore.Qt.DateFormat.ISODate)
            end_iso   = QtCore.QDateTime(QtCore.QDate(ev.end.year, ev.end.month, ev.end.day),
                                         QtCore.QTime(ev.end.hour, ev.end.minute)).toString(QtCore.Qt.DateFormat.ISODate)
            if start_iso and end_iso:
                self.store.update_event(int(ev.id), start_iso, end_iso)

    def _on_block_resized(self, ev: EventBlock):
        self._on_block_moved(ev)
