from __future__ import annotations
from PyQt6 import QtCore, QtGui, QtWidgets
from theme.colors import (
    COLOR_PRIMARY_BG, COLOR_TEXT, COLOR_TEXT_MUTED, COLOR_ACCENT
)

class MiniMonthCalendar(QtWidgets.QFrame):
    """
    Küçük aylık takvim.
    - Üstte özel başlık: [prev]  Ay YYYY  [next]
    - PNG/SVG ile ileri-geri ikonlarını dışarıdan ayarlayabilirsin.
    - Sadece DIŞ ÇERÇEVE var; zemin şeffaf (arka planı parent gösterir).
    - Hafta sonu (Cts/Paz) yazıları kırmızı DEĞİL, muted renkte.
    """
    dateSelected = QtCore.pyqtSignal(QtCore.QDate)

    def __init__(self, parent=None, anchor_date: QtCore.QDate | None = None,
                 prev_icon: str | QtGui.QIcon | None = None,
                 next_icon: str | QtGui.QIcon | None = None,
                 icon_px: int = 18):
        super().__init__(parent)
        self.setObjectName("MiniMonthCalendar")
        self._icon_px = icon_px
        self._prev_icon = prev_icon
        self._next_icon = next_icon
        self._marked: dict[QtCore.QDate, int] = {}

        self._build_ui()
        self._apply_style()

        # Başlangıç tarihi
        self.setAnchorDate(anchor_date or QtCore.QDate.currentDate())

        # Hafta sonu formatını uygula (kırmızı yerine muted)
        self._apply_weekend_format()

        # Dışarıdan ikon verilmişse uygula
        if prev_icon or next_icon:
            self.setNavIcons(prev_icon, next_icon, icon_px)

    # ---------- UI ----------
    def _build_ui(self):
        root = QtWidgets.QVBoxLayout(self)
        root.setContentsMargins(8, 8, 8, 8)
        root.setSpacing(6)

        # Header (custom)
        header = QtWidgets.QWidget(self)
        h = QtWidgets.QHBoxLayout(header)
        h.setContentsMargins(4, 0, 4, 0)
        h.setSpacing(4)

        self.btn_prev = QtWidgets.QToolButton(header)
        self.btn_prev.setCursor(QtCore.Qt.CursorShape.PointingHandCursor)
        self.btn_prev.setAutoRaise(True)
        self.btn_prev.setIconSize(QtCore.QSize(self._icon_px, self._icon_px))
        self.btn_prev.clicked.connect(self._go_prev_month)

        self.lbl_month = QtWidgets.QLabel("", header)
        self.lbl_month.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)

        self.btn_next = QtWidgets.QToolButton(header)
        self.btn_next.setCursor(QtCore.Qt.CursorShape.PointingHandCursor)
        self.btn_next.setAutoRaise(True)
        self.btn_next.setIconSize(QtCore.QSize(self._icon_px, self._icon_px))
        self.btn_next.clicked.connect(self._go_next_month)

        h.addWidget(self.btn_prev)
        h.addWidget(self.lbl_month, 1)
        h.addWidget(self.btn_next)
        root.addWidget(header)

        # QCalendarWidget (nav bar kapalı)
        self.cal = QtWidgets.QCalendarWidget(self)
        self.cal.setNavigationBarVisible(False)
        self.cal.setVerticalHeaderFormat(QtWidgets.QCalendarWidget.VerticalHeaderFormat.NoVerticalHeader)
        self.cal.setHorizontalHeaderFormat(QtWidgets.QCalendarWidget.HorizontalHeaderFormat.ShortDayNames)
        self.cal.setFirstDayOfWeek(QtCore.Qt.DayOfWeek.Monday)
        self.cal.setGridVisible(False)
        self.cal.selectionChanged.connect(self._emit_selected)
        root.addWidget(self.cal)

    def _apply_style(self):
        # Sadece DIŞ ÇERÇEVE: arka plan şeffaf
        self.setStyleSheet("""
        QFrame#MiniMonthCalendar {
            background: transparent;
            border: 1px solid #3a3a3a;
            border-radius: 8px;
        }
        """)
        # Calendar & header metinleri
        cal_qss = f"""
        QLabel {{
            color: {COLOR_TEXT};
        }}
        QToolButton {{
            background: transparent;
            border: none;
            padding: 6px; /* tıklama alanı */
            color: {COLOR_TEXT};
        }}
        QToolButton:hover {{
            background: rgba(255,255,255,0.06);
            border-radius: 6px;
        }}
        /* Takvim içi */
        QCalendarWidget QWidget {{
            color: {COLOR_TEXT};
        }}
        QCalendarWidget QAbstractItemView:enabled {{
            background: {COLOR_PRIMARY_BG}; /* iç zemin: primary */
            selection-background-color: {COLOR_ACCENT};
            selection-color: #ffffff;
            outline: none;
        }}
        QCalendarWidget QTableView {{
            background: {COLOR_PRIMARY_BG};
            gridline-color: #3a3a3a;
        }}
        """
        self.cal.setStyleSheet(cal_qss)

    # ---------- Weekend format ----------
    def _apply_weekend_format(self):
        """Cumartesi & Pazar günlerinin yazı rengini muted yap."""
        fmt = QtGui.QTextCharFormat()
        fmt.setForeground(QtGui.QBrush(QtGui.QColor(COLOR_TEXT_MUTED)))
        self.cal.setWeekdayTextFormat(QtCore.Qt.DayOfWeek.Saturday, fmt)
        self.cal.setWeekdayTextFormat(QtCore.Qt.DayOfWeek.Sunday, fmt)

    # ---------- Public API ----------
    def setAnchorDate(self, date: QtCore.QDate):
        if not isinstance(date, QtCore.QDate) or not date.isValid():
            date = QtCore.QDate.currentDate()
        self.cal.setSelectedDate(date)
        self.cal.setCurrentPage(date.year(), date.month())
        self._refresh_header()

    def setMarkedDates(self, marks: dict[QtCore.QDate, int]):
        """İşaretli günleri hafif renkle vurgula (count>0). Weekend formatı korunur."""
        self._marked = marks or {}
        # Önce tüm özel formatları sıfırla
        self.cal.setDateTextFormat(QtCore.QDate(), QtGui.QTextCharFormat())
        # Weekend renklerini tekrar uygula
        self._apply_weekend_format()

        # İşaretli günlere hafif arka plan
        if self._marked:
            fmt = QtGui.QTextCharFormat()
            fmt.setBackground(QtGui.QColor(255, 255, 255, 18))
            for d, count in self._marked.items():
                if isinstance(d, QtCore.QDate) and d.isValid() and count:
                    self.cal.setDateTextFormat(d, fmt)

    def setNavIcons(self, prev_icon: str | QtGui.QIcon | None,
                    next_icon: str | QtGui.QIcon | None,
                    icon_px: int | None = None):
        """İleri/geri butonlarına dışarıdan PNG/SVG ikon ata."""
        if icon_px:
            self._icon_px = int(icon_px)
            self.btn_prev.setIconSize(QtCore.QSize(self._icon_px, self._icon_px))
            self.btn_next.setIconSize(QtCore.QSize(self._icon_px, self._icon_px))

        def _as_icon(x) -> QtGui.QIcon | None:
            if x is None:
                return None
            if isinstance(x, QtGui.QIcon):
                return x
            return QtGui.QIcon(str(x))

        ic_prev = _as_icon(prev_icon)
        ic_next = _as_icon(next_icon)

        if ic_prev:
            self.btn_prev.setIcon(ic_prev)
            self.btn_prev.setText("")
        else:
            self.btn_prev.setIcon(QtGui.QIcon())
            self.btn_prev.setText("‹")

        if ic_next:
            self.btn_next.setIcon(ic_next)
            self.btn_next.setText("")
        else:
            self.btn_next.setIcon(QtGui.QIcon())
            self.btn_next.setText("›")

    # ---------- İç mantık ----------
    def _refresh_header(self):
        y = self.cal.yearShown()
        m = self.cal.monthShown()
        month_name = QtCore.QLocale.system().standaloneMonthName(m, QtCore.QLocale.FormatType.LongFormat)
        self.lbl_month.setText(f"{month_name} {y}")

    def _go_prev_month(self):
        self.cal.showPreviousMonth()
        self._refresh_header()

    def _go_next_month(self):
        self.cal.showNextMonth()
        self._refresh_header()

    def _emit_selected(self):
        self.dateSelected.emit(self.cal.selectedDate())
