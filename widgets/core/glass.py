from PyQt6 import QtCore, QtGui, QtWidgets

class GlassHighlight(QtWidgets.QWidget):
    def __init__(self, radius=10, tint=QtGui.QColor("#11989C"), parent=None):
        super().__init__(parent)
        self._radius = float(radius)
        self._tint = QtGui.QColor(tint)
        self.setAttribute(QtCore.Qt.WidgetAttribute.WA_TranslucentBackground)
        shadow = QtWidgets.QGraphicsDropShadowEffect(self)
        shadow.setBlurRadius(18)
        shadow.setOffset(0, 3)
        shadow.setColor(QtGui.QColor(0, 0, 0, 60))
        self.setGraphicsEffect(shadow)

    def paintEvent(self, e):
        p = QtGui.QPainter(self)
        p.setRenderHint(QtGui.QPainter.RenderHint.Antialiasing, True)
        rf = QtCore.QRectF(self.rect())

        path = QtGui.QPainterPath()
        path.addRoundedRect(rf.adjusted(0, 0, -1, -1), self._radius, self._radius)

        # arka cam degrade
        base = QtGui.QLinearGradient(rf.topLeft(), rf.bottomLeft())
        base.setColorAt(0.0, QtGui.QColor(255, 255, 255, 70))
        base.setColorAt(0.5, QtGui.QColor(255, 255, 255, 40))
        base.setColorAt(1.0, QtGui.QColor(255, 255, 255, 30))
        p.fillPath(path, base)

        # renkli tint
        tint = QtGui.QColor(self._tint)
        tint.setAlpha(65)
        p.fillPath(path, tint)

        # üst parlama
        capf = QtCore.QRectF(rf.left()+2.0, rf.top()+2.0, rf.width()-4.0, max(6.0, rf.height()/3.0))
        glossPath = QtGui.QPainterPath()
        glossPath.addRoundedRect(capf, max(0.0, self._radius-2.0), max(0.0, self._radius-2.0))
        gloss = QtGui.QLinearGradient(capf.topLeft(), capf.center())
        gloss.setColorAt(0.0, QtGui.QColor(255, 255, 255, 90))
        gloss.setColorAt(1.0, QtGui.QColor(255, 255, 255, 0))
        p.fillPath(glossPath, gloss)

        # kenar
        pen = QtGui.QPen(QtGui.QColor(255, 255, 255, 110))
        pen.setWidth(1)
        p.setPen(pen)
        p.drawPath(path)
