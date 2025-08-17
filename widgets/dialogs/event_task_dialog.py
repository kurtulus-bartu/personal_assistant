from __future__ import annotations
from dataclasses import dataclass, field
from typing import Optional, List, Tuple
from PyQt6 import QtCore, QtWidgets
from datetime import datetime, time, timezone

try:
    from theme.colors import COLOR_PRIMARY_BG, COLOR_SECONDARY_BG, COLOR_TEXT
except Exception:
    COLOR_PRIMARY_BG = "#212121"
    COLOR_SECONDARY_BG = "#2d2d2d"
    COLOR_TEXT = "#EEEEEE"
try:
    from dateutil.rrule import rrulestr
except Exception:
    rrulestr = None

ISO_WEEKDAYS = ["MO","TU","WE","TH","FR","SA","SU"]
DEFAULT_RRULE_COUNT = 24  # sonsuz seri yerine makul varsayılan

@dataclass
class ItemModel:
    kind: str                 # "task" or "event"
    id: Optional[int] = None
    title: str = ""
    notes: str = ""
    date: Optional[QtCore.QDate] = None
    start: Optional[QtCore.QTime] = None
    end: Optional[QtCore.QTime] = None
    rrule: str | None = None
    series_id: Optional[int] = None
    task_id: Optional[int] = None  # if event
    parent_id: Optional[int] = None
    tag_id: Optional[int] = None
    project_id: Optional[int] = None
    children: List[Tuple[int, str]] = field(default_factory=list)


