from PyQt6 import QtCore, QtWidgets, QtGui
from widgets.core.buttons import SegmentedControl
from widgets.core.selectors import TagFolderList
from widgets.calendar.mini_month import MiniMonthCalendar
from theme.colors import COLOR_TEXT, COLOR_SECONDARY_BG

class LeftPanel(QtWidgets.QWidget):
    viewChanged = QtCore.pyqtSignal(str)
    tagsChanged = QtCore.pyqtSignal(set)
    dateSelected = QtCore.pyqtSignal(object)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedWidth(280)
        self._store = None
        self._current_tid: int | None = None

        v = QtWidgets.QVBoxLayout(self); v.setContentsMargins(12,12,12,12); v.setSpacing(12)

        self.month = MiniMonthCalendar(self)
        self.month.setAnchorDate(QtCore.QDate.currentDate())
        self.month.dateSelected.connect(self.dateSelected.emit)
        v.addWidget(self.month)

        self.segment = SegmentedControl(initial="weekly")
        self.segment.changed.connect(self.viewChanged.emit)
        v.addWidget(self.segment)

        v.addStretch(1)

        center = QtWidgets.QHBoxLayout(); center.addStretch(1)
        self.tags = TagFolderList(); self.tags.setFixedWidth(240)
        self.tags.changed.connect(self._on_tag_changed)
        center.addWidget(self.tags); center.addStretch(1)
        v.addLayout(center)

        v.addStretch(1)

        # New bar
        self.new_bar = QtWidgets.QWidget()
        hb = QtWidgets.QHBoxLayout(self.new_bar); hb.setContentsMargins(0,0,0,0); hb.setSpacing(8)
        self.txt_new = QtWidgets.QLineEdit(); self.txt_new.setPlaceholderText("New folder name…"); self.txt_new.setMaxLength(48)
        self.txt_new.setStyleSheet(f"background:{COLOR_SECONDARY_BG}; color:{COLOR_TEXT}; border:1px solid #3a3a3a; border-radius:10px; padding:6px 8px;")
        self.btn_add = QtWidgets.QPushButton("Add"); self.btn_add.setFixedHeight(36)
        self.btn_add.setStyleSheet(f"background:{COLOR_SECONDARY_BG}; color:{COLOR_TEXT}; border:1px solid #3a3a3a; border-radius:10px;")
        self.btn_add.clicked.connect(self._on_add_clicked)
        hb.addWidget(self.txt_new, 1); hb.addWidget(self.btn_add)
        self.new_bar.setVisible(False); v.addWidget(self.new_bar)

        row = QtWidgets.QHBoxLayout(); row.setSpacing(8)
        self.btn_new = QtWidgets.QPushButton("+ New Tag"); self.btn_new.setFixedHeight(36)
        self.btn_new.setStyleSheet(f"background:{COLOR_SECONDARY_BG}; color:{COLOR_TEXT}; border:1px solid #3a3a3a; border-radius:10px;")
        self.btn_new.clicked.connect(self._toggle_new_bar)
        self.btn_delete = QtWidgets.QPushButton("Delete Tag"); self.btn_delete.setFixedHeight(36)
        self.btn_delete.setStyleSheet(f"background:{COLOR_SECONDARY_BG}; color:{COLOR_TEXT}; border:1px solid #3a3a3a; border-radius:10px;")
        self.btn_delete.clicked.connect(self._on_delete_clicked)
        row.addWidget(self.btn_new); row.addWidget(self.btn_delete)
        v.addLayout(row)

        self.txt_new.returnPressed.connect(self._on_add_clicked)

    # ---- Orchestrator entegrasyonu ----
    def attachStore(self, store):
        self._store = store
        self._store.tagsUpdated.connect(self._on_server_tags)

    def applyServerTags(self, items: list[tuple[int,str]]):
        self.tags.setItems(items)

    # ---- UI handlers ----
    def _on_tag_changed(self, tid: int):
        self._current_tid = tid
        self.tagsChanged.emit({tid})

    def _toggle_new_bar(self):
        show = not self.new_bar.isVisible()
        self.new_bar.setVisible(show)
        self.btn_new.setText("Close" if show else "+ New Tag")
        if show:
            self.txt_new.clear()
            self.txt_new.setFocus(QtCore.Qt.FocusReason.ActiveWindowFocusReason)

    def _on_add_clicked(self):
        name = (self.txt_new.text() or "").strip()
        if not name: return
        if self._store:
            self._store.add_tag(name)  # local + queue + emit
        self.new_bar.setVisible(False)
        self.btn_new.setText("+ New Tag")
        self.txt_new.clear()

    def _on_delete_clicked(self):
        if self._current_tid is None: return
        if self._store:
            self._store.delete_tag(int(self._current_tid))
        self._current_tid = None

    # ---- store callback ----
    def _on_server_tags(self, rows: list[dict]):
        items = [(int(r["id"]), r["name"]) for r in rows]
        self.tags.setItems(items)

    # ---- public ----
    def setMonthNavIcons(self, prev_path, next_path, icon_px: int | None = None):
        self.month.setNavIcons(prev_path, next_path, icon_px)
