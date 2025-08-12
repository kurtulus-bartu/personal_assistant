from PyQt6 import QtCore, QtGui, QtWidgets
from theme.colors import COLOR_PRIMARY_BG, COLOR_TEXT, COLOR_TEXT_MUTED

class SplashScreen(QtWidgets.QSplashScreen):
    def __init__(self, icon_path: str | None = None, title: str = "App", subtitle: str = ""):
        pm = self._make_pixmap(icon_path, title, subtitle)
        super().__init__(pm)

        self._title = title
        self._icon_path = icon_path
        self._subtitle = subtitle

        # En önde dursun
        self.setWindowFlag(QtCore.Qt.WindowType.WindowStaysOnTopHint, True)
        self.setWindowModality(QtCore.Qt.WindowModality.ApplicationModal)

    def showEvent(self, e: QtGui.QShowEvent):
        super().showEvent(e)
        self.raise_()
        self.activateWindow()

    def set_status(self, text: str):
        self._subtitle = text
        self.setPixmap(self._make_pixmap(self._icon_path, self._title, self._subtitle))

    # --- painter ---
    def _make_pixmap(self, icon_path: str | None, title: str, subtitle: str) -> QtGui.QPixmap:
        w, h = 460, 260
        pm = QtGui.QPixmap(w, h)
        pm.fill(QtGui.QColor(COLOR_PRIMARY_BG))
        p = QtGui.QPainter(pm)
        p.setRenderHints(
            QtGui.QPainter.RenderHint.Antialiasing
            | QtGui.QPainter.RenderHint.TextAntialiasing
            | QtGui.QPainter.RenderHint.SmoothPixmapTransform, True
        )

        # İnce çerçeve
        pen = QtGui.QPen(QtGui.QColor("#2a2a2a")); pen.setWidth(1)
        p.setPen(pen); p.drawRect(0, 0, w-1, h-1)

        # Uygulama fontunu baz al
        base_font = QtWidgets.QApplication.font()

        # 1) Logo (üstte — YATAY TAM ORTA)
        if icon_path:
            src = QtGui.QPixmap(icon_path)
            if not src.isNull():
                # HiDPI için: hedef boyutu DIP'te belirle, Smooth ile ölçekle
                target = 80  # dilediğin gibi değişebilir
                screen = QtGui.QGuiApplication.primaryScreen()
                dpr = screen.devicePixelRatio() if screen else 1.0
                scaled = src.scaled(int(target * dpr), int(target * dpr),
                                    QtCore.Qt.AspectRatioMode.KeepAspectRatio,
                                    QtCore.Qt.TransformationMode.SmoothTransformation)
                scaled.setDevicePixelRatio(dpr)

                # hedef dikdörtgen: yatay tam merkez, üstten 18 px boşluk
                tw, th = target, target * (scaled.height() / scaled.width())
                x = (w - tw) / 2.0
                y = 18.0
                target_rect = QtCore.QRectF(x, y, tw, th)
                p.drawPixmap(target_rect, scaled, QtCore.QRectF(scaled.rect()))

        # 2) Başlık (tam ortada)
        title_font = QtGui.QFont(base_font); title_font.setPointSize(max(14, base_font.pointSize() + 2)); title_font.setBold(True)
        p.setFont(title_font); p.setPen(QtGui.QColor(COLOR_TEXT))
        p.drawText(pm.rect(), QtCore.Qt.AlignmentFlag.AlignCenter, title)

        # 3) Loading (altta — ortalı)
        sub_font = QtGui.QFont(base_font); sub_font.setPointSize(max(10, base_font.pointSize() - 2))
        p.setFont(sub_font); p.setPen(QtGui.QColor(COLOR_TEXT_MUTED))
        bottom_rect = pm.rect().adjusted(0, 0, 0, -12)
        p.drawText(bottom_rect, QtCore.Qt.AlignmentFlag.AlignHCenter | QtCore.Qt.AlignmentFlag.AlignBottom,
                   subtitle or "Loading…")

        p.end()
        return pm