class RecurEditor(QtWidgets.QGroupBox):
    """RFC 5545 RRULE üretir: FREQ, INTERVAL, BYDAY, COUNT/UNTIL."""
    rruleChanged = QtCore.pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__("Repeat")
        self.setObjectName("Card")
        self.setCheckable(True)
        self.setChecked(False)

        self.freq = QtWidgets.QComboBox()
        self.freq.addItems(["Daily","Weekly","Monthly","Yearly"])
        self.interval = QtWidgets.QSpinBox(); self.interval.setRange(1, 366); self.interval.setValue(1)

        self.endNever = QtWidgets.QRadioButton("Never")
        self.endOn    = QtWidgets.QRadioButton("On")
        self.endAfter = QtWidgets.QRadioButton("After")
        self.endNever.setChecked(True)

        self.untilDate = QtWidgets.QDateEdit(); self.untilDate.setCalendarPopup(True)
        self.untilDate.setDate(QtCore.QDate.currentDate())
        self.countSpin = QtWidgets.QSpinBox(); self.countSpin.setRange(1, 1000); self.countSpin.setValue(10)

        self.weekdayBox = QtWidgets.QWidget()
        self._wdChecks = []
        wdLay = QtWidgets.QHBoxLayout(self.weekdayBox); wdLay.setContentsMargins(0,0,0,0)
        for label in ["Mon","Tue","Wed","Thu","Fri","Sat","Sun"]:
            cb = QtWidgets.QCheckBox(label)
            self._wdChecks.append(cb)
            wdLay.addWidget(cb)

        self.postponeBtn = QtWidgets.QPushButton("Postpone to Next")
        self.postponeBtn.setVisible(False)

        grid = QtWidgets.QGridLayout(self)
        grid.setContentsMargins(12,12,12,12)
        r = 0
        grid.addWidget(QtWidgets.QLabel("Frequency"), r, 0)
        grid.addWidget(self.freq, r, 1)
        r += 1
        grid.addWidget(QtWidgets.QLabel("Interval"), r, 0)
        grid.addWidget(self.interval, r, 1)
        r += 1
        grid.addWidget(QtWidgets.QLabel("Weekdays"), r, 0)
        grid.addWidget(self.weekdayBox, r, 1)
        r += 1

        endRow = QtWidgets.QHBoxLayout()
        endRow.addWidget(self.endNever)
        endRow.addWidget(self.endOn)
        endRow.addWidget(self.untilDate)
        endRow.addWidget(self.endAfter)
        endRow.addWidget(self.countSpin)
        endRow.addStretch(1)
        grid.addLayout(endRow, r, 0, 1, 2)
        r += 1

        grid.addWidget(self.postponeBtn, r, 0, 1, 2)

        self.freq.currentTextChanged.connect(self._on_freq_changed)
        for cb in self._wdChecks:
            cb.toggled.connect(self._emit_rrule)
        for w in (self.interval, self.untilDate, self.countSpin, self):
            try:
                w.valueChanged.connect(self._emit_rrule)
            except Exception:
                pass
        self.endNever.toggled.connect(self._emit_rrule)
        self.endOn.toggled.connect(self._emit_rrule)
        self.endAfter.toggled.connect(self._emit_rrule)
        self.toggled.connect(self._emit_rrule)

        self._on_freq_changed(self.freq.currentText())
        self.setStyleSheet(
            """
        QGroupBox#Card {
          border: 1px solid #333; border-radius: 12px; margin-top: 8px;
        }
        QGroupBox#Card::title { subcontrol-origin: margin; left: 12px; padding: 0 4px; }
        """
        )

    def _on_freq_changed(self, txt):
        self.weekdayBox.setEnabled(txt == "Weekly")
        self._emit_rrule()

    def _selected_byday(self):
        idxs = [i for i, cb in enumerate(self._wdChecks) if cb.isChecked()]
        return [ISO_WEEKDAYS[i] for i in idxs]

    def get_rrule(self, dtstart: QtCore.QDateTime | None) -> str | None:
        if not self.isChecked():
            return None

        freq_map = {"Daily":"DAILY","Weekly":"WEEKLY","Monthly":"MONTHLY","Yearly":"YEARLY"}
        parts = [f"FREQ={freq_map[self.freq.currentText()]}", f"INTERVAL={self.interval.value()}"]

        if self.freq.currentText() == "Weekly":
            byday = self._selected_byday()
            if byday:
                parts.append("BYDAY=" + ",".join(byday))
            else:
                if dtstart:
                    wd = dtstart.date().dayOfWeek()
                    parts.append("BYDAY=" + ISO_WEEKDAYS[wd-1])

        if self.endOn.isChecked():
            qd = self.untilDate.date()
            dt_local = datetime(qd.year(), qd.month(), qd.day(), 23, 59, 59)
            dt_utc = dt_local.astimezone(timezone.utc)
            parts.append("UNTIL=" + dt_utc.strftime("%Y%m%dT%H%M%SZ"))
        elif self.endAfter.isChecked():
            parts.append(f"COUNT={self.countSpin.value()}")
        elif self.endNever.isChecked() and self.freq.currentText() in ("Daily", "Weekly"):
            parts.append(f"COUNT={DEFAULT_RRULE_COUNT}")

        return "RRULE:" + ";".join(parts)

    def set_from_rrule(self, rrule_str: str | None):
        if not rrule_str:
            self.setChecked(False)
            return
        self.setChecked(True)
        core = rrule_str.replace("RRULE:", "")
        kv = {}
        for part in core.split(";"):
            if "=" in part:
                k, v = part.split("=",1); kv[k.upper()] = v

        inv = {v:k for k,v in {"Daily":"DAILY","Weekly":"WEEKLY","Monthly":"MONTHLY","Yearly":"YEARLY"}.items()}
        self.freq.setCurrentText(inv.get(kv.get("FREQ","DAILY"), "Daily"))
        self.interval.setValue(int(kv.get("INTERVAL","1")))

        if "BYDAY" in kv:
            by = kv["BYDAY"].split(",")
            for i, code in enumerate(ISO_WEEKDAYS):
                self._wdChecks[i].setChecked(code in by)

        if "UNTIL" in kv:
            self.endOn.setChecked(True)
            s = kv["UNTIL"][:8]
            self.untilDate.setDate(QtCore.QDate.fromString(s, "yyyyMMdd"))
        elif "COUNT" in kv:
            self.endAfter.setChecked(True)
            self.countSpin.setValue(int(kv["COUNT"]))
        else:
            self.endNever.setChecked(True)

    def _emit_rrule(self):
        r = self.get_rrule(None)
        self.postponeBtn.setVisible(self.isChecked())
        if r:
            self.rruleChanged.emit(r)

