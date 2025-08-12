from __future__ import annotations
from PyQt6 import QtGui, QtCore
try:
    from PyQt6.QtSvg import QSvgRenderer
except Exception:
    QSvgRenderer = None


def _with_hints(p: QtGui.QPainter):
    p.setRenderHints(
        QtGui.QPainter.RenderHint.Antialiasing
        | QtGui.QPainter.RenderHint.TextAntialiasing
        | QtGui.QPainter.RenderHint.SmoothPixmapTransform,
        True
    )


def _trim_transparent(pm: QtGui.QPixmap) -> QtGui.QPixmap:
    img = pm.toImage().convertToFormat(QtGui.QImage.Format.Format_RGBA8888)
    w, h = img.width(), img.height()
    left, right, top, bottom = w, -1, h, -1
    ptr = img.constBits(); ptr.setsize(img.sizeInBytes()); buf = memoryview(ptr)
    for y in range(h):
        row = buf[y * w * 4:(y + 1) * w * 4]
        for x in range(w):
            if row[x * 4 + 3]:  # alpha>0
                if x < left: left = x
                if x > right: right = x
                if y < top: top = y
                if y > bottom: bottom = y
    if right < left or bottom < top:
        return pm
    rect = QtCore.QRect(left, top, right - left + 1, bottom - top + 1)
    return pm.copy(rect)


def _to_square_centered(pm: QtGui.QPixmap, size: int) -> QtGui.QPixmap:
    pm = _trim_transparent(pm)
    canvas = QtGui.QPixmap(size, size)
    canvas.fill(QtCore.Qt.GlobalColor.transparent)
    scaled = pm.scaled(
        size, size,
        QtCore.Qt.AspectRatioMode.KeepAspectRatio,
        QtCore.Qt.TransformationMode.SmoothTransformation
    )
    x = (size - scaled.width()) // 2
    y = (size - scaled.height()) // 2
    p = QtGui.QPainter(canvas); _with_hints(p)
    p.drawPixmap(x, y, scaled)
    p.end()
    return canvas


def _load_png_square(path: str, size: int) -> QtGui.QPixmap:
    base = QtGui.QPixmap(path)
    if base.isNull():
        base = QtGui.QIcon(path).pixmap(size, size)
    return _to_square_centered(base, size)


def _load_svg_square(path: str, size: int) -> QtGui.QPixmap:
    if QSvgRenderer is None:
        return _load_png_square(path, size)
    pm = QtGui.QPixmap(size, size)
    pm.fill(QtCore.Qt.GlobalColor.transparent)
    r = QSvgRenderer(path)
    p = QtGui.QPainter(pm); _with_hints(p)
    r.render(p, QtCore.QRectF(0, 0, size, size))
    p.end()
    return pm


def _tint(pm: QtGui.QPixmap, color: str | None) -> QtGui.QPixmap:
    if not color:
        return pm
    out = QtGui.QPixmap(pm.size())
    out.fill(QtCore.Qt.GlobalColor.transparent)
    p = QtGui.QPainter(out); _with_hints(p)
    p.drawPixmap(0, 0, pm)
    p.setCompositionMode(QtGui.QPainter.CompositionMode.CompositionMode_SourceIn)
    p.fillRect(out.rect(), QtGui.QColor(color))
    p.end()
    return out


def make_icon_pm_pair(path_or_qicon,
                      size: int = 30,
                      normal_color: str | None = None,
                      active_color: str | None = None) -> tuple[QtGui.QPixmap, QtGui.QPixmap]:
    """
    Navigator/toolbar için: NORMAL ve AKTİF kare QPixmap çifti döner.
    PNG → trim+center; SVG → kare raster. İsteğe bağlı tint.
    """
    if isinstance(path_or_qicon, QtGui.QIcon):
        base = _to_square_centered(path_or_qicon.pixmap(size, size), size)
    else:
        path = str(path_or_qicon)
        ext = path.lower().rsplit(".", 1)[-1] if "." in path else ""
        base = _load_svg_square(path, size) if ext == "svg" else _load_png_square(path, size)
    return _tint(base, normal_color), _tint(base, active_color)


def make_app_icon_png(path: str) -> QtGui.QIcon:
    """
    Uygulama (window/dock) ikonu için HiDPI dostu, çok boyutlu QIcon.
    PNG kare değilse de görünür içerik trimlenir ve merkezlenir.
    """
    icon = QtGui.QIcon()
    for s in [16, 20, 22, 24, 32, 48, 64, 72, 96, 128, 256, 512]:
        pm = _load_png_square(path, s)
        icon.addPixmap(pm)
    return icon
