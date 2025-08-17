from __future__ import annotations
from PyQt6 import QtCore, QtGui, QtWidgets
from datetime import datetime, timedelta
from itertools import islice
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
from pages.pomodoro_page import PomodoroPage

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


def _expand_rrule_simple(rrule: str, dtstart: datetime, limit: int = 50) -> list[datetime]:
    """Expand a minimal subset of RRULE strings without external deps.

    Supports ``FREQ=DAILY`` and ``FREQ=WEEKLY`` with optional ``BYDAY``,
    ``COUNT`` and ``UNTIL`` parts. The first occurrence is always ``dtstart``.
    """

    rule = rrule.upper()
    if rule.startswith("RRULE="):
        rule = rule[6:]

    parts: dict[str, str] = {}
    for part in rule.split(";"):
        if "=" in part:
            k, v = part.split("=", 1)
            parts[k] = v

    freq = parts.get("FREQ", "DAILY")
    count = int(parts.get("COUNT", "0")) if parts.get("COUNT") else None
    until = None
    if parts.get("UNTIL"):
        try:
            until = datetime.strptime(parts["UNTIL"][:8], "%Y%m%d").date()
        except Exception:
            pass
    byday = parts.get("BYDAY")

    dates: list[datetime] = []

    if freq == "DAILY":
        current = dtstart
        while True:
            if until and current.date() > until:
                break
            dates.append(current)
            if count and len(dates) >= count:
                break
            if len(dates) >= limit:
                break
            current += timedelta(days=1)

    elif freq == "WEEKLY":
        day_map = {"MO": 0, "TU": 1, "WE": 2, "TH": 3, "FR": 4, "SA": 5, "SU": 6}
        weekdays = [day_map.get(d) for d in (byday.split(",") if byday else []) if day_map.get(d) is not None]
        if not weekdays:
            weekdays = [dtstart.weekday()]
        base_date = dtstart.date()
        while True:
            for wd in sorted(set(weekdays)):
                next_date = base_date + timedelta((wd - base_date.weekday()) % 7)
                occurrence = datetime.combine(next_date, dtstart.time())
                if occurrence < dtstart:
                    continue
                if until and occurrence.date() > until:
                    return dates
                dates.append(occurrence)
                if count and len(dates) >= count:
                    return dates
                if len(dates) >= limit:
                    return dates
            base_date += timedelta(days=7)

    return dates[:limit]


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
        root.setContentsMargins(12, 12, 12, 12)
        root.setSpacing(8)

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

        # ---- SPLITTER: Sol panel + Takvim/Kanban ----
        self.left_panel_widget = LeftPanel(); self.left_panel_widget.setObjectName("Card")
        self.left_panel_widget.viewChanged.connect(self.on_view_changed)
        self.left_panel_widget.tagsChanged.connect(self.on_tags_changed)
        self.left_panel_widget.dateSelected.connect(self.on_anchor_date_changed)

        self.calendar_container = QtWidgets.QWidget(); self.calendar_container.setObjectName("Card")
        h = QtWidgets.QHBoxLayout(self.calendar_container)
        h.setContentsMargins(0, 0, 0, 0)
        h.setSpacing(0)

        # Orta panel: Takvim
        content = QtWidgets.QWidget()
        content.setStyleSheet(f"background:{COLOR_PRIMARY_BG};")
        content_l = QtWidgets.QVBoxLayout(content)
        content_l.setContentsMargins(12, 12, 12, 12)
        content_l.setSpacing(8)

        class VScrollArea(QtWidgets.QScrollArea):
            """ScrollArea that keeps calendar views within a min column width."""

            def __init__(self, *a, min_day_w: int = 160, days: int = 7, **k):
                super().__init__(*a, **k)
                self.setWidgetResizable(False)
                self.setFrameShape(QtWidgets.QFrame.Shape.NoFrame)
                self.setVerticalScrollBarPolicy(QtCore.Qt.ScrollBarPolicy.ScrollBarAsNeeded)
                self.setHorizontalScrollBarPolicy(QtCore.Qt.ScrollBarPolicy.ScrollBarAsNeeded)
                self._min_day_w = min_day_w
                self._days = days
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
                min_w = self._min_day_w * self._days
                if hasattr(widget, "_left_timebar"):
                    min_w += getattr(widget, "_left_timebar", 0)
                target_w = max(w, min_w)
                widget.setFixedWidth(int(target_w))

        self.week = CalendarWeekView(); self.week.setFixedHeight(self.week.sizeHint().height())
        self.day  = CalendarDayView();  self.day.setFixedHeight(self.day.sizeHint().height())
        if hasattr(self.week, "daySelected"):
            self.week.daySelected.connect(self._on_week_day_selected)

        self.week_scroll = VScrollArea(min_day_w=120, days=7); self.week_scroll.setWidget(self.week)
        self.day_scroll  = VScrollArea(min_day_w=120, days=1); self.day_scroll.setWidget(self.day)

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
        self.kanban.newTaskRequested.connect(lambda: self._open_new_task_dialog(self._anchor_date, QtCore.QTime(0,0), QtCore.QTime(0,0), False))

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

        main_row = QtWidgets.QHBoxLayout()
        main_row.setContentsMargins(0, 0, 0, 0)
        main_row.setSpacing(8)
        main_row.addWidget(self.left_panel_widget)
        main_row.addWidget(self.calendar_container, 1)
        root.addLayout(main_row, 1)

        # Başlangıç
        if hasattr(self.week, "setAnchorDate"):
            self.week.setAnchorDate(self._anchor_date)
        self.stacked.setCurrentIndex(0)

        # Event sinyalleri (varsa)
        if hasattr(self.week, "blockCreated"):   self.week.blockCreated.connect(self._on_block_created)
        if hasattr(self.week, "blockMoved"):     self.week.blockMoved.connect(self._on_block_moved)
        if hasattr(self.week, "blockResized"):   self.week.blockResized.connect(self._on_block_resized)
        if hasattr(self.week, "blockActivated"): self.week.blockActivated.connect(self._open_event_dialog_from_block)
        if hasattr(self.week, "emptyCellClicked"): self.week.emptyCellClicked.connect(self._on_week_empty_clicked)
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
        if hasattr(self.left_panel_widget, "attachStore"):
            self.left_panel_widget.attachStore(self.store)
        self.store.bootstrap()

        self.pomo = PomodoroPage()
        self.pomo.set_store(self.store)
        self.pomo.completed.connect(self._on_pomo_completed)

        if hasattr(self.kanban, "statusChanged"):
            self.kanban.statusChanged.connect(self.store.set_task_status)
        if hasattr(self.kanban, "taskReparented"):
            self.kanban.taskReparented.connect(self.store.set_task_parent)

    def _on_refresh_clicked(self):
        self.store.refresh()

    def _on_pomo_completed(self, task_id, actual_secs, plan_secs, note):
        # DB ekleme zaten PomodoroPage içinde store.add_pomodoro_session ile deneniyor.
        # Burada istersen küçük bir “task activity” etiketi veya status güncellemesi yap.
        if task_id:
            try:
                # Örn: toplam odak süresi alanın varsa burada artırabilirsin
                pass
            except Exception:
                pass
        # UI refresh: bir yerde açık diyalog varsa yenile
        try:
            if hasattr(self, "eventDialog") and self.eventDialog and self.eventDialog.isVisible():
                if getattr(self.eventDialog._model, "id", None) == task_id:
                    self.eventDialog._load_pomodoro_history(task_id)
        except Exception:
            pass

    def _on_add_project_clicked(self):
        # Tag seçili değilse proje eklenemez
        if self._current_tag is None:
            QtWidgets.QMessageBox.warning(
                self, "Tag required",
                "Önce bir tag seçmelisin. Tag seçmeden proje eklenemez."
            )
            return

        name, ok = QtWidgets.QInputDialog.getText(self, "Add Project", "Project name:")
        if not(ok and name.strip()):
            return

        # Tag seçiliyken projenin tag_id’sini vererek ekle
        tag_id = int(self._current_tag)
        try:
            # Muhtemel imza: add_project(name: str, tag_id: int)
            self.store.add_project(name.strip(), tag_id=tag_id)
        except TypeError:
            # Alternatif imza: add_project(name: str, tag_id: int) -> *kwargs yoksa positional dene
            try:
                self.store.add_project(name.strip(), tag_id)
            except TypeError:
                # Çok eski imza: sadece isim kabul ediyorsa, en azından engelleyelim
                QtWidgets.QMessageBox.critical(
                    self, "Unsupported",
                    "Store.add_project tag_id kabul etmiyor. Services katmanında 'add_project(name, tag_id)' desteği gerekli."
                )
                return

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
                # Boş – yeni görev (tıklanan saatlere göre)
                try:
                    start_dt, end_dt = self.week.dateTimeRangeAtPos(me.position().toPoint())
                    qd = QtCore.QDate(start_dt.year, start_dt.month, start_dt.day)
                    qs = QtCore.QTime(start_dt.hour, start_dt.minute)
                    qe = QtCore.QTime(end_dt.hour, end_dt.minute)
                    self._open_new_task_dialog(qd, qs, qe, default_has_time=True)
                    return True
                except Exception:
                    # Fallback
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
    def _build_parent_options(
        self,
        tasks: list[dict],
        tag_id: int | None,
        project_id: int | None,
        exclude_id: int | None = None,
    ) -> list[tuple[int, str]]:
        """Filter tasks to be used as parent candidates.

        Only tasks from the same project are allowed. If the task isn't
        assigned to any project, fallback to filtering by tag. Optionally the
        current task can be excluded via ``exclude_id``.
        """

        if project_id is not None:
            tasks = [
                t
                for t in tasks
                if t.get("project_id") is not None
                and int(t.get("project_id")) == int(project_id)
            ]
        elif tag_id is not None:
            tasks = [
                t
                for t in tasks
                if t.get("tag_id") is not None
                and int(t.get("tag_id")) == int(tag_id)
            ]

        if exclude_id is not None:
            tasks = [t for t in tasks if int(t.get("id")) != int(exclude_id)]

        return [(int(t["id"]), t.get("title", "")) for t in tasks]

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
        tasks = []
        try:
            db = getattr(self.store, "db", None)
            tasks = db.get_tasks() if db else []
        except Exception:
            tasks = []
        tag_opts = [(int(t["id"]), t.get("name", "")) for t in self._all_tags]
        proj_opts = [
            (int(p["id"]), p.get("name", ""), int(p.get("tag_id")) if p.get("tag_id") is not None else None)
            for p in self._all_projects
        ]
        if self._current_tag is not None:
            m.tag_id = int(self._current_tag)
        if self._current_project is not None:
            m.project_id = int(self._current_project)
        opts = self._build_parent_options(tasks, m.tag_id, m.project_id)
        dlg = EventTaskDialog(m, self, parent_options=opts, tag_options=tag_opts, project_options=proj_opts)
        dlg.openTaskRequested.connect(self._open_task_by_id)
        dlg.populate_linked_tasks([])
        dlg.saved.connect(self._on_dialog_saved)
        dlg.deleted.connect(self._on_dialog_deleted)
        dlg.exec()

    def _open_task_by_id(self, task_id: int):
        self._open_task_dialog_by_id(task_id)

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
        m.series_id = (t or {}).get("series_id")
        tasks = []
        try:
            tasks = db.get_tasks() if db else []
        except Exception:
            tasks = []
        child_rows = [
            (int(ct["id"]), ct.get("title", ""))
            for ct in tasks
            if int(ct.get("parent_id") or 0) == int(task_id)
        ]
        m.children = child_rows
        opts = self._build_parent_options(tasks, m.tag_id, m.project_id, exclude_id=task_id)
        tag_opts = [(int(tg["id"]), tg.get("name", "")) for tg in self._all_tags]
        proj_opts = [
            (int(p["id"]), p.get("name", ""), int(p.get("tag_id")) if p.get("tag_id") is not None else None)
            for p in self._all_projects
        ]
        dlg = EventTaskDialog(m, self, parent_options=opts, tag_options=tag_opts, project_options=proj_opts)
        dlg.openTaskRequested.connect(self._open_task_by_id)
        dlg.populate_linked_tasks(self.store.get_linked_tasks(int(task_id)))
        dlg.saved.connect(self._on_dialog_saved)
        dlg.deleted.connect(self._on_dialog_deleted)
        dlg.exec()

    def _open_event_dialog_from_block(self, evb: EventBlock):
        if not EventTaskDialog:
            return
        tid = int(getattr(evb, "task_id", 0) or getattr(evb, "id", 0) or 0)
        m = ItemModel(kind="event", id=tid or None, title=getattr(evb, "title", ""), notes=getattr(evb, "notes", ""))
        m.task_id = tid or None
        d = QtCore.QDate(evb.start.year, evb.start.month, evb.start.day)
        m.date = d
        m.start = QtCore.QTime(evb.start.hour, evb.start.minute)
        m.end   = QtCore.QTime(evb.end.hour, evb.end.minute)
        m.rrule   = getattr(evb, "rrule", None)

        # fetch existing tag/project from store
        task_row = None
        try:
            db = getattr(self.store, "db", None)
            task_row = db.get_task_by_id(tid) if (db and tid) else None
        except Exception:
            task_row = None
        if not task_row:
            for t in self._all_tasks:
                if int(t.get("id") or 0) == tid:
                    task_row = t
                    break
        if task_row:
            m.tag_id = task_row.get("tag_id")
            m.project_id = task_row.get("project_id")
            m.series_id = task_row.get("series_id")

        tag_opts = [(int(tg["id"]), tg.get("name", "")) for tg in self._all_tags]
        proj_opts = [
            (int(p["id"]), p.get("name", ""), int(p.get("tag_id")) if p.get("tag_id") is not None else None)
            for p in self._all_projects
        ]
        dlg = EventTaskDialog(m, self, tag_options=tag_opts, project_options=proj_opts)
        dlg.openTaskRequested.connect(self._open_task_by_id)
        dlg.populate_linked_tasks(self.store.get_linked_tasks(int(m.id)) if m.id else [])
        dlg.saved.connect(self._on_dialog_saved)
        dlg.deleted.connect(self._on_dialog_deleted)
        dlg.exec()

    def _on_week_empty_clicked(self, payload: dict):
        try:
            start_dt = payload.get('start'); end_dt = payload.get('end')
            if start_dt and end_dt:
                qd = QtCore.QDate(start_dt.year, start_dt.month, start_dt.day)
                qs = QtCore.QTime(start_dt.hour, start_dt.minute)
                qe = QtCore.QTime(end_dt.hour, end_dt.minute)
                # Week: saatli etkinlik olarak aç
                self._open_new_task_dialog(qd, qs, qe, default_has_time=True)
        except Exception:
            pass

    def _on_dialog_saved(self, model):
        start_iso = _to_iso_dt(model.date, model.start) if model.start and model.end else None
        end_iso   = _to_iso_dt(model.date, model.end)   if model.start and model.end else None
        due_iso   = _to_iso_qdate(model.date)

        # --- RRULE varsa: yeni veya mevcut fark etmeksizin genişlet ---
        if model.rrule:
            # 1) Başlangıç tarihi/saatini belirle
            dtstart = (
                datetime.fromisoformat(start_iso)
                if start_iso
                else datetime.fromisoformat(due_iso + "T00:00:00")
            )

            # 2) İlk 50 oluşumu güvenli biçimde çek (sonsuz listeleme YOK)
            try:
                from dateutil.rrule import rrulestr

                rule = rrulestr(model.rrule, dtstart=dtstart)
                dates = list(islice(rule, 50))
            except Exception:
                dates = _expand_rrule_simple(model.rrule, dtstart, limit=50)

            # 3) Seri kimliği: varsa koru, yoksa üret
            series_id = model.series_id or int(QtCore.QDateTime.currentDateTime().toSecsSinceEpoch())
            dur_secs = model.start.secsTo(model.end) if model.start and model.end else 0

            # 4) Oluşumları yaz. Mevcut öğe varsa onu güncelle, diğerlerini ekle.
            for d in dates:
                qd = QtCore.QDate(d.year, d.month, d.day)
                s_iso = d.isoformat() if model.start and model.end else None
                e_iso = (
                    (d + timedelta(seconds=dur_secs)).isoformat() if model.start and model.end else None
                )
                due = _to_iso_qdate(qd)

                is_current = False
                if model.id and start_iso and s_iso:
                    # Aynı başlangıç anı ise mevcut kaydı güncelle
                    is_current = s_iso == start_iso

                if is_current and model.id:
                    self.store.upsert_task(
                        model.id,
                        model.title or "Untitled",
                        model.notes or "",
                        due,
                        start_iso=s_iso,
                        end_iso=e_iso,
                        parent_id=model.parent_id,
                        series_id=series_id,
                        tag_id=model.tag_id,
                        project_id=model.project_id,
                    )
                else:
                    self.store.upsert_task(
                        None,
                        model.title or "Untitled",
                        model.notes or "",
                        due,
                        start_iso=s_iso,
                        end_iso=e_iso,
                        parent_id=model.parent_id,
                        series_id=series_id,
                        tag_id=model.tag_id,
                        project_id=model.project_id,
                    )

            # Mevcut kaydın id’sini güncelle (yeni yaratmadıysan da garanti)
            if not model.id:
                # İlk eklenenin id’sini geri yakalamak istiyorsan burada db’den çekebilirsin;
                # şimdilik gerekli değil.
                pass

        else:
            # RRULE yoksa klasik tek kayıt upsert
            tid = self.store.upsert_task(
                model.id,
                model.title or "Untitled",
                model.notes or "",
                due_iso,
                start_iso=start_iso,
                end_iso=end_iso,
                parent_id=model.parent_id,
                series_id=model.series_id,
                tag_id=model.tag_id,
                project_id=model.project_id,
            )
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
        if hasattr(self, "pomo"):
            try:
                self.pomo.reload_sidebar()
            except Exception:
                pass

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
        if hasattr(self.left_panel_widget, "applyServerTags"): self.left_panel_widget.applyServerTags(items)
        elif hasattr(self.left_panel_widget, "applyTags"):     self.left_panel_widget.applyTags(items)

    def _apply_projects(self, projects: list[dict]):
        self._all_projects = projects or []
        self._update_project_buttons()

    def _update_project_buttons(self):
        items: list[tuple[int, str]] = []

        # Tag seçili değilse hiçbir proje gösterme (ama task'lar gösterilmeye devam edecek)
        if self._current_tag is None:
            self.project_bar.setItems([])
            self._current_project = None
            return

        cur_tid = int(self._current_tag)

        # 1) Proje nesnesinin kendi tag_id'sine bak (var ise)
        project_ids_for_tag: set[int] = set()
        for p in self._all_projects:
            try:
                pid = int(p.get("id") or 0)
                if not pid:
                    continue
                p_tag = p.get("tag_id", None)
                if p_tag is not None and int(p_tag) == cur_tid:
                    project_ids_for_tag.add(pid)
            except Exception:
                pass

        # 2) Geri uyum için: task'lar üzerinden o tag'e ait projeleri topla
        derived_from_tasks: set[int] = {
            int(t.get("project_id"))
            for t in self._all_tasks
            if t.get("project_id") is not None and int(t.get("tag_id") or 0) == cur_tid
        }

        allowed = project_ids_for_tag | derived_from_tasks

        for p in self._all_projects:
            try:
                pid = int(p.get("id") or 0)
                if pid and pid in allowed:
                    items.append((pid, p.get("name", "")))
            except Exception:
                pass

        self.project_bar.setItems(items)

        # Seçili proje hâlâ listede mi?
        ids = {pid for pid, _ in items}
        if self._current_project in ids:
            self.project_bar.setCurrentById(int(self._current_project))
        else:
            self._current_project = None

    def _filter_tasks_and_update(self):
        # Kanban: sadece takvime bağımsız task'lar
        filtered = [t for t in self._all_tasks if not bool(t.get("has_time", 0))]

        if self._current_project is not None:
            # Proje seçimi tag'i bastırır
            filtered = [t for t in filtered if int(t.get("project_id") or 0) == int(self._current_project)]
        elif self._current_tag is not None:
            filtered = [t for t in filtered if int(t.get("tag_id") or 0) == int(self._current_tag)]

        tag_map = {int(t["id"]): t.get("name", "") for t in self._all_tags}
        proj_map = {int(p["id"]): p.get("name", "") for p in self._all_projects}
        title_map = {int(t["id"]): t.get("title", "") for t in self._all_tasks}
        for t in filtered:
            tid = int(t.get("tag_id") or 0)
            pid = int(t.get("project_id") or 0)
            par = int(t.get("parent_id") or 0)
            t["tag_name"] = tag_map.get(tid)
            t["project_name"] = proj_map.get(pid)
            t["parent_title"] = title_map.get(par)
            t["due"] = t.get("due") or t.get("due_date")

        if hasattr(self.kanban, "set_tasks"):
            self.kanban.set_tasks(filtered)

    def _filter_events_and_update(self):
        evs = list(self._all_events)

        if self._current_project is not None:
            # Proje seçimi tag'i bastırır
            evs = [e for e in evs if int(e.get("project_id") or 0) == int(self._current_project)]
        elif self._current_tag is not None:
            evs = [e for e in evs if int(e.get("tag_id") or 0) == int(self._current_tag)]

        tag_map = {int(t["id"]): t.get("name", "") for t in self._all_tags}
        proj_map = {int(p["id"]): p.get("name", "") for p in self._all_projects}
        title_map = {int(t["id"]): t.get("title", "") for t in self._all_tasks}
        for e in evs:
            tid = int(e.get("tag_id") or 0)
            pid = int(e.get("project_id") or 0)
            par = int(e.get("parent_id") or 0)
            e["tag_name"] = tag_map.get(tid)
            e["project_name"] = proj_map.get(pid)
            e["parent_title"] = title_map.get(par)
            e["due"] = e.get("due") or e.get("due_date")

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
        if mode == "daily":
            self._switch_to_day_view()

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
        if hasattr(self.week, "setAnchorDate"):
            self.week.setAnchorDate(qdate)
        if hasattr(self.day, "set_date"):
            self.day.set_date(qdate)

    def _on_week_day_selected(self, qdate: QtCore.QDate):
        if hasattr(self.day, "set_date"):
            self.day.set_date(qdate)

    def _switch_to_day_view(self):
        qd = qdate = self._anchor_date
        if hasattr(self.week, "current_selected_date"):
            try:
                qd = self.week.current_selected_date()
            except Exception:
                qd = self._anchor_date
        if hasattr(self.day, "set_date"):
            self.day.set_date(qd)
        self.stacked.setCurrentIndex(1)

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
            start_iso = QtCore.QDateTime(
                QtCore.QDate(ev.start.year, ev.start.month, ev.start.day),
                QtCore.QTime(ev.start.hour, ev.start.minute),
            ).toString(QtCore.Qt.DateFormat.ISODate)
            end_iso = QtCore.QDateTime(
                QtCore.QDate(ev.end.year, ev.end.month, ev.end.day),
                QtCore.QTime(ev.end.hour, ev.end.minute),
            ).toString(QtCore.Qt.DateFormat.ISODate)
            if start_iso and end_iso:
                if hasattr(self.store, "update_task_times"):
                    self.store.update_task_times(
                        task_id=tid, start_iso=start_iso, end_iso=end_iso
                    )
                else:
                    self.store.set_task_times(tid, start_iso, end_iso)

    def _on_block_resized(self, ev: EventBlock):
        self._on_block_moved(ev)
