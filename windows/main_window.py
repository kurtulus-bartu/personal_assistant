# windows/main_window.py
from PyQt6 import QtWidgets, QtCore, QtGui

from widgets.layout.navigator import MiniNavigator, PageSpec
from pages.planner_page import PlannerPage
from pages.health_activity_page import HealthActivityPage
from pages.performance_page import PerformancePage
from pages.journal_page import JournalPage

from theme.colors import COLOR_PRIMARY_BG
from utils.icons import make_app_icon_png


class MainWindow(QtWidgets.QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Personal Assistant")
        self.setWindowIcon(make_app_icon_png("assets/app_icon.png"))

        root = QtWidgets.QWidget()
        h = QtWidgets.QHBoxLayout(root)
        h.setContentsMargins(0, 0, 0, 0)
        h.setSpacing(0)

        # Navigator (ölçüler isteklerine göre)
        self.nav = MiniNavigator(icon_size=28, bar_width=64, lr_margin=6, logo_size=28)
        self.nav.setAppLogo("assets/app_icon.png")
        self.nav.setChatbotIcon("assets/icons/chatbot.png")
        h.addWidget(self.nav)

        # Orta: sayfa yığını
        self.stack = QtWidgets.QStackedWidget()
        h.addWidget(self.stack, 1)

        # --- SAYFALAR ---
        # PlannerPage'i ÖNCE OLUŞTUR → sonra takvim buton ikonlarını ata
        self.page_planner = PlannerPage()
        # >>> Aylık takvim ileri/geri PNG ikonlarını burada veriyoruz
        # Left panel holds the month navigation buttons; expose via
        # ``left_panel_widget`` in ``PlannerPage``.
        self.page_planner.left_panel_widget.setMonthNavIcons(
            "assets/icons/chev_left.png",   # senin sol yön PNG'in
            "assets/icons/chev_right.png",  # senin sağ yön PNG'in
            icon_px=18                      # buton üzerindeki ikon boyutu
        )

        # Diğer sayfalar
        self.page_health = HealthActivityPage()
        self.page_perf   = PerformancePage()
        self.page_journal= JournalPage()
        self.page_pomo   = self.page_planner.pomo

        # Stack'e ekle
        self.pages = {}
        self._add_page("planner",     self.page_planner, "Planner")
        self._add_page("health",      self.page_health,  "Health & Activity")
        self._add_page("performance", self.page_perf,    "Performance")
        self._add_page("journal",     self.page_journal, "Journal")
        self._add_page("pomodoro",    self.page_pomo,    "Pomodoro")

        # Navigator sayfaları
        self.nav.setPages([
            PageSpec("planner",     "Planner",     "assets/icons/calendar.png",   "Planner (G P)"),
            PageSpec("health",      "Health",      "assets/icons/health.png",     "Sağlık & Aktivite"),
            PageSpec("performance", "Performance", "assets/icons/performance.png","Performans"),
            PageSpec("journal",     "Journal",     "assets/icons/journal.png",    "Günlük"),
            PageSpec("pomodoro",    "Pomodoro",    "assets/icons/pomodoro.png",   "Pomodoro"),
        ], active_key="planner")

        self.nav.pageRequested.connect(self._on_page_requested)

        self.setCentralWidget(root)
        # arka planı tema rengine sabitle
        self.setStyleSheet(self.styleSheet() + f" QMainWindow {{ background: {COLOR_PRIMARY_BG}; }}")

    # yardımcılar
    def _add_page(self, key: str, widget: QtWidgets.QWidget, _label: str):
        idx = self.stack.addWidget(widget)
        self.pages[key] = idx

    def _on_page_requested(self, key: str):
        if key in self.pages:
            self.stack.setCurrentIndex(self.pages[key])
