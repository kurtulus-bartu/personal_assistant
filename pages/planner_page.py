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
    COLOR_TEXT,
    COLOR_TEXT_MUTED,
    COLOR_ACCENT,
)
from services.sync_orchestrator import SyncOrchestrator
from widgets.core.selectors import ProjectButtonRow

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
        self._current_tag: int | None = None
        self._current_project: int | None = None
        self._all_tasks: list[dict] = []
        self._all_projects: list[dict] = []
        self._all_tags: list[dict] = []
        self._all_events: list[dict] = []
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
            """ScrollArea that keeps week view scalable until a min column width."""

            def __init__(self, *a, min_day_w: int = 160, **k):
                super().__init__(*a, **k)
                self.setWidgetResizable(False)
                self.setFrameShape(QtWidgets.QFrame.Shape.NoFrame)
                self.setVerticalScrollBarPolicy(QtCore.Qt.ScrollBarPolicy.ScrollBarAsNeeded)
                self.setHorizontalScrollBarPolicy(QtCore.Qt.ScrollBarPolicy.ScrollBarAsNeeded)
                self._min_day_w = min_day_w
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

            def resizeEvent(self, ev: QtGui.QResizeEvent):
                super().resizeEvent(ev)
                w = self.viewport().width()
                widget = self.widget()
                if widget is None:
                    return
                # Minimum width: left timebar + 7 * min_day_w if available
                min_w = self._min_day_w * 7
                if hasattr(widget, "_left_timebar"):
                    min_w += getattr(widget, "_left_timebar", 0)
                target_w = max(w, min_w)
                widget.setFixedWidth(int(target_w))

        self.week = CalendarWeekView(); self.week.setFixedHeight(self.week.sizeHint().height())
        self.day  = CalendarDayView();  self.day.setFixedHeight(self.day.sizeHint().height())

        self.week_scroll = VScrollArea(min_day_w=120); self.week_scroll.setWidget(self.week)
        self.day_scroll  = VScrollArea(); self.day_scroll.setWidget(self.day)

        self.stacked = QtWidgets.QStackedWidget()
        self.stacked.addWidget(self.week_scroll)  # 0
        self.stacked.addWidget(self.day_scroll)   # 1
        content_l.addWidget(self.stacked)
        h.addWidget(content, 1)

        # Sağ panel: Kanban + Proje butonları
        self.kanban = KanbanBoard()
        right = QtWidgets.QWidget(); right.setFixedWidth(360)
        r_l = QtWidgets.QVBoxLayout(right); r_l.setContentsMargins(12, 12, 12, 12); r_l.setSpacing(8)
        self.project_bar = ProjectButtonRow()
        self.project_bar.changed.connect(self.on_project_changed)
        r_l.addWidget(self.project_bar)
        r_l.addWidget(self.kanban, 1)

        proj_row = QtWidgets.QHBoxLayout(); proj_row.setSpacing(8)
        self.btn_add_project = QtWidgets.QPushButton("+ New Project")
        self.btn_add_project.setFixedHeight(36)
        self.btn_add_project.setStyleSheet(
            f"background:{COLOR_SECONDARY_BG}; color:{COLOR_TEXT}; border:1px solid #3a3a3a; border-radius:10px;"
        )
        self.btn_add_project.clicked.connect(self._on_add_project_clicked)
        proj_row.addWidget(self.btn_add_project)

        self.btn_delete_project = QtWidgets.QPushButton("Delete Project")
        self.btn_delete_project.setFixedHeight(36)
        self.btn_delete_project.setStyleSheet(
            f"background:{COLOR_SECONDARY_BG}; color:{COLOR_TEXT}; border:1px solid #3a3a3a; border-radius:10px;"
        )
        self.btn_delete_project.clicked.connect(self._on_delete_project_clicked)
        proj_row.addWidget(self.btn_delete_project)
        r_l.addLayout(proj_row)
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
        self.store.projectsUpdated.connect(self._apply_projects)
        if hasattr(self.left, "attachStore"):
            self.left.attachStore(self.store)
        self.store.bootstrap()
        if hasattr(self.kanban, "statusChanged"):
            self.kanban.statusChanged.connect(self.store.set_task_status)
        if hasattr(self.kanban, "taskReparented"):
            self.kanban.taskReparented.connect(self.store.set_task_parent)

    def _on_refresh_clicked(self):
        self.store.refresh()

    def _on_add_project_clicked(self):
        name, ok = QtWidgets.QInputDialog.getText(self, "Add Project", "Project name:")
        if ok and name.strip():
            self.store.add_project(name.strip())

    def _on_delete_project_clicked(self):
        if self._current_project is None:
            return
        pid = int(self._current_project)
        self.store.delete_project(pid)
        self._current_project = None
        self._filter_tasks_and_update()
        self._filter_events_and_update()

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
        opts = []
        try:
            db = getattr(self.store, "db", None)
            tasks = db.get_tasks() if db else []
            opts = [(int(t["id"]), t.get("title", "")) for t in tasks]
        except Exception:
            pass
        tag_opts = [(int(t["id"]), t.get("name", "")) for t in self._all_tags]
        proj_opts = [(int(p["id"]), p.get("name", "")) for p in self._all_projects]
        if self._current_tag is not None:
            m.tag_id = int(self._current_tag)
        if self._current_project is not None:
            m.project_id = int(self._current_project)
        dlg = EventTaskDialog(m, self, parent_options=opts, tag_options=tag_opts, project_options=proj_opts)
        dlg.saved.connect(self._on_dialog_saved)
        dlg.deleted.connect(self._on_dialog_deleted)
        dlg.exec()

    def _open_task_dialog_by_id(self, task_id: int):
        if not EventTaskDialog:
            return
        # Lokalden oku (store'un DB'si güncel; ayrı bağlantı kullanma)
        try:
            db = getattr(self.store, "db", None)
            t = db.get_task_by_id(int(task_id)) if db else None
        except Exception:
            t = None
        m = ItemModel(kind="task", id=int(task_id), title=(t or {}).get("title", ""), notes=(t or {}).get("notes", ""))
        # Görev – saat kapalı başlat
        m.date = self._anchor_date
        m.start = None; m.end = None
        m.parent_id = (t or {}).get("parent_id")
        m.tag_id = (t or {}).get("tag_id")
        m.project_id = (t or {}).get("project_id")
        opts = []
        try:
            tasks = db.get_tasks() if db else []
            opts = [(int(x["id"]), x.get("title", "")) for x in tasks if int(x["id"]) != int(task_id)]
        except Exception:
            pass
        tag_opts = [(int(tg["id"]), tg.get("name", "")) for tg in self._all_tags]
        proj_opts = [(int(p["id"]), p.get("name", "")) for p in self._all_projects]
        dlg = EventTaskDialog(m, self, parent_options=opts, tag_options=tag_opts, project_options=proj_opts)
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
        m.rrule   = getattr(evb, "rrule", None)
        tag_opts = [(int(tg["id"]), tg.get("name", "")) for tg in self._all_tags]
        proj_opts = [(int(p["id"]), p.get("name", "")) for p in self._all_projects]
        dlg = EventTaskDialog(m, self, tag_options=tag_opts, project_options=proj_opts)
        dlg.saved.connect(self._on_dialog_saved)
        dlg.deleted.connect(self._on_dialog_deleted)
        dlg.exec()

    def _on_dialog_saved(self, model):
        start_iso = _to_iso_dt(model.date, model.start) if model.start and model.end else None
        end_iso   = _to_iso_dt(model.date, model.end) if model.start and model.end else None
        due_iso   = _to_iso_qdate(model.date)
        tid = self.store.upsert_task(model.id, model.title or "Untitled", model.notes or "", due_iso,
                                    start_iso=start_iso, end_iso=end_iso, parent_id=model.parent_id,
                                    tag_id=model.tag_id, project_id=model.project_id)
        if not model.id:
            model.id = tid

    def _on_dialog_deleted(self, model):
        if model.id:
            self.store.delete_task(int(model.id))

    # ---------------- Apply data to UI ----------------
    def _apply_tasks(self, tasks: list[dict]):
        self._all_tasks = tasks or []
        self._update_project_buttons()
        self._filter_tasks_and_update()

    def _apply_events(self, events: list[dict]):
        self._all_events = events or []
        self._filter_events_and_update()

    def _apply_tags(self, tags: list[dict]):
        self._all_tags = tags or []
        items = []
        for t in tags:
            try:
                items.append((int(t["id"]), t["name"]))
            except Exception:
                pass
        if hasattr(self.left, "applyServerTags"): self.left.applyServerTags(items)
        elif hasattr(self.left, "applyTags"):     self.left.applyTags(items)

    def _apply_projects(self, projects: list[dict]):
        self._all_projects = projects or []
        self._update_project_buttons()

    def _update_project_buttons(self):
        items: list[tuple[int, str]] = []
        for p in self._all_projects:
            try:
                pid = int(p.get("id"))
                items.append((pid, p.get("name", "")))
            except Exception:
                pass
        self.project_bar.setItems(items)
        ids = {pid for pid, _ in items}
        if self._current_project in ids:
            self.project_bar.setCurrentById(int(self._current_project))
        else:
            self._current_project = None

    def _filter_tasks_and_update(self):
        filtered = [t for t in self._all_tasks if not bool(t.get("has_time", 0))]
        if self._current_tag is not None:
            filtered = [t for t in filtered if int(t.get("tag_id") or 0) == int(self._current_tag)]
        if self._current_project is not None:
            filtered = [t for t in filtered if int(t.get("project_id") or 0) == int(self._current_project)]
        if hasattr(self.kanban, "set_tasks"):
            self.kanban.set_tasks(filtered)

    def _filter_events_and_update(self):
        evs = self._all_events
        if self._current_tag is not None:
            evs = [e for e in evs if int(e.get("tag_id") or 0) == int(self._current_tag)]
        if self._current_project is not None:
            evs = [e for e in evs if int(e.get("project_id") or 0) == int(self._current_project)]
        if hasattr(self.week, "setEvents"):
            try: self.week.setEvents(evs)
            except Exception: pass
        if hasattr(self.day, "setEvents"):
            try: self.day.setEvents(evs)
            except Exception: pass

    # ---------------- Sol panel slotları ----------------
    def on_view_changed(self, mode: str):
        self._view_mode = mode
        self.stacked.setCurrentIndex(0 if mode == "weekly" else 1)

    def on_tags_changed(self, s: set):
        self._current_tag = next(iter(s)) if s else None
        self._current_project = None
        self._update_project_buttons()
        self._filter_tasks_and_update()
        self._filter_events_and_update()

    def on_project_changed(self, project_id: int):
        self._current_project = project_id or None
        self._filter_tasks_and_update()
        self._filter_events_and_update()

    def on_anchor_date_changed(self, qdate: QtCore.QDate):
        self._anchor_date = qdate
        if hasattr(self.week, "setAnchorDate"): self.week.setAnchorDate(qdate)

    # ---------------- Week view block hareketi ----------------
    def _on_block_created(self, ev: EventBlock):
        start_iso = QtCore.QDateTime(QtCore.QDate(ev.start.year, ev.start.month, ev.start.day),
                                     QtCore.QTime(ev.start.hour, ev.start.minute)).toString(QtCore.Qt.DateFormat.ISODate)
        end_iso   = QtCore.QDateTime(QtCore.QDate(ev.end.year, ev.end.month, ev.end.day),
                                     QtCore.QTime(ev.end.hour, ev.end.minute)).toString(QtCore.Qt.DateFormat.ISODate)
        task_id   = int(getattr(ev, "task_id", 0) or getattr(ev, "id", 0) or 0)
        if task_id and start_iso and end_iso:
            self.store.set_task_times(task_id, start_iso, end_iso)

    def _on_block_moved(self, ev: EventBlock):
        tid = int(getattr(ev, "id", 0) or getattr(ev, "task_id", 0) or 0)
        if tid:
            start_iso = QtCore.QDateTime(QtCore.QDate(ev.start.year, ev.start.month, ev.start.day),
                                         QtCore.QTime(ev.start.hour, ev.start.minute)).toString(QtCore.Qt.DateFormat.ISODate)
            end_iso   = QtCore.QDateTime(QtCore.QDate(ev.end.year, ev.end.month, ev.end.day),
                                         QtCore.QTime(ev.end.hour, ev.end.minute)).toString(QtCore.Qt.DateFormat.ISODate)
            if start_iso and end_iso:
                self.store.set_task_times(tid, start_iso, end_iso)

    def _on_block_resized(self, ev: EventBlock):
        self._on_block_moved(ev)
