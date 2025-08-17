from __future__ import annotations
from dataclasses import dataclass
from typing import Optional
from datetime import datetime

from PyQt6 import QtCore, QtWidgets

from theme.colors import COLOR_PRIMARY_BG, COLOR_SECONDARY_BG, COLOR_TEXT


@dataclass
class ItemModel:
    kind: str  # "task" or "event"
    id: Optional[int] = None
    title: str = ""
    notes: str = ""
    date: Optional[QtCore.QDate] = None
    start: Optional[QtCore.QTime] = None
    end: Optional[QtCore.QTime] = None
    rrule: str | None = None
    task_id: Optional[int] = None  # if event


class EventTaskDialog(QtWidgets.QDialog):
    saved = QtCore.pyqtSignal(object)  # ItemModel
    deleted = QtCore.pyqtSignal(object)  # ItemModel

    def __init__(self, model: ItemModel, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Edit")
        self.setModal(True)
        self.model = model
        self.setMinimumWidth(640)

        main_hbox = QtWidgets.QHBoxLayout(self)
        main_hbox.setContentsMargins(14, 14, 14, 14)
        main_hbox.setSpacing(10)

        left_col = QtWidgets.QVBoxLayout()
        left_col.setSpacing(10)
        main_hbox.addLayout(left_col, 2)

        # Title
        self.edt_title = QtWidgets.QLineEdit()
        self.edt_title.setPlaceholderText("Title")
        left_col.addWidget(self.edt_title)

        # Notes
        self.edt_notes = QtWidgets.QPlainTextEdit()
        self.edt_notes.setPlaceholderText("Notes…")
        self.edt_notes.setFixedHeight(100)
        left_col.addWidget(self.edt_notes)

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
        left_col.addLayout(row)

        # Recurrence
        rec_row = QtWidgets.QHBoxLayout()
        rec_row.setSpacing(8)
        self.cmb_recur = QtWidgets.QComboBox()
        self.cmb_recur.addItems(["None", "Daily", "Weekly", "Monthly", "Custom (RRULE)"])
        self.edt_rrule = QtWidgets.QLineEdit()
        self.edt_rrule.setPlaceholderText("RRULE=FREQ=WEEKLY;INTERVAL=1;BYDAY=MO,WE")
        self.edt_rrule.setEnabled(False)
        rec_row.addWidget(QtWidgets.QLabel("Repeat"))
        rec_row.addWidget(self.cmb_recur, 1)
        rec_row.addWidget(self.edt_rrule, 2)
        left_col.addLayout(rec_row)

        # Buttons
        btn_row = QtWidgets.QHBoxLayout()
        btn_row.addStretch(1)
        self.btn_delete = QtWidgets.QPushButton("Delete")
        self.btn_cancel = QtWidgets.QPushButton("Cancel")
        self.btn_save = QtWidgets.QPushButton("Save")
        btn_row.addWidget(self.btn_delete)
        btn_row.addWidget(self.btn_cancel)
        btn_row.addWidget(self.btn_save)
        left_col.addLayout(btn_row)

        # --- Right column: Pomodoro geçmişi ---
        right_col = QtWidgets.QFrame()
        right_col.setObjectName("pomopane")
        rlo = QtWidgets.QVBoxLayout(right_col)
        rlo.setContentsMargins(12, 12, 12, 12)
        rlo.setSpacing(8)

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

        right_col.setStyleSheet(
            f"""
            QFrame#pomopane {{
                background: {COLOR_SECONDARY_BG};
                border: 1px solid #3a3a3a;
                border-radius: 14px;
                color: {COLOR_TEXT};
            }}
            QListWidget, QTextEdit {{
                background: {COLOR_PRIMARY_BG};
                border: 1px solid #3a3a3a;
                border-radius: 10px;
                color: {COLOR_TEXT};
            }}
            """
        )

        main_hbox.addWidget(right_col, 1)

        # Wire
        self.cmb_recur.currentIndexChanged.connect(self._on_recur_changed)
        self.chk_time.toggled.connect(self._on_has_time_toggled)
        self.btn_delete.clicked.connect(self._on_delete)
        self.btn_cancel.clicked.connect(self.reject)
        self.btn_save.clicked.connect(self._on_save)
        self.list_pomo.itemSelectionChanged.connect(self._on_pomo_selected)

        self._load_model(model)

    def _on_recur_changed(self, idx: int):
        self.edt_rrule.setEnabled(self.cmb_recur.currentText() == "Custom (RRULE)")

    def _on_has_time_toggled(self, checked: bool):
        self.start_edit.setEnabled(checked)
        self.end_edit.setEnabled(checked)

    def _load_model(self, m: ItemModel):
        self.edt_title.setText(m.title or "")
        self.edt_notes.setPlainText(m.notes or "")
        qd = m.date or QtCore.QDate.currentDate()
        self.date_edit.setDate(qd)
        has_time = (m.start is not None and m.end is not None) or (m.kind == "event")
        self.chk_time.setChecked(has_time)
        if m.start:
            self.start_edit.setTime(m.start)
        if m.end:
            self.end_edit.setTime(m.end)
        if m.rrule:
            self.cmb_recur.setCurrentText("Custom (RRULE)")
            self.edt_rrule.setText(m.rrule)
            self.edt_rrule.setEnabled(True)
        else:
            self.cmb_recur.setCurrentText("None")

    def _on_delete(self):
        self.deleted.emit(self.model)
        self.accept()

    def _on_save(self):
        m = ItemModel(kind=self.model.kind, id=self.model.id, task_id=self.model.task_id)
        m.title = self.edt_title.text().strip()
        m.notes = self.edt_notes.toPlainText().strip()
        m.date = self.date_edit.date()
        if self.chk_time.isChecked():
            m.start = self.start_edit.time()
            m.end = self.end_edit.time()
        else:
            m.start = None
            m.end = None
        sel = self.cmb_recur.currentText()
        if sel == "None":
            m.rrule = None
        elif sel == "Daily":
            m.rrule = "RRULE=FREQ=DAILY;INTERVAL=1"
        elif sel == "Weekly":
            m.rrule = "RRULE=FREQ=WEEKLY;INTERVAL=1"
        elif sel == "Monthly":
            m.rrule = "RRULE=FREQ=MONTHLY;INTERVAL=1"
        else:
            m.rrule = self.edt_rrule.text().strip() or None
        self.saved.emit(m)
        self.accept()

    # ---------- Pomodoro history ----------
    def _load_pomodoro_history(self, task_id: int):
        self.list_pomo.clear()
        try:
            sessions = self.store.get_pomodoro_sessions(task_id)  # type: ignore[attr-defined]
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

    def showEvent(self, ev):  # type: ignore[override]
        super().showEvent(ev)
        if getattr(self, "model", None) and getattr(self.model, "id", None):
            self._load_pomodoro_history(self.model.id)  # type: ignore[arg-type]

    def _on_pomo_selected(self):
        it = self.list_pomo.currentItem()
        s = it.data(QtCore.Qt.ItemDataRole.UserRole) if it else None
        self.view_pomo_note.setPlainText((s or {}).get("note", ""))

