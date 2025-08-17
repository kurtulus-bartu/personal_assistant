# pomodoro_page.py — Planner uyumlu Pomodoro (iki mod + not + görev seçici + ikon bar)

from __future__ import annotations
from typing import Any, Callable, Dict, List, Optional, Tuple
from datetime import datetime, timedelta

from PyQt6 import QtCore, QtGui, QtWidgets

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

        self._timer = QtCore.QTimer(self)
        self._timer.setInterval(1000)
        self._timer.timeout.connect(self._on_tick)

        self._build_ui()
        self._apply_styles()
        self._sync_labels()
        self._wire()

    # ------------------------------ Public API ---------------------------------

    def set_store(self, store: Any, fetcher_name_candidates: Tuple[str, ...] = ("list_open_tasks", "list_tasks", "fetch_tasks", "all_tasks")):
        self._store = store
        self._task_fetcher = None
        for name in fetcher_name_candidates:
            if hasattr(store, name):
                fn = getattr(store, name)
                if callable(fn):
                    def fetch():
                        try:
                            tasks = fn()
                        except TypeError:
                            tasks = fn(self)
                        return self._normalize_tasks(tasks)
                    self._task_fetcher = fetch
                    break
        self.reload_tasks()

    def set_tasks(self, tasks: List[Dict[str, Any]]):
        self._task_fetcher = lambda: self._normalize_tasks(tasks)
        self.reload_tasks()

    def reload_tasks(self):
        items = []
        if self._task_fetcher:
            try:
                items = self._task_fetcher() or []
            except Exception:
                items = []
        # Sadece "In Progress"
        items = [t for t in items if (t.get("status") or "").lower() in ("in progress","in_progress","progress","working","doing")]
        self._tasks_all = items
        self._fill_tag_project_filters()

    # ------------------------------ UI -----------------------------------------

    def _build_ui(self):
        self.setObjectName("PomodoroPage")
        root = QtWidgets.QVBoxLayout(self)
        root.setContentsMargins(12, 12, 12, 12)  # Planner başlık hizasıyla aynı
        root.setSpacing(12)

        # Title
        self.lbl_title = QtWidgets.QLabel("Pomodoro")
        self.lbl_title.setObjectName("title")
        root.addWidget(self.lbl_title, 0, QtCore.Qt.AlignmentFlag.AlignLeft)

        # Orta üçlü: Sol Not — Orta Sayaç — Sağ Görev Paneli
        tri = QtWidgets.QHBoxLayout()
        tri.setSpacing(12)
        root.addLayout(tri, 1)

        # Sol: Not alanı
        left = QtWidgets.QFrame()
        left.setObjectName("pane")
        left.setMinimumWidth(260)
        l_lo = QtWidgets.QVBoxLayout(left); l_lo.setContentsMargins(12,12,12,12); l_lo.setSpacing(8)
        l_lo.addWidget(QtWidgets.QLabel("Notlar (bu pomodoro’ya kaydedilecek):"))
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
        right.setObjectName("pane")
        r_lo = QtWidgets.QVBoxLayout(right); r_lo.setContentsMargins(12,12,12,12); r_lo.setSpacing(8)

        row_tag = QtWidgets.QHBoxLayout()
        row_tag.addWidget(QtWidgets.QLabel("Tag:"))
        self.cmb_tag = QtWidgets.QComboBox()
        row_tag.addWidget(self.cmb_tag, 1)
        r_lo.addLayout(row_tag)

        row_proj = QtWidgets.QHBoxLayout()
        row_proj.addWidget(QtWidgets.QLabel("Proje:"))
        self.cmb_proj = QtWidgets.QComboBox()
        row_proj.addWidget(self.cmb_proj, 1)
        r_lo.addLayout(row_proj)

        r_lo.addWidget(QtWidgets.QLabel("Görevler:"))
        self.list_tasks = QtWidgets.QListWidget()
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
                padding-left: 2px;  /* Planner başlık hizası */
            }}
            QFrame#pane {{
                background: {COLOR_SECONDARY_BG};
                border: 1px solid #3a3a3a;
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
            QComboBox, QListWidget, QTextEdit {{
                background: {COLOR_PRIMARY_BG};
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
        self.btn_start.clicked.connect(self._start)
        self.btn_pause.clicked.connect(self._pause)
        self.btn_reset.clicked.connect(self._reset)
        self.btn_finish.clicked.connect(self._finish_early)

        self.edit_time.editingFinished.connect(self._apply_edit_time)

        self.cmb_tag.currentIndexChanged.connect(self._apply_filters)
        self.cmb_proj.currentIndexChanged.connect(self._apply_filters)
        self.list_tasks.itemSelectionChanged.connect(self._on_task_selected)

    # ------------------------------ Tasks Sidebar -------------------------------

    def _normalize_tasks(self, tasks: Any) -> List[Dict[str, Any]]:
        out: List[Dict[str, Any]] = []
        for t in tasks or []:
            if isinstance(t, dict):
                tid    = t.get("id") or t.get("task_id")
                title  = t.get("title") or t.get("name") or f"Task {tid}"
                tag    = t.get("tag") or t.get("tag_name") or ""
                proj   = t.get("project") or t.get("project_name") or ""
                parent = t.get("parent") or t.get("parent_title") or ""
                status = t.get("status") or t.get("state") or ""
            elif isinstance(t, (tuple, list)) and len(t) >= 2:
                tid, title = t[0], t[1]
                tag = proj = parent = status = ""
            else:
                continue
            meta_parts = [p for p in (tag, proj, parent) if p]
            meta = ">".join(meta_parts) if meta_parts else ""
            out.append({"id": tid, "title": title, "tag": tag, "project": proj, "parent": parent, "meta": meta, "status": status})
        return out

    def _fill_tag_project_filters(self):
        tags = sorted({t["tag"] for t in self._tasks_all if t.get("tag")})
        self.cmb_tag.blockSignals(True); self.cmb_tag.clear(); self.cmb_tag.addItem("Tümü", userData=None)
        for tg in tags: self.cmb_tag.addItem(tg, userData=tg)
        self.cmb_tag.blockSignals(False)

        self._apply_filters()

    def _apply_filters(self):
        sel_tag = self.cmb_tag.currentData()
        filtered = [t for t in self._tasks_all if (sel_tag is None or t.get("tag")==sel_tag)]

        projs = sorted({t["project"] for t in filtered if t.get("project")})
        self.cmb_proj.blockSignals(True); self.cmb_proj.clear(); self.cmb_proj.addItem("Tümü", userData=None)
        for pr in projs: self.cmb_proj.addItem(pr, userData=pr)
        self.cmb_proj.blockSignals(False)

        self._fill_task_list()

    def _fill_task_list(self):
        sel_tag = self.cmb_tag.currentData()
        sel_proj= self.cmb_proj.currentData()

        items = [t for t in self._tasks_all
                 if (sel_tag is None or t.get("tag")==sel_tag)
                 and (sel_proj is None or t.get("project")==sel_proj)]

        self.list_tasks.clear()
        for t in items:
            txt = t["title"] if not t.get("meta") else f'{t["title"]} ({t["meta"]})'
            it = QtWidgets.QListWidgetItem(txt)
            it.setData(QtCore.Qt.ItemDataRole.UserRole, t["id"])
            self.list_tasks.addItem(it)

        # önceki seçimi muhafaza etmek istersen burada arayabilirsin.

    def _on_task_selected(self):
        it = self.list_tasks.currentItem()
        self._current_task_id = it.data(QtCore.Qt.ItemDataRole.UserRole) if it else None

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
        # süreyi editörden güncelle
        self._apply_edit_time()
        self._running = True
        self._tick_start_mono_ms = QtCore.QTime.currentTime().msecsSinceStartOfDay()
        self._timer.start()
        self.stack_timer.setCurrentIndex(1)  # Running görünüme geç
        self.started.emit(self._current_task_id, self._plan_secs)

    def _pause(self):
        if not self._running:
            return
        self._timer.stop()
        self._running = False
        self._elapsed_before_pause = self._elapsed_total()
        self.stack_timer.setCurrentIndex(0)  # Pre-start görünümüne dön (süre editlenebilir)
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
