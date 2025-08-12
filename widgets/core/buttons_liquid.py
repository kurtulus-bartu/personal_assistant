from PyQt6 import QtCore, QtWidgets, QtGui
from theme.colors import COLOR_SECONDARY_BG, COLOR_TEXT, COLOR_ACCENT
from widgets.core.glass import GlassHighlight

class LiquidSegmentedControl(QtWidgets.QFrame):
    changed = QtCore.pyqtSignal(str)  # "weekly" | "daily"

    def __init__(self, parent=None, options=("Weekly", "Daily"), initial="weekly"):
        super().__init__(parent)
        self._labels = list(options)
        self._keys = [s.lower() for s in options]
        self._key_map = dict(zip(self._labels, self._keys))
        self._current_key = initial

        self.setStyleSheet(f"background:{COLOR_SECONDARY_BG}; border:1px solid #3a3a3a; border-radius:12px;")
        self.setFixedHeight(40)

        self._wrap = QtWidgets.QWidget(self)
        self._wrap.setGeometry(6, 6, 0, 0)
        self._layout = QtWidgets.QHBoxLayout(self._wrap)
        self._layout.setContentsMargins(6, 6, 6, 6)
        self._layout.setSpacing(6)

        self._buttons = {}
        for label in self._labels:
            btn = QtWidgets.QPushButton(label)
            btn.setCheckable(True)
            btn.setAutoExclusive(True)
            btn.setCursor(QtCore.Qt.CursorShape.PointingHandCursor)
            btn.setStyleSheet(f"color:{COLOR_TEXT}; border:0; padding:6px 12px; border-radius:10px;")
            btn.clicked.connect(lambda _=False, k=self._key_map[label]: self.setValue(k, animate=True))
            self._layout.addWidget(btn)
            self._buttons[self._key_map[label]] = btn

        self._hl = GlassHighlight(radius=10, tint=QtGui.QColor(COLOR_ACCENT), parent=self)
        self._hl.raise_()
        self._anim = QtCore.QPropertyAnimation(self._hl, b"geometry", duration=200)
        self._anim.setEasingCurve(QtCore.QEasingCurve.Type.InOutQuad)

        self.setValue(initial, animate=False)

    def resizeEvent(self, e: QtGui.QResizeEvent):
        super().resizeEvent(e)
        self._wrap.setGeometry(0, 0, self.width(), self.height())
        self._reposition_highlight()

    def setValue(self, key: str, animate=True):
        if key not in self._buttons:
            return
        self._buttons[key].setChecked(True)
        prev = self._current_key
        self._current_key = key
        self._reposition_highlight(animate=animate and prev is not None)
        if prev != key:
            self.changed.emit(key)

    def _reposition_highlight(self, animate=False):
        btn = self._buttons[self._current_key]
        g = btn.geometry()
        tgt = QtCore.QRect(g.left()+6, g.top()+6, g.width(), g.height())
        if animate:
            self._anim.stop()
            self._anim.setStartValue(self._hl.geometry())
            self._anim.setEndValue(tgt)
            self._anim.start()
        else:
            self._hl.setGeometry(tgt)
        self._hl.show()
