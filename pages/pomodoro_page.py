# pomodoro_page.py  — TAM DOSYA (drop-in)

from __future__ import annotations

from PyQt6 import QtCore, QtWidgets, QtGui
from typing import Any, Callable, Dict, List, Optional, Tuple

# Colors (align with Planner)
try:
    from theme.colors import COLOR_PRIMARY_BG, COLOR_SECONDARY_BG, COLOR_TEXT, COLOR_TEXT_MUTED, COLOR_ACCENT
except Exception:
    # Safe fallbacks
    COLOR_PRIMARY_BG   = "#212121"
    COLOR_SECONDARY_BG = "#2d2d2d"
    COLOR_TEXT         = "#EEEEEE"
    COLOR_TEXT_MUTED   = "#AEAEAE"
    COLOR_ACCENT       = "#15B4B9"


class PomodoroPage(QtWidgets.QWidget):
    """
    Planner-benzeri Pomodoro sayfası:
    - Süre ayarlanabilir (dakika)
    - Task seçilip o task için Pomodoro başlatılabilir
    - Başlat / Durdur / Sıfırla
    - Planner Page stiliyle uyumlu kart tasarımı
    - Sinyaller: started(task_id, secs), paused(task_id, elapsed), reset(task_id), completed(task_id)
    """
    started   = QtCore.pyqtSignal(object, int)   # task_id, plan_secs
    paused    = QtCore.pyqtSignal(object, int)   # task_id, elapsed_secs
    reset     = QtCore.pyqtSignal(object)        # task_id
    completed = QtCore.pyqtSignal(object, int)   # task_id, plan_secs

    def __init__(self, parent: Optional[QtWidgets.QWidget] = None):
        super().__init__(parent)

        # --- State ---
        self._plan_secs: int = 25 * 60
        self._remaining: int = self._plan_secs
        self._running: bool = False
        self._current_task_id: Optional[int] = None
        self._elapsed_before_pause: int = 0  # toplam geçen süre
        self._tick_start_mono_ms: int = 0

        self._timer = QtCore.QTimer(self)
        self._timer.setInterval(1000)
        self._timer.timeout.connect(self._on_tick)

        # optional store/callback for tasks
        self._store: Any = None
        self._task_fetcher: Optional[Callable[[], List[Dict[str, Any]]]] = None
        self._all_tasks: List[Dict[str, Any]] = []

        self._build_ui()
        self._apply_styles()
        self._sync_labels()
        self._update_ui_state()

    # ------------------------------ Public API ---------------------------------

    def set_store(self, store: Any, fetcher_name_candidates: Tuple[str, ...] = ("list_open_tasks", "list_tasks", "fetch_tasks", "all_tasks")):
        """Store enjekte et; bilinen isimlerden birini deneyerek task listesi çek."""
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
                            tasks = fn(self)  # bazı implementasyonlar self istiyor olabilir
                        return self._normalize_tasks(tasks)
                    self._task_fetcher = fetch
                    break
        self.reload_tasks()

    def set_tasks(self, tasks: List[Dict[str, Any]]):
        """Harici listeden taskları yüklemek için alternatif API."""
        self._task_fetcher = lambda: self._normalize_tasks(tasks)
        self.reload_tasks()

    def reload_tasks(self):
        items: List[Dict[str, Any]] = []
        if self._task_fetcher:
            try:
                items = self._task_fetcher() or []
            except Exception:
                items = []
        items = [t for t in items if str(t.get("status", "")).lower() in {"in progress", "doing"}]
        self._all_tasks = items
        self._fill_tag_project()
        self._apply_filters()

    # ------------------------------ UI Build -----------------------------------

    def _build_ui(self):
        self.setObjectName("PomodoroPage")
        self.setAutoFillBackground(True)

        outer = QtWidgets.QHBoxLayout(self)
        outer.setContentsMargins(12, 12, 12, 12)
        outer.setSpacing(12)

        # Left note area
        self.note_edit = QtWidgets.QTextEdit()
        self.note_edit.setObjectName("note")
        self.note_edit.setPlaceholderText("Not...")
        outer.addWidget(self.note_edit, 1)

        # Center timer card
        center_wrap = QtWidgets.QVBoxLayout()
        outer.addLayout(center_wrap, 1)

        header = QtWidgets.QHBoxLayout()
        lbl_title = QtWidgets.QLabel("Pomodoro")
        lbl_title.setObjectName("title")
        header.addWidget(lbl_title, 1)
        center_wrap.addLayout(header)

        card = QtWidgets.QFrame()
        card.setObjectName("card")
        center_wrap.addWidget(card, 1)

        c = QtWidgets.QVBoxLayout(card)
        c.setContentsMargins(16, 16, 16, 16)
        c.setSpacing(12)

        self.edit_time = QtWidgets.QLineEdit("25:00")
        self.edit_time.setObjectName("timeEdit")
        self.edit_time.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        self.lbl_time = QtWidgets.QLabel("25:00")
        self.lbl_time.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        self.lbl_time.setObjectName("time")
        self.time_stack = QtWidgets.QStackedLayout()
        self.time_stack.addWidget(self.edit_time)
        self.time_stack.addWidget(self.lbl_time)
        c.addLayout(self.time_stack)

        row_ctrl = QtWidgets.QHBoxLayout()
        row_ctrl.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        self.btn_start = QtWidgets.QToolButton()
        self.btn_start.setIcon(self.style().standardIcon(QtWidgets.QStyle.StandardPixmap.SP_MediaPlay))
        self.btn_pause = QtWidgets.QToolButton()
        self.btn_pause.setIcon(self.style().standardIcon(QtWidgets.QStyle.StandardPixmap.SP_MediaPause))
        self.btn_reset = QtWidgets.QToolButton()
        self.btn_reset.setIcon(self.style().standardIcon(QtWidgets.QStyle.StandardPixmap.SP_BrowserReload))
        self.btn_complete = QtWidgets.QToolButton()
        self.btn_complete.setIcon(self.style().standardIcon(QtWidgets.QStyle.StandardPixmap.SP_DialogApplyButton))
        for b in (self.btn_start, self.btn_pause, self.btn_reset, self.btn_complete):
            b.setIconSize(QtCore.QSize(32, 32))
            b.setCursor(QtGui.QCursor(QtCore.Qt.CursorShape.PointingHandCursor))
        row_ctrl.addWidget(self.btn_start)
        row_ctrl.addWidget(self.btn_pause)
        row_ctrl.addWidget(self.btn_reset)
        row_ctrl.addWidget(self.btn_complete)
        c.addLayout(row_ctrl)

        # Right task selection
        right_wrap = QtWidgets.QVBoxLayout()
        outer.addLayout(right_wrap, 1)
        right_wrap.addWidget(QtWidgets.QLabel("Tag:"))
        self.cmb_tag = QtWidgets.QComboBox()
        right_wrap.addWidget(self.cmb_tag)
        right_wrap.addWidget(QtWidgets.QLabel("Proje:"))
        self.cmb_project = QtWidgets.QComboBox()
        right_wrap.addWidget(self.cmb_project)
        self.lst_tasks = QtWidgets.QListWidget()
        right_wrap.addWidget(self.lst_tasks, 1)
        self.btn_refresh = QtWidgets.QToolButton()
        self.btn_refresh.setText("↻")
        self.btn_refresh.setToolTip("Görev listesini yenile")
        right_wrap.addWidget(self.btn_refresh)

        self.btn_refresh.clicked.connect(self.reload_tasks)
        self.edit_time.editingFinished.connect(self._apply_edit_time)
        self.btn_start.clicked.connect(self._start)
        self.btn_pause.clicked.connect(self._pause)
        self.btn_reset.clicked.connect(self._reset)
        self.btn_complete.clicked.connect(self._complete_now)
        self.lst_tasks.itemSelectionChanged.connect(self._on_task_changed)
        self.cmb_tag.currentIndexChanged.connect(self._apply_filters)
        self.cmb_project.currentIndexChanged.connect(self._apply_filters)

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
            QFrame#card {{
                background: {COLOR_SECONDARY_BG};
                border: 1px solid #3a3a3a;
                border-radius: 14px;
            }}
            QLabel#time {{
                font-size: 56px;
                font-weight: 700;
                padding: 12px 0;
            }}
            QLineEdit#timeEdit {{
                background: transparent;
                border: 0;
                font-size: 56px;
                font-weight: 700;
                padding: 12px 0;
                color: {COLOR_TEXT};
            }}
            QPushButton, QToolButton {{
                background: {COLOR_ACCENT};
                border: 0;
                border-radius: 10px;
                padding: 8px 14px;
                color: {COLOR_TEXT};
            }}
            QPushButton:hover, QToolButton:hover {{ opacity: .9; }}
            QComboBox {{
                background: {COLOR_PRIMARY_BG};
                border: 1px solid #3a3a3a;
                border-radius: 8px;
                padding: 6px 8px;
                color: {COLOR_TEXT};
            }}
            QTextEdit#note {{
                background: {COLOR_SECONDARY_BG};
                border: 1px solid #3a3a3a;
                border-radius: 8px;
                padding: 8px;
                color: {COLOR_TEXT};
            }}
        """)

    # ------------------------------ Logic --------------------------------------

    def _normalize_tasks(self, tasks: Any) -> List[Dict[str, Any]]:
        """
        Gelen task liste yapısını normalize eder.
        Kabul ettiği varyasyon örnekleri:
          - [{'id': 1, 'title': 'X', 'tag':'A','project':'P','parent':'Y', ...}, ...]
          - (id, title) tuple listesi
        """
        out: List[Dict[str, Any]] = []
        try:
            for t in tasks or []:
                if isinstance(t, dict):
                    tid = t.get("id") or t.get("task_id")
                    title = t.get("title") or t.get("name") or f"Task {tid}"
                    tag = t.get("tag") or t.get("tag_name") or ""
                    proj = t.get("project") or t.get("project_name") or ""
                    parent = t.get("parent") or t.get("parent_title") or ""
                    status = t.get("status") or t.get("state") or ""
                elif isinstance(t, (tuple, list)) and len(t) >= 2:
                    tid, title = t[0], t[1]
                    tag = proj = parent = status = ""
                else:
                    continue
                meta = ">"
                meta_parts = [p for p in (tag, proj, parent) if p]
                meta = ">".join(meta_parts) if meta_parts else ""
                out.append({"id": tid, "title": title, "meta": meta, "tag": tag, "project": proj, "status": status})
        except Exception:
            pass
        return out

    def _fill_task_list(self, items: List[Dict[str, Any]]):
        cur_id = self._current_task_id
        self.lst_tasks.blockSignals(True)
        self.lst_tasks.clear()
        for t in items:
            it = QtWidgets.QListWidgetItem(t["title"])
            it.setData(QtCore.Qt.ItemDataRole.UserRole, t["id"])
            meta = [p for p in (t.get("tag"), t.get("project")) if p]
            if meta:
                it.setToolTip(" / ".join(meta))
            self.lst_tasks.addItem(it)
        self.lst_tasks.blockSignals(False)
        if cur_id is not None:
            for i in range(self.lst_tasks.count()):
                item = self.lst_tasks.item(i)
                if item.data(QtCore.Qt.ItemDataRole.UserRole) == cur_id:
                    self.lst_tasks.setCurrentItem(item)
                    break

    def _on_task_changed(self):
        items = self.lst_tasks.selectedItems()
        if items:
            self._current_task_id = items[0].data(QtCore.Qt.ItemDataRole.UserRole)
        else:
            self._current_task_id = None

    def _fill_tag_project(self):
        tags = sorted({t.get("tag") for t in self._all_tasks if t.get("tag")})
        projects = sorted({t.get("project") for t in self._all_tasks if t.get("project")})
        self.cmb_tag.blockSignals(True)
        self.cmb_tag.clear()
        self.cmb_tag.addItem("Hepsi", userData=None)
        for tag in tags:
            self.cmb_tag.addItem(tag, userData=tag)
        self.cmb_tag.blockSignals(False)
        self.cmb_project.blockSignals(True)
        self.cmb_project.clear()
        self.cmb_project.addItem("Hepsi", userData=None)
        for proj in projects:
            self.cmb_project.addItem(proj, userData=proj)
        self.cmb_project.blockSignals(False)

    def _apply_filters(self):
        tag = self.cmb_tag.currentData()
        proj = self.cmb_project.currentData()
        filtered = [t for t in self._all_tasks if (tag is None or t.get("tag") == tag) and (proj is None or t.get("project") == proj)]
        self._fill_task_list(filtered)

    def _sync_labels(self):
        m, s = divmod(max(0, self._remaining), 60)
        text = f"{m:02d}:{s:02d}"
        self.lbl_time.setText(text)
        self.edit_time.setText(text)

    def _apply_edit_time(self):
        text = self.edit_time.text().strip()
        try:
            if ":" in text:
                m, s = text.split(":", 1)
                mins = int(m)
                secs = int(s)
            else:
                mins = int(text)
                secs = 0
        except ValueError:
            return
        self._plan_secs = mins * 60 + secs
        if not self._running:
            self._remaining = self._plan_secs
            self._elapsed_before_pause = 0
        self._sync_labels()

    def _start(self):
        if self._running:
            return
        if self._current_task_id is None:
            # Görev seçilmemişse yine de başlatılabilsin ama uyarı ver
            QtWidgets.QToolTip.showText(self.mapToGlobal(QtCore.QPoint(0,0)), "Görev seçilmedi — yine de başlatıldı.")
        self._running = True
        self._tick_start_mono_ms = QtCore.QTime.currentTime().msecsSinceStartOfDay()
        self._timer.start()
        self.started.emit(self._current_task_id, self._plan_secs)
        self._update_ui_state()

    def _pause(self):
        if not self._running:
            return
        self._timer.stop()
        self._running = False
        self.paused.emit(self._current_task_id, self._elapsed_total())
        self._update_ui_state()

    def _reset(self):
        was_running = self._running
        if was_running:
            self._timer.stop()
        self._running = False
        self._elapsed_before_pause = 0
        self._remaining = self._plan_secs
        self._sync_labels()
        self.reset.emit(self._current_task_id)
        self._update_ui_state()

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
        if self._remaining == 0:
            self._timer.stop()
            self._running = False
            self._elapsed_before_pause = 0
            self.completed.emit(self._current_task_id, self._plan_secs)
            self._log_pomodoro()
            self._notify_done()
            self._update_ui_state()

    def _complete_now(self):
        if not self._running:
            return
        self._timer.stop()
        self._running = False
        self._elapsed_before_pause = 0
        self._remaining = 0
        self.completed.emit(self._current_task_id, self._plan_secs)
        self._log_pomodoro()
        self._notify_done()
        self._update_ui_state()

    def _notify_done(self):
        try:
            # Basit bir görsel titreşim/renk animasyonu
            eff = QtWidgets.QGraphicsColorizeEffect(self)
            eff.setColor(QtGui.QColor(COLOR_ACCENT))
            self.setGraphicsEffect(eff)
            QtCore.QTimer.singleShot(600, lambda: self.setGraphicsEffect(None))
        except Exception:
            pass

    def _log_pomodoro(self):
        note = self.note_edit.toPlainText()
        if self._store and hasattr(self._store, "log_pomodoro"):
            try:
                self._store.log_pomodoro(self._current_task_id, note, self._plan_secs)
            except Exception:
                pass
        self.note_edit.clear()

    def _update_ui_state(self):
        if self._running:
            self.time_stack.setCurrentIndex(1)
        else:
            self.time_stack.setCurrentIndex(0)
