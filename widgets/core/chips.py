from typing import Dict, List, Set, Tuple
from PyQt6 import QtCore, QtGui, QtWidgets
from theme.colors import COLOR_TEXT, COLOR_ACCENT, COLOR_SECONDARY_BG


class FlowLayout(QtWidgets.QLayout):
    def __init__(self, parent=None, margin=0, hspacing=8, vspacing=8):
        super().__init__(parent)
        self._items: List[QtWidgets.QLayoutItem] = []
        self.setContentsMargins(margin, margin, margin, margin)
        self.hspacing = hspacing
        self.vspacing = vspacing

    def addItem(self, item):
        self._items.append(item)

    def count(self):
        return len(self._items)

    def itemAt(self, i):
        if 0 <= i < len(self._items):
            return self._items[i]
        return None

    def takeAt(self, i):
        if 0 <= i < len(self._items):
            return self._items.pop(i)
        return None

    def expandingDirections(self):
        return QtCore.Qt.Orientation(0)

    def hasHeightForWidth(self):
        return True

    def heightForWidth(self, width):
        return self.doLayout(QtCore.QRect(0, 0, width, 0), test_only=True)

    def setGeometry(self, rect):
        super().setGeometry(rect)
        self.doLayout(rect, test_only=False)

    def sizeHint(self):
        return self.minimumSize()

    def minimumSize(self):
        size = QtCore.QSize()
        for item in self._items:
            size = size.expandedTo(item.minimumSize())
        margins = self.contentsMargins()
        size += QtCore.QSize(margins.left() + margins.right(), margins.top() + margins.bottom())
        return size

    def doLayout(self, rect, test_only):
        x = rect.x(); y = rect.y(); line_h = 0
        for item in self._items:
            space_x = self.hspacing; space_y = self.vspacing
            next_x = x + item.sizeHint().width() + space_x
            if next_x - space_x > rect.right() and line_h > 0:
                x = rect.x(); y = y + line_h + space_y
                next_x = x + item.sizeHint().width() + space_x
                line_h = 0
            if not test_only:
                item.setGeometry(QtCore.QRect(QtCore.QPoint(x, y), item.sizeHint()))
            x = next_x
            line_h = max(line_h, item.sizeHint().height())
        return y + line_h - rect.y()


class TagChip(QtWidgets.QCheckBox):
    def __init__(self, text: str, tag_id: int, parent=None):
        super().__init__(text, parent)
        self.tag_id = tag_id
        self.setCursor(QtCore.Qt.CursorShape.PointingHandCursor)
        self.setStyleSheet(f"""
            QCheckBox {{ spacing: 6px; color: {COLOR_TEXT}; }}
            QCheckBox::indicator {{ width:0px; height:0px; }}
            QCheckBox[checked="true"] {{ background: {COLOR_ACCENT}; border-radius:8px; padding:4px 8px; }}
            QCheckBox[checked="false"] {{ background: {COLOR_SECONDARY_BG}; border-radius:8px; padding:4px 8px; }}
        """)
        self.setProperty("checked", False)
        self.toggled.connect(lambda v: self.setProperty("checked", v))
        self.toggled.connect(self._update_style)
        self._update_style()

    def sizeHint(self):
        m = QtGui.QFontMetrics(self.font())
        w = m.horizontalAdvance(self.text()) + 24
        h = m.height() + 8
        return QtCore.QSize(w, h)

    def _update_style(self):
        self.style().unpolish(self)
        self.style().polish(self)
        self.update()


class TagChipList(QtWidgets.QWidget):
    selectionChanged = QtCore.pyqtSignal(set)
    newTagRequested = QtCore.pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._selection: Set[int] = set()
        self._chips: Dict[int, TagChip] = {}
        v = QtWidgets.QVBoxLayout(self)
        v.setContentsMargins(0, 0, 0, 0)
        v.setSpacing(8)
        self.flow = FlowLayout()
        v.addLayout(self.flow)
        self.btn_new = QtWidgets.QPushButton("+ New Tag")
        self.btn_new.clicked.connect(self.newTagRequested.emit)
        self.btn_new.setCursor(QtCore.Qt.CursorShape.PointingHandCursor)
        self.btn_new.setStyleSheet(f"background:{COLOR_SECONDARY_BG}; color:{COLOR_TEXT}; border:1px solid #3a3a3a; border-radius:8px; padding:6px 10px;")
        v.addWidget(self.btn_new, alignment=QtCore.Qt.AlignmentFlag.AlignLeft)

    def setTags(self, tags: List[Tuple[int, str]]):
        while self.flow.count():
            item = self.flow.takeAt(0)
            if item and item.widget():
                item.widget().deleteLater()
        self._chips.clear()
        for tag_id, label in tags:
            chip = TagChip(label, tag_id)
            chip.toggled.connect(lambda v, tid=tag_id: self._on_chip_toggled(tid, v))
            self._chips[tag_id] = chip
            self.flow.addWidget(chip)

    def _on_chip_toggled(self, tag_id: int, checked: bool):
        if checked:
            self._selection.add(tag_id)
        else:
            self._selection.discard(tag_id)
        self.selectionChanged.emit(set(self._selection))
