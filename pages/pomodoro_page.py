# pomodoro_page.py — Planner uyumlu Pomodoro (iki mod + not + görev seçici + ikon bar)

from __future__ import annotations
from typing import Any, Callable, Dict, List, Optional
from datetime import datetime, timedelta

from PyQt6 import QtCore, QtGui, QtWidgets

from widgets.core.selectors import ProjectButtonRow
from widgets.layout.navigator import NavIconButton
from utils.icons import make_icon_pm_pair

# Planner renkleri
try:
    from theme.colors import COLOR_PRIMARY_BG, COLOR_SECONDARY_BG, COLOR_TEXT, COLOR_TEXT_MUTED, COLOR_ACCENT
except Exception:
    COLOR_PRIMARY_BG   = "#212121"
    COLOR_SECONDARY_BG = "#2d2d2d"
    COLOR_TEXT         = "#EEEEEE"
    COLOR_TEXT_MUTED   = "#AEAEAE"
    COLOR_ACCENT       = "#15B4B9"


class PomodoroPage(QtWidgets.QWidget):
    """
    - Başlamadan önce: orta bölümde büyük editable süre (borderless QLineEdit görünümlü sayaç)
    - Başladıktan sonra: büyük LABEL sayaç
    - Sol: not alanı (sayfanın ~1/3’ü)
    - Sağ: In Progress görev seçici (TAG > PROJECT > TASK listesi)
    - Alt merkez: ikon barı (Başlat, Durdur, Sıfırla, Erken Bitir)
    - Sinyaller:
        started(task_id:int|None, plan_secs:int)
        paused(task_id:int|None, elapsed_secs:int)
        reset(task_id:int|None)
        completed(task_id:int|None, actual_secs:int, plan_secs:int, note:str)
    """
    started   = QtCore.pyqtSignal(object, int)
    paused    = QtCore.pyqtSignal(object, int)
    reset     = QtCore.pyqtSignal(object)
    completed = QtCore.pyqtSignal(object, int, int, str)
    taskActivated = QtCore.pyqtSignal(int)

    def __init__(self, parent: Optional[QtWidgets.QWidget] = None):
        super().__init__(parent)

        # --- State ---
        self._plan_secs: int = 25 * 60
        self._remaining: int = self._plan_secs
        self._running: bool = False
        self._current_task_id: Optional[int] = None
        self._elapsed_before_pause: int = 0
        self._tick_start_mono_ms: int = 0
        self._store: Any = None
        self._task_fetcher: Optional[Callable[[], List[Dict[str, Any]]]] = None
        self._tag_ids: Dict[int, str] = {}
        self._proj_ids: Dict[int, str] = {}
        self._sel_tag_id: int = 0
        self._sel_proj_id: int = 0
        self._tasks_all: List[Dict[str, Any]] = []
        self._tags_map: Dict[int, str] = {}
        self._projects_map: Dict[int, str] = {}

        self._timer = QtCore.QTimer(self)
        self._timer.setInterval(1000)
        self._timer.timeout.connect(self._on_tick)

        self._build_ui()
        self._apply_styles()
        self._sync_labels()
        self._wire()

    # ------------------------------ Public API ---------------------------------

    def set_store(self, store: Any):
        """Planner ile aynı store'u bağla ve yan paneli tazele."""
        self._store = store
        self._task_fetcher = None
        self.reload_sidebar()

    def set_tasks(self, tasks: List[Dict[str, Any]]):
        self._task_fetcher = lambda: tasks
        self.reload_sidebar()

    def reload_tasks(self):
        self.reload_sidebar()

    def reload_sidebar(self):
        tasks: List[Dict[str, Any]] = []
        if self._task_fetcher:
            try:
                tasks = self._task_fetcher() or []
            except Exception:
                tasks = []
        else:
            tasks = self._fetch_tasks_from_store()

        tags, projects = self._fetch_tags_projects()
        self._tags_map = {int(t.get("id")): t.get("name", "") for t in tags if t.get("id") is not None}
        self._projects_map = {int(p.get("id")): p.get("name", "") for p in projects if p.get("id") is not None}

        all_norm = self._normalize_tasks(tasks)
        inprog = [t for t in all_norm if self._is_in_progress(t)]
        self._tasks_all = inprog if inprog else all_norm
        self._fill_tag_project_filters()

    # ------------------------------ UI -----------------------------------------

    def _build_ui(self):
        self.setObjectName("PomodoroPage")
        root = QtWidgets.QVBoxLayout(self)
        root.setContentsMargins(12, 12, 12, 12)  # Planner başlık hizasıyla aynı
        root.setSpacing(8)

        # ---- HEADER ----
        header_w = QtWidgets.QWidget()
        header = QtWidgets.QHBoxLayout(header_w)
        header.setContentsMargins(12, 12, 12, 8)
        header.setSpacing(8)
        self.lbl_title = QtWidgets.QLabel("Pomodoro")
        self.lbl_title.setObjectName("title")
        font = self.lbl_title.font()
        font.setPointSize(20)
        font.setWeight(600)
        self.lbl_title.setFont(font)
        header.addWidget(self.lbl_title)
        header.addStretch(1)
        pm_n, pm_a = make_icon_pm_pair(
            self.style().standardIcon(QtWidgets.QStyle.StandardPixmap.SP_BrowserReload),
            size=24,
            normal_color=COLOR_TEXT_MUTED,
            active_color=COLOR_ACCENT,
        )
        self.btn_refresh = NavIconButton(pm_n, pm_a, row_width=40, box_w=32, box_h=32, tooltip="Refresh")
        header.addWidget(self.btn_refresh)
        root.addWidget(header_w)

        # Orta üçlü: Sol Not — Orta Sayaç — Sağ Görev Paneli
        tri = QtWidgets.QHBoxLayout()
        tri.setSpacing(12)
        root.addLayout(tri, 1)

        # Sol: Not alanı
        left = QtWidgets.QFrame()
        left.setObjectName("pane_primary")
        left.setMinimumWidth(260)
        l_lo = QtWidgets.QVBoxLayout(left); l_lo.setContentsMargins(12,12,12,12); l_lo.setSpacing(8)
        lbl_notes = QtWidgets.QLabel("Notlar")
        lbl_notes.setStyleSheet(f"color:{COLOR_TEXT_MUTED};")
        l_lo.addWidget(lbl_notes)
        self.txt_notes = QtWidgets.QTextEdit()
        self.txt_notes.setPlaceholderText("Pomodoro notlarını buraya yaz…")
        l_lo.addWidget(self.txt_notes, 1)
        tri.addWidget(left, 1)

        # Orta: Sayaç (iki mod için stacked)
        center = QtWidgets.QFrame()
        center.setObjectName("pane")
        c_lo = QtWidgets.QVBoxLayout(center); c_lo.setContentsMargins(12,12,12,12); c_lo.setSpacing(8)

        self.stack_timer = QtWidgets.QStackedWidget()

        # Pre-start: borderless editable süre (line edit – büyük yazı)
        pre = QtWidgets.QWidget()
        pre_lo = QtWidgets.QVBoxLayout(pre); pre_lo.setContentsMargins(0,0,0,0); pre_lo.setSpacing(0)
        self.edit_time = QtWidgets.QLineEdit()
        self.edit_time.setObjectName("edit_time")
        self.edit_time.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        self.edit_time.setPlaceholderText("25:00")
        pre_lo.addStretch(1); pre_lo.addWidget(self.edit_time); pre_lo.addStretch(1)

        # Running: büyük label
        run = QtWidgets.QWidget()
        run_lo = QtWidgets.QVBoxLayout(run); run_lo.setContentsMargins(0,0,0,0); run_lo.setSpacing(0)
        self.lbl_time = QtWidgets.QLabel("--:--")
        self.lbl_time.setObjectName("time")
        self.lbl_time.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        run_lo.addStretch(1); run_lo.addWidget(self.lbl_time); run_lo.addStretch(1)

        self.stack_timer.addWidget(pre)   # index 0
        self.stack_timer.addWidget(run)   # index 1

        c_lo.addWidget(self.stack_timer, 1)
        center.setLayout(c_lo)
        tri.addWidget(center, 1)

        # Sağ: In Progress görev seçici (TAG → PROJECT → TASK)
        right = QtWidgets.QFrame()
        right.setObjectName("pane_primary")
        r_lo = QtWidgets.QVBoxLayout(right); r_lo.setContentsMargins(12,12,12,12); r_lo.setSpacing(8)

        lbl_tags = QtWidgets.QLabel("Taglar")
        lbl_tags.setStyleSheet(f"color:{COLOR_TEXT_MUTED};")
        r_lo.addWidget(lbl_tags)
        self.tag_bar = ProjectButtonRow()
        r_lo.addWidget(self.tag_bar)

        lbl_proj = QtWidgets.QLabel("Projeler")
        lbl_proj.setStyleSheet(f"color:{COLOR_TEXT_MUTED};")
        r_lo.addWidget(lbl_proj)
        self.project_bar = ProjectButtonRow()
        r_lo.addWidget(self.project_bar)

        lbl_tasks = QtWidgets.QLabel("Görevler")
        lbl_tasks.setStyleSheet(f"color:{COLOR_TEXT_MUTED};")
        r_lo.addWidget(lbl_tasks)
        class TaskListWidget(QtWidgets.QListWidget):
            def resizeEvent(self, e: QtGui.QResizeEvent):
                super().resizeEvent(e)
                w = self.viewport().width() - 12
                for i in range(self.count()):
                    it = self.item(i)
                    sz = it.sizeHint()
                    if sz.width() != w:
                        it.setSizeHint(QtCore.QSize(w, sz.height()))

        self.list_tasks = TaskListWidget()
        self.list_tasks.setViewMode(QtWidgets.QListWidget.ViewMode.ListMode)
        self.list_tasks.setFlow(QtWidgets.QListView.Flow.TopToBottom)
        self.list_tasks.setUniformItemSizes(True)
        self.list_tasks.setSpacing(6)
        self.list_tasks.setSelectionMode(QtWidgets.QAbstractItemView.SelectionMode.SingleSelection)
        r_lo.addWidget(self.list_tasks, 1)

        tri.addWidget(right, 1)

        # Alt: ikon bar (merkez)
        bar = QtWidgets.QHBoxLayout()
        bar.setContentsMargins(0,0,0,0); bar.setSpacing(8)
        root.addLayout(bar, 0)

        bar.addStretch(1)
        self.btn_start = QtWidgets.QToolButton(); self.btn_start.setIcon(self.style().standardIcon(QtWidgets.QStyle.StandardPixmap.SP_MediaPlay)); self.btn_start.setToolTip("Başlat")
        self.btn_pause = QtWidgets.QToolButton(); self.btn_pause.setIcon(self.style().standardIcon(QtWidgets.QStyle.StandardPixmap.SP_MediaPause)); self.btn_pause.setToolTip("Durdur")
        self.btn_reset = QtWidgets.QToolButton(); self.btn_reset.setIcon(self.style().standardIcon(QtWidgets.QStyle.StandardPixmap.SP_BrowserReload)); self.btn_reset.setToolTip("Sıfırla")
        self.btn_finish= QtWidgets.QToolButton(); self.btn_finish.setIcon(self.style().standardIcon(QtWidgets.QStyle.StandardPixmap.SP_DialogApplyButton)); self.btn_finish.setToolTip("Erken bitir / Tamamlandı")
        for b in (self.btn_start, self.btn_pause, self.btn_reset, self.btn_finish):
            b.setCursor(QtGui.QCursor(QtCore.Qt.CursorShape.PointingHandCursor))
            b.setIconSize(QtCore.QSize(28,28))
        bar.addWidget(self.btn_start); bar.addWidget(self.btn_pause); bar.addWidget(self.btn_reset); bar.addWidget(self.btn_finish)
        bar.addStretch(1)

    def _apply_styles(self):
        self.setStyleSheet(f"""
            QWidget#PomodoroPage {{
                background: {COLOR_PRIMARY_BG};
                color: {COLOR_TEXT};
            }}
            QLabel#title {{
                font-size: 20px;
                font-weight: 600;
            }}
            QFrame#pane {{
                background: {COLOR_SECONDARY_BG};
                border: 1px solid #3a3a3a;
                border-radius: 14px;
            }}
            QFrame#pane_primary {{
                background: {COLOR_PRIMARY_BG};
                border: none;
                border-radius: 14px;
            }}
            QLabel#time {{
                font-size: 64px;
                font-weight: 800;
                padding: 8px 0 12px 0;
            }}
            QLineEdit#edit_time {{
                font-size: 64px;
                font-weight: 800;
                padding: 8px 0 12px 0;
                border: none;
                background: transparent;
                color: {COLOR_TEXT};
                selection-background-color: {COLOR_ACCENT};
            }}
            QListWidget {{
                background: {COLOR_SECONDARY_BG};
                border: none;
                border-radius: 8px;
                color: {COLOR_TEXT};
            }}
            QTextEdit {{
                background: {COLOR_SECONDARY_BG};
                border: 1px solid #3a3a3a;
                border-radius: 10px;
                color: {COLOR_TEXT};
            }}
            QToolButton {{
                background: {COLOR_SECONDARY_BG};
                border: 1px solid #3a3a3a;
                border-radius: 10px;
                padding: 8px;
            }}
            QToolButton:hover {{ border-color: #4a4a4a; }}
        """)

    def _wire(self):
        self.btn_refresh.clicked.connect(self.reload_sidebar)
        self.btn_start.clicked.connect(self._start)
        self.btn_pause.clicked.connect(self._pause)
        self.btn_reset.clicked.connect(self._reset)
        self.btn_finish.clicked.connect(self._finish_early)

        self.edit_time.editingFinished.connect(self._apply_edit_time)

        self.tag_bar.changed.connect(self._on_tag_changed)
        self.project_bar.changed.connect(self._on_proj_changed)
        self.list_tasks.itemSelectionChanged.connect(self._on_task_selected)
        self.list_tasks.itemDoubleClicked.connect(self._emit_task_activated)

    # ------------------------------ Tasks Sidebar -------------------------------

    def _fetch_tasks_from_store(self) -> List[Dict[str, Any]]:
        if not self._store:
            return []
        db = getattr(self._store, "db", None)
        if db:
            for fn_name in ("get_all_tasks", "get_tasks"):
                if hasattr(db, fn_name):
                    try:
                        return getattr(db, fn_name)() or []
                    except Exception:
                        pass
        for fn_name in ("list_open_tasks", "list_tasks", "fetch_tasks", "all_tasks", "get_tasks"):
            if hasattr(self._store, fn_name):
                try:
                    return getattr(self._store, fn_name)() or []
                except Exception:
                    pass
        return []

    def _fetch_tags_projects(self) -> tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
        tags: List[Dict[str, Any]] = []
        projects: List[Dict[str, Any]] = []
        if not self._store:
            return tags, projects
        db = getattr(self._store, "db", None)
        if db:
            try:
                tags = db.get_tags() or []
            except Exception:
                pass
            try:
                projects = db.get_projects() or []
            except Exception:
                pass
        return tags, projects

    def _is_in_progress(self, t: dict) -> bool:
        s = (t.get("status") or "").strip().lower()
        tokens = ("in progress", "in_progress", "progress", "working", "doing", "devam", "çalış", "aktif")
        return any(tok in s for tok in tokens)

    def _normalize_tasks(self, tasks: Any) -> List[Dict[str, Any]]:
        out: List[Dict[str, Any]] = []
        for t in tasks or []:
            if isinstance(t, dict):
                tid    = t.get("id") or t.get("task_id")
                title  = t.get("title") or t.get("name") or f"Task {tid}"
                tag_id = t.get("tag_id")
                proj_id = t.get("project_id")
                tag    = t.get("tag") or t.get("tag_name")
                if tag is None and tag_id is not None:
                    tag = self._tags_map.get(int(tag_id), "")
                if tag is None:
                    tag = ""
                proj   = t.get("project") or t.get("project_name")
                if proj is None and proj_id is not None:
                    proj = self._projects_map.get(int(proj_id), "")
                if proj is None:
                    proj = ""
                parent = t.get("parent") or t.get("parent_title") or ""
                status = t.get("status") or t.get("state") or ""
                due = t.get("due") or t.get("due_date") or ""
            elif isinstance(t, (tuple, list)) and len(t) >= 2:
                tid, title = t[0], t[1]
                tag = proj = parent = status = due = ""
            else:
                continue
            meta_parts = [p for p in (tag, proj, parent) if p]
            meta = ">".join(meta_parts) if meta_parts else ""
            out.append({"id": tid, "title": title, "tag": tag, "project": proj, "parent": parent, "meta": meta, "status": status, "due": due})
        return out

    def _fill_tag_project_filters(self):
        tags = sorted({t["tag"] for t in self._tasks_all if t.get("tag")})
        self._tag_ids = {i + 1: tg for i, tg in enumerate(tags)}
        self.tag_bar.setItems([(i, tg) for i, tg in self._tag_ids.items()])
        self._sel_tag_id = 0
        self._on_tag_changed(0)

    def _on_tag_changed(self, tag_id: int):
        self._sel_tag_id = tag_id
        sel_tag = self._tag_ids.get(tag_id)
        filtered = [t for t in self._tasks_all if (sel_tag is None or t.get("tag") == sel_tag)]

        projs = sorted({t["project"] for t in filtered if t.get("project")})
        self._proj_ids = {i + 1: pr for i, pr in enumerate(projs)}
        self.project_bar.setItems([(i, pr) for i, pr in self._proj_ids.items()])
        self._sel_proj_id = 0
        self._fill_task_list(filtered)

    def _on_proj_changed(self, proj_id: int):
        self._sel_proj_id = proj_id
        self._fill_task_list()

    def _fill_task_list(self, base: Optional[List[Dict[str, Any]]] = None):
        sel_tag = self._tag_ids.get(self._sel_tag_id)
        sel_proj = self._proj_ids.get(self._sel_proj_id)

        items = base if base is not None else [t for t in self._tasks_all
                 if (sel_tag is None or t.get("tag") == sel_tag)
                 and (sel_proj is None or t.get("project") == sel_proj)]

        self.list_tasks.clear()
        for t in items:
            self._add_task_item(t["id"], t["title"], t.get("meta"), t.get("due"))

        # önceki seçimi muhafaza etmek istersen burada arayabilirsin.

    def _add_task_item(self, task_id: int, title: str, meta: Optional[str] = None, due: Optional[str] = None):
        plain = title or f"Task #{task_id}"
        if meta:
            left_html = f"{plain} <span style='color:{COLOR_TEXT_MUTED};'>({meta})</span>"
        else:
            left_html = plain

        it = QtWidgets.QListWidgetItem()
        it.setData(QtCore.Qt.ItemDataRole.UserRole, task_id)
        it.setFlags(it.flags() | QtCore.Qt.ItemFlag.ItemIsSelectable | QtCore.Qt.ItemFlag.ItemIsEnabled)

        w = QtWidgets.QWidget()
        row = QtWidgets.QHBoxLayout(w)
        row.setContentsMargins(8, 6, 8, 6)
        row.setSpacing(8)

        lbl_left = QtWidgets.QLabel()
        lbl_left.setTextFormat(QtCore.Qt.TextFormat.RichText)
        lbl_left.setWordWrap(True)
        lbl_left.setText(left_html)

        due_disp = ""
        if due:
            try:
                due_disp = datetime.fromisoformat(str(due).replace("Z", "+00:00")).date().isoformat()
            except Exception:
                due_disp = str(due).split(" ")[0]
        lbl_right = QtWidgets.QLabel(due_disp)
        lbl_right.setAlignment(QtCore.Qt.AlignmentFlag.AlignRight | QtCore.Qt.AlignmentFlag.AlignVCenter)

        row.addWidget(lbl_left, 1)
        row.addWidget(lbl_right, 1)

        self.list_tasks.addItem(it)
        self.list_tasks.setItemWidget(it, w)
        it.setSizeHint(QtCore.QSize(self.list_tasks.viewport().width() - 12, max(40, w.sizeHint().height())))

    def _on_task_selected(self):
        it = self.list_tasks.currentItem()
        self._current_task_id = it.data(QtCore.Qt.ItemDataRole.UserRole) if it else None

    def _emit_task_activated(self, item: QtWidgets.QListWidgetItem):
        try:
            task_id = int(item.data(QtCore.Qt.ItemDataRole.UserRole))
            self.taskActivated.emit(task_id)
        except Exception:
            pass

    # ------------------------------ Timer Logic ---------------------------------

    def _apply_edit_time(self):
        text = (self.edit_time.text() or "").strip()
        secs = self._parse_duration_text(text) if text else self._plan_secs
        if secs <= 0: secs = 60
        self._plan_secs = secs
        if not self._running:
            self._remaining = secs
            self._elapsed_before_pause = 0
        self._sync_labels()

    def _parse_duration_text(self, text: str) -> int:
        # "25" (dk), "25:00", "1:30:00" (hh:mm:ss) destekler
        parts = [p for p in text.replace(" ", "").split(":") if p != ""]
        if not parts:
            return 0
        if len(parts) == 1:
            m = int(parts[0])
            return max(0, m) * 60
        if len(parts) == 2:
            m, s = int(parts[0]), int(parts[1])
            return m*60 + s
        if len(parts) == 3:
            h, m, s = int(parts[0]), int(parts[1]), int(parts[2])
            return h*3600 + m*60 + s
        return 0

    def _sync_labels(self):
        m, s = divmod(max(0, self._remaining), 60)
        if self._running:
            self.lbl_time.setText(f"{m:02d}:{s:02d}")
        else:
            # pre-start input'u da bu formata eşitle
            self.edit_time.setText(f"{m:02d}:{s:02d}")

    def _start(self):
        if self._running:
            return
        # sadece ilk başlatmada editördeki süreyi uygula
        if self._elapsed_before_pause == 0:
            self._apply_edit_time()
        self._running = True
        self._tick_start_mono_ms = QtCore.QTime.currentTime().msecsSinceStartOfDay()
        self._timer.start()
        self.stack_timer.setCurrentIndex(1)  # Running görünüme geç
        if self._elapsed_before_pause == 0:
            self.started.emit(self._current_task_id, self._plan_secs)

    def _pause(self):
        if not self._running:
            return
        self._timer.stop()
        self._running = False
        self._elapsed_before_pause = self._elapsed_total()
        self.stack_timer.setCurrentIndex(0)  # Pre-start görünümüne dön (süre editlenebilir)
        self._sync_labels()
        self.paused.emit(self._current_task_id, self._elapsed_before_pause)

    def _reset(self):
        was_running = self._running
        if was_running:
            self._timer.stop()
        self._running = False
        self._elapsed_before_pause = 0
        self._remaining = self._plan_secs
        self.stack_timer.setCurrentIndex(0)
        self._sync_labels()
        self.reset.emit(self._current_task_id)

    def _finish_early(self):
        """Erken bitir: planı tamamlamadan seansı sonlandır."""
        actual = self._elapsed_total() if self._running else self._elapsed_before_pause
        self._finish_and_log(actual_secs=max(1, actual))

    def _elapsed_total(self) -> int:
        if not self._running:
            return self._elapsed_before_pause
        now_ms = QtCore.QTime.currentTime().msecsSinceStartOfDay()
        delta_ms = max(0, now_ms - self._tick_start_mono_ms)
        return self._elapsed_before_pause + delta_ms // 1000

    def _on_tick(self):
        if not self._running:
            return
        self._remaining = max(0, self._remaining - 1)
        self._sync_labels()
        if self._remaining <= 0:
            self._finish_and_log(actual_secs=self._plan_secs)

    def _finish_and_log(self, actual_secs: int):
        # Sayaç durumu
        self._timer.stop()
        self._running = False
        self._elapsed_before_pause = 0
        self._remaining = self._plan_secs
        self.stack_timer.setCurrentIndex(0)
        self._sync_labels()

        note = (self.txt_notes.toPlainText() or "").strip()
        self.completed.emit(self._current_task_id, int(actual_secs), int(self._plan_secs), note)

        # DB’ye yaz (varsa store)
        try:
            if self._store and hasattr(self._store, "add_pomodoro_session"):
                self._store.add_pomodoro_session(
                    task_id=self._current_task_id,
                    planned_secs=int(self._plan_secs),
                    actual_secs=int(actual_secs),
                    note=note
                )
        except Exception:
            pass

        # Görsel bir feedback
        try:
            eff = QtWidgets.QGraphicsColorizeEffect(self)
            eff.setColor(QtGui.QColor(COLOR_ACCENT))
            self.setGraphicsEffect(eff)
            QtCore.QTimer.singleShot(600, lambda: self.setGraphicsEffect(None))
        except Exception:
            pass

        # Notu temizlemek istersen (yorum satırını kaldır)
        # self.txt_notes.clear()
