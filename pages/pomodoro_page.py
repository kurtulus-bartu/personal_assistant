from PyQt6 import QtCore, QtWidgets
from theme.colors import COLOR_PRIMARY_BG, COLOR_SECONDARY_BG, COLOR_TEXT, COLOR_ACCENT

class PomodoroPage(QtWidgets.QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._remaining = 25 * 60
        self._timer = QtCore.QTimer(self); self._timer.setInterval(1000); self._timer.timeout.connect(self._tick)

        self.setStyleSheet(f"background:{COLOR_PRIMARY_BG}; color:{COLOR_TEXT};")
        v = QtWidgets.QVBoxLayout(self); v.setContentsMargins(12,12,12,12); v.setSpacing(12)

        title = QtWidgets.QLabel("Pomodoro"); title.setStyleSheet("font-size:20px; font-weight:600;")
        v.addWidget(title)

        card = QtWidgets.QFrame(); card.setStyleSheet(f"background:{COLOR_SECONDARY_BG}; border:1px solid #3a3a3a; border-radius:12px;")
        c = QtWidgets.QVBoxLayout(card); c.setContentsMargins(16,16,16,16); c.setSpacing(12)

        self.lbl = QtWidgets.QLabel(self._fmt()); self.lbl.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        self.lbl.setStyleSheet("font-size:36px; font-weight:600;")
        c.addWidget(self.lbl)

        row = QtWidgets.QHBoxLayout()
        self.btn_start = QtWidgets.QPushButton("Start"); self.btn_pause = QtWidgets.QPushButton("Pause"); self.btn_reset = QtWidgets.QPushButton("Reset")
        for b in (self.btn_start, self.btn_pause, self.btn_reset):
            b.setFixedHeight(36); b.setStyleSheet(f"background:{COLOR_ACCENT}; border-radius:10px;")
        self.btn_start.clicked.connect(self._start); self.btn_pause.clicked.connect(self._pause); self.btn_reset.clicked.connect(self._reset)
        row.addWidget(self.btn_start); row.addWidget(self.btn_pause); row.addWidget(self.btn_reset)
        c.addLayout(row)

        v.addWidget(card, 1)

    def _fmt(self):
        m, s = divmod(self._remaining, 60)
        return f"{m:02d}:{s:02d}"

    def _tick(self):
        if self._remaining > 0:
            self._remaining -= 1
            self.lbl.setText(self._fmt())
        else:
            self._timer.stop()

    def _start(self): self._timer.start()
    def _pause(self): self._timer.stop()
    def _reset(self):
        self._timer.stop()
        self._remaining = 25 * 60
        self.lbl.setText(self._fmt())
