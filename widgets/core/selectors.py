from typing import List, Tuple, Dict
from PyQt6 import QtCore, QtWidgets
from theme.colors import COLOR_TEXT, COLOR_SECONDARY_BG, COLOR_ACCENT

class SlidingSelector(QtWidgets.QFrame):
    """Dikey tek-seçim klasör listesi (şeffaf zemin, aktif= koyu gri arka plan)."""
    changed = QtCore.pyqtSignal(int)  # seçilen id

    def __init__(self, parent=None, item_height=36, radius=12):
        super().__init__(parent)
        self._id_order: List[int] = []
        self._buttons: Dict[int, QtWidgets.QPushButton] = {}
        self._item_h = item_height
        self._radius = radius
        self._current_id: int | None = None

        # Arka planı tamamen kaldır (şeffaf), kenarlık yok
        self.setStyleSheet(f"""
        /* Bu kapsayıcıya arka plan yok */
        QFrame {{
            background: transparent;
            border: 0;
        }}
        /* Butonların temel görünümü */
        QPushButton {{
            color: {COLOR_TEXT};
            background: transparent;          /* arka plan yok */
            border: 1px solid #3a3a3a;
            border-radius: {radius}px;
            padding: 6px 12px;
            text-align: center;               /* metni ortala */
        }}
        /* Aktif (checked) durum: koyu gri arka plan */
        QPushButton:checked {{
            background: {COLOR_ACCENT};
            color: {COLOR_TEXT};
            border-color: {COLOR_ACCENT};
        }}
        """)
        self._wrap = QtWidgets.QWidget()
        self._layout = QtWidgets.QVBoxLayout(self._wrap)
        self._layout.setContentsMargins(6, 6, 6, 6)
        self._layout.setSpacing(6)

        lay = QtWidgets.QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(0)
        lay.addWidget(self._wrap)

    def setItems(self, items: List[Tuple[int, str]]):
        # temizle
        while self._layout.count():
            it = self._layout.takeAt(0)
            if it and it.widget():
                it.widget().deleteLater()
        self._buttons.clear()
        self._id_order = []
        for _id, label in items:
            btn = QtWidgets.QPushButton(label, self._wrap)
            btn.setCheckable(True)
            btn.setAutoExclusive(True)
            btn.setCursor(QtCore.Qt.CursorShape.PointingHandCursor)
            btn.setFixedHeight(self._item_h)
            btn.clicked.connect(lambda _=False, i=_id: self._on_clicked(i))
            self._buttons[_id] = btn
            self._layout.addWidget(btn)
            self._id_order.append(_id)
        self._layout.addStretch(1)
        # varsayılan ilkini seç
        if self._id_order:
            self.setCurrentById(self._id_order[0])

    def _on_clicked(self, _id: int):
        self.setCurrentById(_id)
        self.changed.emit(_id)

    def currentId(self):
        return self._current_id

    def setCurrentById(self, _id: int):
        if _id not in self._buttons:
            return
        if self._current_id is not None and self._current_id in self._buttons:
            self._buttons[self._current_id].setChecked(False)
        self._buttons[_id].setChecked(True)
        self._current_id = _id

class TagFolderList(SlidingSelector):
    pass
