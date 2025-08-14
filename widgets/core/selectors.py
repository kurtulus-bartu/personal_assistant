from typing import List, Tuple, Dict
from PyQt6 import QtCore, QtWidgets, QtGui
from theme.colors import COLOR_TEXT, COLOR_SECONDARY_BG, COLOR_ACCENT

class SlidingSelector(QtWidgets.QFrame):
    """Dikey tek-seçim klasör listesi (şeffaf zemin, aktif= koyu gri arka plan).

    Bir etikete tekrar tıklanınca seçimi kaldırıp tüm etiketleri gösterebilmek
    için `changed` sinyali 0 değeri yayımlayabilir."""
    changed = QtCore.pyqtSignal(int)  # seçilen id (0 = tümü)

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
            btn.setCursor(QtCore.Qt.CursorShape.PointingHandCursor)
            btn.setFixedHeight(self._item_h)
            btn.clicked.connect(lambda checked, i=_id: self._on_clicked(i, checked))
            self._buttons[_id] = btn
            self._layout.addWidget(btn)
            self._id_order.append(_id)
        self._layout.addStretch(1)
        # başlangıçta hiçbirini seçme
        self._current_id = None

    def _on_clicked(self, _id: int, checked: bool):
        if checked:
            if self._current_id is not None and self._current_id in self._buttons:
                self._buttons[self._current_id].setChecked(False)
            self._current_id = _id
            self.changed.emit(_id)
        else:
            self._current_id = None
            self.changed.emit(0)

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


class HorizontalSelector(QtWidgets.QFrame):
    """Horizontal single-selection button row with toggle-off capability."""
    changed = QtCore.pyqtSignal(int)  # 0 = tümü

    def __init__(self, parent=None, item_width: int = 100, item_height: int = 36):
        super().__init__(parent)
        self._buttons: Dict[int, QtWidgets.QPushButton] = {}
        self._current_id: int | None = None
        self._item_w = item_width
        self._item_h = item_height

        self.setStyleSheet(f"""
        QPushButton {{
            color: {COLOR_TEXT};
            background: transparent;
            border: 1px solid #3a3a3a;
            border-radius: 8px;
            padding: 6px 12px;
        }}
        QPushButton:checked {{
            background: {COLOR_ACCENT};
            color: {COLOR_TEXT};
            border-color: {COLOR_ACCENT};
        }}
        """)

        self._wrap = QtWidgets.QWidget()
        self._layout = QtWidgets.QHBoxLayout(self._wrap)
        self._layout.setContentsMargins(6, 6, 6, 6)
        self._layout.setSpacing(6)

        lay = QtWidgets.QHBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.addWidget(self._wrap)

    def setItems(self, items: List[Tuple[int, str]]):
        while self._layout.count():
            it = self._layout.takeAt(0)
            if it and it.widget():
                it.widget().deleteLater()
        self._buttons.clear()
        for _id, label in items:
            btn = QtWidgets.QPushButton(label, self._wrap)
            btn.setCheckable(True)
            btn.setFixedSize(self._item_w, self._item_h)
            btn.clicked.connect(lambda checked, i=_id: self._on_clicked(i, checked))
            self._buttons[_id] = btn
            self._layout.addWidget(btn)
        # başlangıçta seçim yok
        self._current_id = None

    def _on_clicked(self, _id: int, checked: bool):
        if checked:
            if self._current_id is not None and self._current_id in self._buttons:
                self._buttons[self._current_id].setChecked(False)
            self._current_id = _id
            self.changed.emit(_id)
        else:
            self._current_id = None
            self.changed.emit(0)

    def setCurrentById(self, _id: int):
        if _id not in self._buttons:
            return
        if self._current_id is not None and self._current_id in self._buttons:
            self._buttons[self._current_id].setChecked(False)
        self._buttons[_id].setChecked(True)
        self._current_id = _id


class ProjectButtonRow(QtWidgets.QScrollArea):
    """Horizontal project selector with automatic scroll when overflowing."""
    changed = QtCore.pyqtSignal(int)

    def __init__(self, parent=None, item_width: int = 100, item_height: int = 36):
        super().__init__(parent)
        # PyQt6 relocated ScrollBarPolicy enums under Qt.ScrollBarPolicy
        self.setHorizontalScrollBarPolicy(
            QtCore.Qt.ScrollBarPolicy.ScrollBarAlwaysOff
        )
        self.setVerticalScrollBarPolicy(
            QtCore.Qt.ScrollBarPolicy.ScrollBarAlwaysOff
        )
        self.setWidgetResizable(False)
        self.setFrameShape(QtWidgets.QFrame.Shape.NoFrame)

        self._inner = HorizontalSelector(item_width=item_width, item_height=item_height)
        self._inner.changed.connect(self.changed.emit)
        # İç widget genişliği içeriğe göre ayarlansın
        # In Qt6, QSizePolicy enums moved under the Policy enum
        self._inner.setSizePolicy(
            QtWidgets.QSizePolicy.Policy.Fixed, QtWidgets.QSizePolicy.Policy.Fixed
        )
        self.setWidget(self._inner)
        self.setFixedHeight(item_height + 12)

    def setItems(self, items: List[Tuple[int, str]]):
        self._inner.setItems(items)
        self._inner.adjustSize()
        QtCore.QTimer.singleShot(0, self._inner.adjustSize)

    def setCurrentById(self, _id: int):
        self._inner.setCurrentById(_id)

    def wheelEvent(self, e: QtGui.QWheelEvent):
        self.horizontalScrollBar().setValue(
            self.horizontalScrollBar().value() - e.angleDelta().y()
        )
        e.accept()
