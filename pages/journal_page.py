from PyQt6 import QtWidgets
from theme.colors import COLOR_PRIMARY_BG, COLOR_SECONDARY_BG, COLOR_TEXT

class JournalPage(QtWidgets.QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setStyleSheet(f"background:{COLOR_PRIMARY_BG}; color:{COLOR_TEXT};")
        v = QtWidgets.QVBoxLayout(self); v.setContentsMargins(12,12,12,12); v.setSpacing(8)
        title = QtWidgets.QLabel("Journal"); title.setStyleSheet("font-size:20px; font-weight:600;")
        v.addWidget(title)
        editor = QtWidgets.QPlainTextEdit(); editor.setPlaceholderText("Write your day…")
        editor.setStyleSheet(f"background:{COLOR_SECONDARY_BG}; border:1px solid #3a3a3a; border-radius:12px; padding:8px;")
        v.addWidget(editor, 1)
