from __future__ import annotations
from dataclasses import dataclass, field
from typing import Optional, List, Tuple
from PyQt6 import QtCore, QtWidgets

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

class EventTaskDialog(QtWidgets.QDialog):
    saved = QtCore.pyqtSignal(object)    # ItemModel
    deleted = QtCore.pyqtSignal(object)  # ItemModel
    postponed = QtCore.pyqtSignal(object)  # ItemModel

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
        self.setMinimumWidth(480)

        main = QtWidgets.QVBoxLayout(self)
        main.setContentsMargins(14, 14, 14, 14)
        main.setSpacing(10)

        body = QtWidgets.QHBoxLayout()
        body.setSpacing(10)
        main.addLayout(body, 1)

        left = QtWidgets.QVBoxLayout()
        left.setSpacing(10)
        right = QtWidgets.QVBoxLayout()
        right.setSpacing(10)
        body.addLayout(left, 1)
        body.addLayout(right, 1)

        # Title
        self.edt_title = QtWidgets.QLineEdit()
        self.edt_title.setPlaceholderText("Title")
        left.addWidget(self.edt_title)

        # Notes
        self.edt_notes = QtWidgets.QPlainTextEdit()
        self.edt_notes.setPlaceholderText("Notes…")
        self.edt_notes.setFixedHeight(100)
        left.addWidget(self.edt_notes)

        # Subtask list
        left.addWidget(QtWidgets.QLabel("Linked Tasks"))
        self.lst_children = QtWidgets.QListWidget()
        left.addWidget(self.lst_children, 1)

        # Tag selection
        tag_row = QtWidgets.QHBoxLayout()
        tag_row.setSpacing(8)
        self.cmb_tag = QtWidgets.QComboBox()
        self.cmb_tag.addItem("None", None)
        for tid, name in self._tag_options:
            self.cmb_tag.addItem(name, tid)
        tag_row.addWidget(QtWidgets.QLabel("Tag"))
        tag_row.addWidget(self.cmb_tag, 1)
        right.addLayout(tag_row)

        # Project selection
        proj_row = QtWidgets.QHBoxLayout()
        proj_row.setSpacing(8)
        self.cmb_project = QtWidgets.QComboBox()
        self.cmb_project.addItem("None", None)
        for pid, name, _ in self._project_options:
            self.cmb_project.addItem(name, pid)
        proj_row.addWidget(QtWidgets.QLabel("Project"))
        proj_row.addWidget(self.cmb_project, 1)
        right.addLayout(proj_row)

        # Parent selection
        parent_row = QtWidgets.QHBoxLayout()
        parent_row.setSpacing(8)
        self.cmb_parent = QtWidgets.QComboBox()
        self.cmb_parent.addItem("None", None)
        for pid, title in self._parent_options:
            self.cmb_parent.addItem(title, pid)
        parent_row.addWidget(QtWidgets.QLabel("Parent"))
        parent_row.addWidget(self.cmb_parent, 1)
        right.addLayout(parent_row)

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

        # Recurrence
        rec_row = QtWidgets.QHBoxLayout()
        rec_row.setSpacing(8)
        self.cmb_recur = QtWidgets.QComboBox()
        self.cmb_recur.addItems(["None", "Weekdays", "Daily", "Weekly", "Custom"])
        self.spn_count = QtWidgets.QSpinBox()
        self.spn_count.setRange(1, 999)
        self.spn_count.setEnabled(False)
        self.until_edit = QtWidgets.QDateEdit(calendarPopup=True)
        self.until_edit.setDisplayFormat("yyyy-MM-dd")
        self.until_edit.setEnabled(False)
        rec_row.addWidget(QtWidgets.QLabel("Repeat"))
        rec_row.addWidget(self.cmb_recur, 1)
        rec_row.addWidget(QtWidgets.QLabel("Count"))
        rec_row.addWidget(self.spn_count)
        rec_row.addWidget(QtWidgets.QLabel("Until"))
        rec_row.addWidget(self.until_edit)
        right.addLayout(rec_row)

        # Buttons
        btn_row = QtWidgets.QHBoxLayout()
        btn_row.addStretch(1)
        self.btn_skip = QtWidgets.QPushButton("Postpone")
        self.btn_delete = QtWidgets.QPushButton("Delete")
        self.btn_cancel = QtWidgets.QPushButton("Cancel")
        self.btn_save = QtWidgets.QPushButton("Save")
        btn_row.addWidget(self.btn_skip)
        btn_row.addWidget(self.btn_delete)
        btn_row.addWidget(self.btn_cancel)
        btn_row.addWidget(self.btn_save)
        self.btn_skip.setVisible(model.id is not None)
        main.addLayout(btn_row)

        # Wire
        self.cmb_recur.currentIndexChanged.connect(self._on_recur_changed)
        self.chk_time.toggled.connect(self._on_has_time_toggled)
        self.cmb_tag.currentIndexChanged.connect(self._on_tag_changed)
        self.btn_skip.clicked.connect(self._on_postpone)
        self.btn_delete.clicked.connect(self._on_delete)
        self.btn_cancel.clicked.connect(self.reject)
        self.btn_save.clicked.connect(self._on_save)

        self._load_model(model)

    def _on_recur_changed(self, idx: int):
        is_custom = self.cmb_recur.currentText() == "Custom"
        self.spn_count.setEnabled(is_custom)
        self.until_edit.setEnabled(is_custom)

    def _on_has_time_toggled(self, checked: bool):
        self.start_edit.setEnabled(checked); self.end_edit.setEnabled(checked)

    def _load_model(self, m: ItemModel):
        self.edt_title.setText(m.title or "")
        self.edt_notes.setPlainText(m.notes or "")
        self.lst_children.clear()
        for _, title in m.children:
            self.lst_children.addItem(title)
        qd = m.date or QtCore.QDate.currentDate()
        self.date_edit.setDate(qd)
        has_time = (m.start is not None and m.end is not None) or (m.kind == "event")
        self.chk_time.setChecked(has_time)
        if m.start: self.start_edit.setTime(m.start)
        if m.end: self.end_edit.setTime(m.end)
        if m.rrule:
            rr = m.rrule.upper()
            if rr == "RRULE=FREQ=WEEKLY;BYDAY=MO,TU,WE,TH,FR":
                self.cmb_recur.setCurrentText("Weekdays")
            elif rr.startswith("RRULE=FREQ=DAILY") and "COUNT" not in rr and "UNTIL" not in rr:
                self.cmb_recur.setCurrentText("Daily")
            elif rr.startswith("RRULE=FREQ=WEEKLY") and "BYDAY" not in rr:
                self.cmb_recur.setCurrentText("Weekly")
            else:
                self.cmb_recur.setCurrentText("Custom")
                # naive parse for COUNT and UNTIL
                if "COUNT=" in rr:
                    try:
                        cnt = int(rr.split("COUNT=")[1].split(";")[0])
                        self.spn_count.setValue(cnt)
                    except Exception:
                        pass
                if "UNTIL=" in rr:
                    try:
                        until_part = rr.split("UNTIL=")[1].split(";")[0]
                        qd = QtCore.QDate.fromString(until_part[:8], "yyyyMMdd")
                        if qd.isValid():
                            self.until_edit.setDate(qd)
                    except Exception:
                        pass
                self.spn_count.setEnabled(True)
                self.until_edit.setEnabled(True)
        else:
            self.cmb_recur.setCurrentText("None")
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

    def _on_postpone(self):
        self.postponed.emit(self._model)
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
        sel = self.cmb_recur.currentText()
        if sel == "None":
            m.rrule = None
        elif sel == "Weekdays":
            m.rrule = "RRULE=FREQ=WEEKLY;BYDAY=MO,TU,WE,TH,FR"
        elif sel == "Daily":
            m.rrule = "RRULE=FREQ=DAILY"
        elif sel == "Weekly":
            m.rrule = "RRULE=FREQ=WEEKLY"
        else:
            parts = ["RRULE=FREQ=DAILY"]
            if self.spn_count.isEnabled():
                parts.append(f"COUNT={self.spn_count.value()}")
            if self.until_edit.isEnabled() and self.until_edit.date().isValid():
                until = self.until_edit.date().toString("yyyyMMdd")
                parts.append(f"UNTIL={until}")
            m.rrule = ";".join(parts)
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
