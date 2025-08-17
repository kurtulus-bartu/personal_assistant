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

        self._build_ui()
        self._apply_styles()
        self._sync_labels()

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
        items = []
        if self._task_fetcher:
            try:
                items = self._task_fetcher() or []
            except Exception:
                items = []
        self._fill_task_combo(items)

    # ------------------------------ UI Build -----------------------------------

    def _build_ui(self):
        self.setObjectName("PomodoroPage")
        self.setAutoFillBackground(True)

        outer = QtWidgets.QVBoxLayout(self)
        outer.setContentsMargins(12, 12, 12, 12)
        outer.setSpacing(12)

        # Header
        header = QtWidgets.QHBoxLayout()
        lbl_title = QtWidgets.QLabel("Pomodoro")
        lbl_title.setObjectName("title")
        header.addWidget(lbl_title, 1)

        # Task selector (planner benzeri)
        self.cmb_task = QtWidgets.QComboBox()
        self.cmb_task.setMinimumWidth(280)
        self.cmb_task.setSizeAdjustPolicy(QtWidgets.QComboBox.SizeAdjustPolicy.AdjustToContents)
        self.btn_refresh = QtWidgets.QToolButton()
        self.btn_refresh.setText("↻")
        self.btn_refresh.setToolTip("Görev listesini yenile")

        task_row = QtWidgets.QHBoxLayout()
        task_row.addWidget(QtWidgets.QLabel("Görev:"))
        task_row.addWidget(self.cmb_task, 1)
        task_row.addWidget(self.btn_refresh, 0)

        header_wrap = QtWidgets.QWidget()
        hw_l = QtWidgets.QVBoxLayout(header_wrap)
        hw_l.setContentsMargins(0,0,0,0)
        hw_l.setSpacing(6)
        hw_l.addLayout(header)
        hw_l.addLayout(task_row)

        outer.addWidget(header_wrap)

        # Card
        card = QtWidgets.QFrame()
        card.setObjectName("card")
        outer.addWidget(card, 1)

        c = QtWidgets.QVBoxLayout(card)
        c.setContentsMargins(16, 16, 16, 16)
        c.setSpacing(12)

        # Time display
        self.lbl_time = QtWidgets.QLabel("--:--")
        self.lbl_time.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        self.lbl_time.setObjectName("time")
        c.addWidget(self.lbl_time)

        # Duration controls
        row_dur = QtWidgets.QHBoxLayout()
        row_dur.addWidget(QtWidgets.QLabel("Süre (dk):"))
        self.spin_minutes = QtWidgets.QSpinBox()
        self.spin_minutes.setRange(1, 180)
        self.spin_minutes.setValue(25)
        row_dur.addWidget(self.spin_minutes)

        self.btn_apply = QtWidgets.QPushButton("Uygula")
        row_dur.addWidget(self.btn_apply)
        row_dur.addStretch(1)
        c.addLayout(row_dur)

        # Controls
        row_ctrl = QtWidgets.QHBoxLayout()
        self.btn_start = QtWidgets.QPushButton("Başlat")
        self.btn_pause = QtWidgets.QPushButton("Durdur")
        self.btn_reset = QtWidgets.QPushButton("Sıfırla")

        for b in (self.btn_start, self.btn_pause, self.btn_reset):
            b.setFixedHeight(40)
            b.setCursor(QtGui.QCursor(QtCore.Qt.CursorShape.PointingHandCursor))
        row_ctrl.addWidget(self.btn_start)
        row_ctrl.addWidget(self.btn_pause)
        row_ctrl.addWidget(self.btn_reset)
        c.addLayout(row_ctrl)

        # Wire
        self.btn_refresh.clicked.connect(self.reload_tasks)
        self.btn_apply.clicked.connect(self._apply_minutes)
        self.btn_start.clicked.connect(self._start)
        self.btn_pause.clicked.connect(self._pause)
        self.btn_reset.clicked.connect(self._reset)

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
            QPushButton {{
                background: {COLOR_ACCENT};
                border: 0;
                border-radius: 10px;
                padding: 8px 14px;
                color: {COLOR_TEXT};
            }}
            QPushButton:hover {{ opacity: .9; }}
            QComboBox {{
                background: {COLOR_PRIMARY_BG};
                border: 1px solid #3a3a3a;
                border-radius: 8px;
                padding: 6px 8px;
                color: {COLOR_TEXT};
            }}
            QSpinBox {{
                background: {COLOR_PRIMARY_BG};
                border: 1px solid #3a3a3a;
                border-radius: 8px;
                padding: 4px 8px;
                color: {COLOR_TEXT};
                min-width: 72px;
            }}
            QToolButton {{
                background: {COLOR_PRIMARY_BG};
                border: 1px solid #3a3a3a;
                border-radius: 8px;
                padding: 4px 8px;
                color: {COLOR_TEXT};
                min-width: 32px;
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
                elif isinstance(t, (tuple, list)) and len(t) >= 2:
                    tid, title = t[0], t[1]
                    tag = proj = parent = ""
                else:
                    continue
                meta = ">"
                meta_parts = [p for p in (tag, proj, parent) if p]
                meta = ">".join(meta_parts) if meta_parts else ""
                out.append({"id": tid, "title": title, "meta": meta})
        except Exception:
            pass
        return out

    def _fill_task_combo(self, items: List[Dict[str, Any]]):
        cur_id = self._current_task_id
        self.cmb_task.blockSignals(True)
        self.cmb_task.clear()
        self.cmb_task.addItem("— Görev seç —", userData=None)
        for t in items:
            text = t["title"] if not t.get("meta") else f'{t["title"]} ({t["meta"]})'
            self.cmb_task.addItem(text, userData=t["id"])
        self.cmb_task.blockSignals(False)

        # Try restore selection
        if cur_id is not None:
            idx = self.cmb_task.findData(cur_id)
            if idx != -1:
                self.cmb_task.setCurrentIndex(idx)

        self.cmb_task.currentIndexChanged.connect(self._on_task_changed)

    def _on_task_changed(self, _idx: int):
        tid = self.cmb_task.currentData()
        self._current_task_id = tid

    def _sync_labels(self):
        m, s = divmod(max(0, self._remaining), 60)
        self.lbl_time.setText(f"{m:02d}:{s:02d}")

    def _apply_minutes(self):
        mins = int(self.spin_minutes.value())
        self._plan_secs = mins * 60
        # Eğer çalışmıyorsa direkt uygula; çalışıyorsa sadece planı güncelle
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

    def _pause(self):
        if not self._running:
            return
        self._timer.stop()
        self._running = False
        self.paused.emit(self._current_task_id, self._elapsed_total())

    def _reset(self):
        was_running = self._running
        if was_running:
            self._timer.stop()
        self._running = False
        self._elapsed_before_pause = 0
        self._remaining = self._plan_secs
        self._sync_labels()
        self.reset.emit(self._current_task_id)

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
            # elapsed'i sıfırla (plan tamamlandı)
            self._elapsed_before_pause = 0
            self.completed.emit(self._current_task_id, self._plan_secs)
            # Görsel bildirim
            self._notify_done()

    def _notify_done(self):
        try:
            # Basit bir görsel titreşim/renk animasyonu
            eff = QtWidgets.QGraphicsColorizeEffect(self)
            eff.setColor(QtGui.QColor(COLOR_ACCENT))
            self.setGraphicsEffect(eff)
            QtCore.QTimer.singleShot(600, lambda: self.setGraphicsEffect(None))
        except Exception:
            pass