class EventTaskDialog(QtWidgets.QDialog):
    saved = QtCore.pyqtSignal(object)    # ItemModel
    deleted = QtCore.pyqtSignal(object)  # ItemModel
    openTaskRequested = QtCore.pyqtSignal(int)

    def __init__(self, model: ItemModel, parent=None,
                 parent_options: List[Tuple[int, str]] | None = None,
                 tag_options: List[Tuple[int, str]] | None = None,
                 project_options: List[Tuple[int, str, int | None]] | None = None):
        super().__init__(parent)
        self.setWindowTitle("Edit")
        self.setModal(True)
        self._model = model
        self._parent_options = parent_options or []
        self._tag_options = tag_options or []
        # project_options: (project_id, name, tag_id or None)
        self._project_options: List[Tuple[int, str, int | None]] = project_options or []
        self.store = getattr(parent, "store", None)
        self.setMinimumWidth(480)

        main = QtWidgets.QVBoxLayout(self)
        main.setContentsMargins(14, 14, 14, 14)
        main.setSpacing(10)

        body = QtWidgets.QHBoxLayout()
        body.setSpacing(10)
        main.addLayout(body, 1)

        left_w = QtWidgets.QWidget(); right_w = QtWidgets.QWidget()
        left = QtWidgets.QVBoxLayout(left_w); left.setSpacing(10)
        right = QtWidgets.QVBoxLayout(right_w); right.setSpacing(10)
        body.addWidget(left_w, 1)
        body.addWidget(right_w, 1)

        # --- Right column: Pomodoro geçmişi ---
        right_col = QtWidgets.QFrame()
        right_col.setObjectName("pomopane")
        rlo = QtWidgets.QVBoxLayout(right_col); rlo.setContentsMargins(12,12,12,12); rlo.setSpacing(8)

        lbl_hist = QtWidgets.QLabel("Pomodorolar")
        lbl_hist.setStyleSheet("font-weight:600;")
        rlo.addWidget(lbl_hist)

        self.list_pomo = QtWidgets.QListWidget()
        self.list_pomo.setSelectionMode(QtWidgets.QAbstractItemView.SelectionMode.SingleSelection)
        rlo.addWidget(self.list_pomo, 1)

        lbl_note = QtWidgets.QLabel("Seçili pomodoro notu")
        rlo.addWidget(lbl_note)
        self.view_pomo_note = QtWidgets.QTextEdit()
        self.view_pomo_note.setReadOnly(True)
        rlo.addWidget(self.view_pomo_note, 1)

        body.addWidget(right_col, 1)
        body.setStretch(0, 1); body.setStretch(1, 1); body.setStretch(2, 1)

        right_col.setStyleSheet(f"""
            QFrame#pomopane {{
                background: {COLOR_PRIMARY_BG};
                border: 1px solid #3a3a3a;
                border-radius: 14px;
                color: {COLOR_TEXT};
            }}
            QListWidget, QTextEdit {{
                background: {COLOR_SECONDARY_BG};
                border: 1px solid #3a3a3a;
                border-radius: 10px;
                color: {COLOR_TEXT};
            }}
        """)

        # Title
        self.edt_title = QtWidgets.QLineEdit()
        self.edt_title.setPlaceholderText("Title")
        left.addWidget(self.edt_title)

        # Notes
        self.edt_notes = QtWidgets.QPlainTextEdit()
        self.edt_notes.setPlaceholderText("Notes…")
        self.edt_notes.setFixedHeight(100)
        left.addWidget(self.edt_notes)

        # Linked tasks
        self._build_linked_tasks_ui()
        left.addWidget(self.linkedGroup, 1)

        # Tag/Project/Parent selection (aligned)
        form = QtWidgets.QFormLayout(); form.setHorizontalSpacing(8)
        lbl_w = 60

        self.cmb_tag = QtWidgets.QComboBox(); self.cmb_tag.addItem("None", None)
        for tid, name in self._tag_options:
            self.cmb_tag.addItem(name, tid)
        lbl = QtWidgets.QLabel("Tag"); lbl.setFixedWidth(lbl_w)
        form.addRow(lbl, self.cmb_tag)

        self.cmb_project = QtWidgets.QComboBox(); self.cmb_project.addItem("None", None)
        for pid, name, _ in self._project_options:
            self.cmb_project.addItem(name, pid)
        lbl = QtWidgets.QLabel("Project"); lbl.setFixedWidth(lbl_w)
        form.addRow(lbl, self.cmb_project)

        self.cmb_parent = QtWidgets.QComboBox(); self.cmb_parent.addItem("None", None)
        for pid, title in self._parent_options:
            self.cmb_parent.addItem(title, pid)
        lbl = QtWidgets.QLabel("Parent"); lbl.setFixedWidth(lbl_w)
        form.addRow(lbl, self.cmb_parent)

        right.addLayout(form)

        right.addStretch(1)

        # Date + time row
        row = QtWidgets.QHBoxLayout()
        row.setSpacing(8)
        self.date_edit = QtWidgets.QDateEdit(calendarPopup=True)
        self.date_edit.setDisplayFormat("yyyy-MM-dd")
        self.chk_time = QtWidgets.QCheckBox("Has time (event)")
        self.start_edit = QtWidgets.QTimeEdit()
        self.end_edit = QtWidgets.QTimeEdit()
        self.start_edit.setDisplayFormat("HH:mm")
        self.end_edit.setDisplayFormat("HH:mm")
        row.addWidget(QtWidgets.QLabel("Date"))
        row.addWidget(self.date_edit)
        row.addSpacing(12)
        row.addWidget(self.chk_time)
        row.addSpacing(12)
        row.addWidget(QtWidgets.QLabel("Start"))
        row.addWidget(self.start_edit)
        row.addWidget(QtWidgets.QLabel("End"))
        row.addWidget(self.end_edit, 1)
        right.addLayout(row)

        # Recurrence editor
        self.recur = RecurEditor()
        self.recur.rruleChanged.connect(self._on_rrule_changed)
        right.addWidget(self.recur)

        # Footer buttons
        footer = QtWidgets.QHBoxLayout()
        self.deleteBtn = QtWidgets.QPushButton("Delete")
        self.saveBtn = QtWidgets.QPushButton("Save")
        self.cancelBtn = QtWidgets.QPushButton("Cancel")
        footer.addWidget(self.deleteBtn)
        footer.addStretch(1)
        footer.addWidget(self.cancelBtn)
        footer.addWidget(self.saveBtn)
        main.addLayout(footer)

        # Wire
        self.chk_time.toggled.connect(self._on_has_time_toggled)
        self.cmb_tag.currentIndexChanged.connect(self._on_tag_changed)
        self.deleteBtn.clicked.connect(self._on_delete)
        self.cancelBtn.clicked.connect(self.reject)
        self.saveBtn.clicked.connect(self._on_save)
        self.recur.postponeBtn.clicked.connect(self._postpone_to_next)
        self.list_pomo.itemSelectionChanged.connect(self._on_pomo_selected)

        self._load_model(model)

    def _build_linked_tasks_ui(self):
        self.linkedGroup = QtWidgets.QGroupBox("Linked Tasks")
        self.linkedList = QtWidgets.QListWidget()
        self.linkedList.itemActivated.connect(self._on_link_activated)
        lay = QtWidgets.QVBoxLayout(self.linkedGroup)
        lay.setContentsMargins(8,8,8,8)
        lay.addWidget(self.linkedList)

    def populate_linked_tasks(self, tasks):
        self.linkedList.clear()
        for t in tasks:
            it = QtWidgets.QListWidgetItem(str(t['title']))
            it.setData(QtCore.Qt.ItemDataRole.UserRole, int(t['id']))
            self.linkedList.addItem(it)

    def _on_link_activated(self, item):
        tid = item.data(QtCore.Qt.ItemDataRole.UserRole)
        if tid:
            self.openTaskRequested.emit(int(tid))

    def _load_pomodoro_history(self, task_id: int):
        self.list_pomo.clear()
        try:
            sessions = self.store.get_pomodoro_sessions(task_id)
        except Exception:
            sessions = []

        for s in sessions:
            try:
                ended = datetime.fromisoformat(s["ended_at"])
            except Exception:
                ended = None
            dur_m = int(max(1, s["actual_secs"])) // 60
            plan_m = int(max(1, s["planned_secs"])) // 60
            title = f"{ended.strftime('%d %b %H:%M') if ended else s['ended_at']} — {dur_m}m (plan:{plan_m}m)"
            it = QtWidgets.QListWidgetItem(title)
            it.setData(QtCore.Qt.ItemDataRole.UserRole, s)
            self.list_pomo.addItem(it)

    def showEvent(self, ev):
        super().showEvent(ev)
        if getattr(self, "_model", None) and getattr(self._model, "id", None):
            self._load_pomodoro_history(self._model.id)

    def _on_pomo_selected(self):
        it = self.list_pomo.currentItem()
        s = it.data(QtCore.Qt.ItemDataRole.UserRole) if it else None
        self.view_pomo_note.setPlainText((s or {}).get("note", ""))

    def _on_rrule_changed(self, r):
        self._model.rrule = r

    def _on_has_time_toggled(self, checked: bool):
        self.start_edit.setEnabled(checked); self.end_edit.setEnabled(checked)

    def _load_model(self, m: ItemModel):
        self.edt_title.setText(m.title or "")
        self.edt_notes.setPlainText(m.notes or "")
        qd = m.date or QtCore.QDate.currentDate()
        self.date_edit.setDate(qd)
        has_time = (m.start is not None and m.end is not None) or (m.kind == "event")
        self.chk_time.setChecked(has_time)
        if m.start: self.start_edit.setTime(m.start)
        if m.end: self.end_edit.setTime(m.end)
        self.recur.set_from_rrule(m.rrule)
        if m.parent_id is not None:
            idx = self.cmb_parent.findData(int(m.parent_id))
            if idx != -1:
                self.cmb_parent.setCurrentIndex(idx)
        else:
            self.cmb_parent.setCurrentIndex(0)
        if m.tag_id is not None:
            idx = self.cmb_tag.findData(int(m.tag_id))
            if idx != -1:
                self.cmb_tag.setCurrentIndex(idx)
        else:
            self.cmb_tag.setCurrentIndex(0)

        # refresh projects according to tag selection
        self._refresh_project_combo(m.tag_id)
        if m.project_id is not None:
            idx = self.cmb_project.findData(int(m.project_id))
            if idx != -1:
                self.cmb_project.setCurrentIndex(idx)
        else:
            self.cmb_project.setCurrentIndex(0)

    def _on_delete(self):
        self.deleted.emit(self._model)
        self.accept()

    def _on_save(self):
        m = ItemModel(kind=self._model.kind, id=self._model.id, task_id=self._model.task_id)
        m.title = self.edt_title.text().strip()
        m.notes = self.edt_notes.toPlainText().strip()
        m.date = self.date_edit.date()
        if self.chk_time.isChecked():
            m.start = self.start_edit.time()
            m.end = self.end_edit.time()
        else:
            m.start = None; m.end = None
        start_dt = self._get_start_qdatetime()
        m.rrule = self.recur.get_rrule(start_dt)
        data = self.cmb_parent.currentData()
        m.parent_id = int(data) if data is not None else None
        data = self.cmb_tag.currentData()
        m.tag_id = int(data) if data is not None else None
        data = self.cmb_project.currentData()
        m.project_id = int(data) if data is not None else None
        m.children = list(self._model.children)
        self.saved.emit(m)
        self.accept()

    def _on_tag_changed(self, idx: int):
        data = self.cmb_tag.itemData(idx)
        tag_id = int(data) if data is not None else None
        self._refresh_project_combo(tag_id)

    def _refresh_project_combo(self, tag_id: int | None):
        current = self.cmb_project.currentData()
        self.cmb_project.blockSignals(True)
        self.cmb_project.clear()
        self.cmb_project.addItem("None", None)
        for pid, name, p_tag in self._project_options:
            if tag_id is None or (p_tag is not None and int(p_tag) == int(tag_id)):
                self.cmb_project.addItem(name, pid)
        if current is not None:
            idx = self.cmb_project.findData(current)
            if idx != -1:
                self.cmb_project.setCurrentIndex(idx)
        self.cmb_project.blockSignals(False)

    def _get_start_qdatetime(self) -> QtCore.QDateTime | None:
        if not self.date_edit.date().isValid():
            return None
        t = self.start_edit.time() if self.chk_time.isChecked() else QtCore.QTime(0,0)
        return QtCore.QDateTime(self.date_edit.date(), t)

    def _set_start_end_from_python_dt(self, dt: datetime):
        qd = QtCore.QDate(dt.year, dt.month, dt.day)
        self.date_edit.setDate(qd)
        if self.chk_time.isChecked():
            st = QtCore.QTime(dt.hour, dt.minute)
            self.start_edit.setTime(st)
            duration = 0
            if self._model.start and self._model.end:
                duration = QtCore.QTime(0,0).secsTo(self._model.end) - QtCore.QTime(0,0).secsTo(self._model.start)
            else:
                duration = self.start_edit.time().secsTo(self.end_edit.time())
            self.end_edit.setTime(st.addSecs(duration))

    def _postpone_to_next(self):
        if not self._model.rrule or not rrulestr:
            return
        start_dt = self._get_start_qdatetime()
        if not start_dt:
            return
        dtstart_py = start_dt.toPyDateTime()
        rule = rrulestr(self._model.rrule.replace("RRULE:", ""), dtstart=dtstart_py)
        next_dt = rule.after(dtstart_py, inc=False)
        if next_dt:
            self._set_start_end_from_python_dt(next_dt)
