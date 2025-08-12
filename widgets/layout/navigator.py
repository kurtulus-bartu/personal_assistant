from __future__ import annotations
from dataclasses import dataclass
from typing import List, Dict
from PyQt6 import QtCore, QtGui, QtWidgets
from theme.colors import COLOR_PRIMARY_BG, COLOR_SECONDARY_BG, COLOR_ACCENT, COLOR_TEXT_MUTED
from utils.icons import make_icon_pm_pair

@dataclass
class PageSpec:
    key: str
    label: str
    icon: QtGui.QIcon | str | None = None
    tooltip: str | None = None
    shortcut: str | None = None


def _pm_logical_size(pm: QtGui.QPixmap) -> QtCore.QSizeF:
    dpr = pm.devicePixelRatio() if hasattr(pm, "devicePixelRatio") else 1.0
    if not dpr: dpr = 1.0
    return QtCore.QSizeF(pm.width() / dpr, pm.height() / dpr)


class NavIconButton(QtWidgets.QWidget):
    clicked = QtCore.pyqtSignal()

    def __init__(self, pm_normal: QtGui.QPixmap, pm_active: QtGui.QPixmap,
                 row_width: int, box_w: int = 48, box_h: int = 48,
                 tooltip: str = "", parent=None):
        super().__init__(parent)
        self._pm_n = pm_normal
        self._pm_a = pm_active
        self._active = False
        self._hover = False
        self._row_w = row_width
        self._box_w = box_w
        self._box_h = box_h
        self.setFixedSize(self._row_w, self._box_h + 12)
        self.setToolTip(tooltip)
        self.setCursor(QtCore.Qt.CursorShape.PointingHandCursor)
        self.setAttribute(QtCore.Qt.WidgetAttribute.WA_Hover, True)

    def setActive(self, active: bool):
        if self._active != active:
            self._active = active
            self.update()

    def sizeHint(self) -> QtCore.QSize:
        return QtCore.QSize(self._row_w, self._box_h + 12)

    def paintEvent(self, e: QtGui.QPaintEvent):
        p = QtGui.QPainter(self)
        p.setRenderHints(QtGui.QPainter.RenderHint.Antialiasing
                         | QtGui.QPainter.RenderHint.TextAntialiasing
                         | QtGui.QPainter.RenderHint.SmoothPixmapTransform, True)

        # Hover kutusu: tam merkez
        bx = (self.width() - self._box_w) / 2.0
        by = (self.height() - self._box_h) / 2.0
        box_rect = QtCore.QRectF(bx, by, self._box_w, self._box_h)
        if self._hover:
            p.setPen(QtCore.Qt.PenStyle.NoPen)
            p.setBrush(QtGui.QColor(COLOR_SECONDARY_BG))
            p.drawRoundedRect(box_rect, 8, 8)

        # İkon: dpr-aware merkez
        pm = self._pm_a if self._active else self._pm_n
        ls = _pm_logical_size(pm)
        ix = (self.width() - ls.width()) / 2.0
        iy = (self.height() - ls.height()) / 2.0
        p.drawPixmap(QtCore.QRectF(ix, iy, ls.width(), ls.height()), pm, QtCore.QRectF(pm.rect()))
        p.end()

    def enterEvent(self, e: QtCore.QEvent):
        self._hover = True; self.update(); return super().enterEvent(e)

    def leaveEvent(self, e: QtCore.QEvent):
        self._hover = False; self.update(); return super().leaveEvent(e)

    def mousePressEvent(self, e: QtGui.QMouseEvent):
        if e.button() == QtCore.Qt.MouseButton.LeftButton:
            self.clicked.emit()
        return super().mousePressEvent(e)


