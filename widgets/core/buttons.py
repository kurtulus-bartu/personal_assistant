from PyQt6 import QtCore, QtWidgets
from theme.colors import COLOR_SECONDARY_BG, COLOR_TEXT, COLOR_ACCENT

class SegmentedControl(QtWidgets.QWidget):
    changed = QtCore.pyqtSignal(str)  # "weekly" | "daily"

    def __init__(self, parent=None, options=("Weekly", "Daily"), initial="weekly"):
        super().__init__(parent)
        self._map = {label: label.lower() for label in options}
        self._buttons = {}

        lay = QtWidgets.QHBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(8)

        self.setStyleSheet(f"""
        QPushButton {{
            background: transparent;
            color: {COLOR_TEXT};
            border: 1px solid #3a3a3a;
            border-radius: 10px;
            padding: 6px 12px;
            text-align: center;
        }}
        QPushButton:checked {{
            background: {COLOR_ACCENT};   /* seçiliyken yeşil */
            color: {COLOR_TEXT};
            border-color: {COLOR_ACCENT};
        }}
        QPushButton:hover {{ border-color: #4a4a4a; }}
        """)

        for label in options:
            btn = QtWidgets.QPushButton(label)
            btn.setCheckable(True)
            btn.setAutoExclusive(True)
            btn.clicked.connect(self._on_clicked)
            self._buttons[self._map[label]] = btn
            lay.addWidget(btn)

        self.setValue(initial, emit=False)

    def _on_clicked(self):
        for key, btn in self._buttons.items():
            if btn.isChecked():
                self.setValue(key)
                self.changed.emit(key)
                return

    def setValue(self, key: str, emit: bool = True):
        for k, btn in self._buttons.items():
            btn.setChecked(k == key)
        if emit:
            self.changed.emit(key)