class MiniNavigator(QtWidgets.QFrame):
    pageRequested = QtCore.pyqtSignal(str)
    chatbotToggled = QtCore.pyqtSignal(bool)

    def __init__(self, parent=None, icon_size: int = 30, bar_width: int = 64, lr_margin: int = 6, logo_size: int | None = None):
        """
        icon_size: sayfa/chatbot ikonlarının piksel boyutu
        bar_width: toplam bar genişliği
        lr_margin: içerik sol/sağ margin (simetrik)
        logo_size: üst app icon piksel boyutu (varsayılan: icon_size ile aynı)
        """
        super().__init__(parent)
        self._icon_px  = icon_size
        self._logo_px  = logo_size or icon_size   # <<< app icon artık sabit px
        self._bar_w    = bar_width
        self._lr_margin= lr_margin
        self._inner_w  = self._bar_w - 2*self._lr_margin
        self._box_w    = 48
        self._box_h    = 48
        self._buttons: Dict[str, NavIconButton] = {}
        self._pages: List[PageSpec] = []
        self._chatbot_open = False

        self.setObjectName("MiniNavigator")
        self.setFixedWidth(self._bar_w)
        self.setStyleSheet(f"""
        QFrame#MiniNavigator {{
            background: {COLOR_PRIMARY_BG};
            border-right: 1px solid #2a2a2a;
        }}
        QLabel#Logo {{ background: transparent; }}
        """)

        root = QtWidgets.QVBoxLayout(self)
        root.setContentsMargins(self._lr_margin, 6, self._lr_margin, 6)
        root.setSpacing(6)

        # Üst: App icon (sabit px; bar genişliğinden etkilenmez)
        self._logo = QtWidgets.QLabel(self)
        self._logo.setObjectName("Logo")
        self._logo.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        # Konteyner genişliği iç alana eşit, yüksekliği kutu ile benzer olsun
        self._logo.setFixedSize(self._inner_w, self._box_h)
        root.addWidget(self._logo, alignment=QtCore.Qt.AlignmentFlag.AlignHCenter)

        # Orta: sayfa ikon grubu (dikey merkez)
        self._center = QtWidgets.QVBoxLayout()
        self._center.setContentsMargins(0, 0, 0, 0)
        self._center.setSpacing(4)
        center_wrap = QtWidgets.QVBoxLayout()
        center_wrap.setContentsMargins(0, 0, 0, 0)
        center_wrap.setSpacing(0)
        center_wrap.addStretch(1)
        center_wrap.addLayout(self._center)
        center_wrap.addStretch(1)
        root.addLayout(center_wrap, 1)

        # Alt: Chatbot — aynı buton sınıfı
        pm_n, pm_a = make_icon_pm_pair(
            self.style().standardIcon(QtWidgets.QStyle.StandardPixmap.SP_MessageBoxInformation),
            size=self._icon_px,
            normal_color=COLOR_TEXT_MUTED, active_color=COLOR_ACCENT
        )
        self._chat_btn = NavIconButton(pm_n, pm_a,
                                       row_width=self._inner_w,
                                       box_w=self._box_w, box_h=self._box_h,
                                       tooltip="Chatbot")
        self._chat_btn.clicked.connect(self._on_chatbot_clicked)
        root.addWidget(self._chat_btn, alignment=QtCore.Qt.AlignmentFlag.AlignHCenter)

    # ---- Public API ----
    def setAppLogo(self, path_or_qicon):
        """App icon’u sayfa ikonlarıyla aynı şekilde trim+center edip SABİT pikselde gösterir."""
        pm_n, _pm_a = make_icon_pm_pair(path_or_qicon, size=self._logo_px, normal_color=None, active_color=None)
        # QLabel scaling yok; pixmap zaten hedef px’te ortalı
        self._logo.setPixmap(pm_n)

    def setChatbotIcon(self, path_or_qicon):
        pm_n, pm_a = make_icon_pm_pair(path_or_qicon,
                                       size=self._icon_px,
                                       normal_color=COLOR_TEXT_MUTED,
                                       active_color=COLOR_ACCENT)
        self._chat_btn._pm_n = pm_n
        self._chat_btn._pm_a = pm_a
        self._chat_btn.update()

    def setPages(self, pages: List[PageSpec], active_key: str | None = None):
        while self._center.count():
            it = self._center.takeAt(0)
            if w := it.widget(): w.deleteLater()
        self._buttons.clear()
        self._pages = pages[:]

        for spec in pages:
            if spec.icon is None:
                pm_n, pm_a = make_icon_pm_pair(
                    self.style().standardIcon(QtWidgets.QStyle.StandardPixmap.SP_FileIcon),
                    size=self._icon_px,
                    normal_color=COLOR_TEXT_MUTED, active_color=COLOR_ACCENT
                )
            else:
                pm_n, pm_a = make_icon_pm_pair(
                    spec.icon, size=self._icon_px,
                    normal_color=COLOR_TEXT_MUTED, active_color=COLOR_ACCENT
                )
            btn = NavIconButton(pm_n, pm_a,
                                row_width=self._inner_w,
                                box_w=self._box_w, box_h=self._box_h,
                                tooltip=spec.tooltip or spec.label)
            btn.clicked.connect(lambda _=False, k=spec.key: self._on_page_clicked(k))
            self._center.addWidget(btn, alignment=QtCore.Qt.AlignmentFlag.AlignHCenter)
            self._buttons[spec.key] = btn

        if active_key is None and pages:
            active_key = pages[0].key
        if active_key:
            self.setActive(active_key)

    def setActive(self, key: str):
        for k, b in self._buttons.items():
            b.setActive(k == key)

    # ---- slots ----
    def _on_page_clicked(self, key: str):
        self.setActive(key)
        self.pageRequested.emit(key)

    def _on_chatbot_clicked(self):
        self._chatbot_open = not self._chatbot_open
        self._chat_btn.setActive(self._chatbot_open)
        self.chatbotToggled.emit(self._chatbot_open)
