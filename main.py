# main.py
import os
import sys
from PyQt6 import QtCore, QtGui, QtWidgets

# ---- Proje içi importlar ----
from windows.main_window import MainWindow
from windows.splash_screen import SplashScreen
from utils.icons import make_app_icon_png
from theme.colors import (
    COLOR_PRIMARY_BG,
    COLOR_SECONDARY_BG,
    COLOR_TEXT,
    COLOR_TEXT_MUTED,
)

# -------------------------------------------------------------------
# High-DPI (Qt6 güvenli)
# -------------------------------------------------------------------
def set_qt_attributes():
    try:
        QtGui.QGuiApplication.setHighDpiScaleFactorRoundingPolicy(
            QtCore.Qt.HighDpiScaleFactorRoundingPolicy.PassThrough
        )
    except Exception:
        pass

# -------------------------------------------------------------------
# Uygulama kimliği
# -------------------------------------------------------------------
def set_app_identity():
    QtCore.QCoreApplication.setOrganizationName("YourOrg")
    QtCore.QCoreApplication.setOrganizationDomain("yourorg.example")
    QtCore.QCoreApplication.setApplicationName("Personal Assistant")
    QtCore.QCoreApplication.setApplicationVersion("1.0.0")

# -------------------------------------------------------------------
# Font yükleme (Inter varsa kullan)
# -------------------------------------------------------------------
def load_inter_font(assets_dir: str) -> bool:
    ok = False
    for name in ("Inter-Regular.ttf", "Inter-Medium.ttf", "Inter-SemiBold.ttf", "Inter-Bold.ttf"):
        path = os.path.join(assets_dir, name)
        if os.path.exists(path):
            fid = QtGui.QFontDatabase.addApplicationFont(path)
            if fid != -1:
                ok = True
    return ok

def apply_default_font(preferred_family: str | None = None, point_size: int = 14):
    fam = preferred_family or QtWidgets.QApplication.font().family()
    f = QtGui.QFont(fam, point_size)
    QtWidgets.QApplication.setFont(f)

# -------------------------------------------------------------------
# Palet (dark) + Global QSS
# -------------------------------------------------------------------
def apply_palette(app: QtWidgets.QApplication):
    pal = app.palette()
    q = QtGui.QColor
    pal.setColor(QtGui.QPalette.ColorRole.Window,         q(COLOR_PRIMARY_BG))
    pal.setColor(QtGui.QPalette.ColorRole.Base,           q(COLOR_PRIMARY_BG))
    pal.setColor(QtGui.QPalette.ColorRole.AlternateBase,  q(COLOR_SECONDARY_BG))
    pal.setColor(QtGui.QPalette.ColorRole.Text,           q(COLOR_TEXT))
    pal.setColor(QtGui.QPalette.ColorRole.WindowText,     q(COLOR_TEXT))
    pal.setColor(QtGui.QPalette.ColorRole.PlaceholderText,q(COLOR_TEXT_MUTED))
    pal.setColor(QtGui.QPalette.ColorRole.ToolTipBase,    q(COLOR_SECONDARY_BG))
    pal.setColor(QtGui.QPalette.ColorRole.ToolTipText,    q(COLOR_TEXT))
    pal.setColor(QtGui.QPalette.ColorRole.Button,         q(COLOR_SECONDARY_BG))
    pal.setColor(QtGui.QPalette.ColorRole.ButtonText,     q(COLOR_TEXT))
    app.setPalette(pal)

def apply_global_qss(app: QtWidgets.QApplication):
    qss = f"""
    QToolTip {{
        background: {COLOR_SECONDARY_BG};
        color: {COLOR_TEXT};
        border: 1px solid #3a3a3a;
        padding: 4px 6px;
        border-radius: 6px;
    }}
    QScrollBar:vertical {{
        background: {COLOR_SECONDARY_BG};
        width: 10px; margin: 0; border: 0;
    }}
    QScrollBar::handle:vertical {{
        background: #555; min-height: 36px; border-radius: 5px;
    }}
    QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0; }}
    QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {{ background: transparent; }}
    QLineEdit, QPlainTextEdit, QTextEdit {{
        background: {COLOR_SECONDARY_BG};
        color: {COLOR_TEXT};
        border: 1px solid #3a3a3a;
        border-radius: 8px;
        padding: 6px 8px;
    }}
    """
    app.setStyleSheet(qss)

# -------------------------------------------------------------------
# Hata yakalama (debug için)
# -------------------------------------------------------------------
def install_exception_hook():
    def _hook(exc_type, exc, tb):
        import traceback
        msg = "".join(traceback.format_exception(exc_type, exc, tb))
        print(msg, file=sys.stderr)
        try:
            QtWidgets.QMessageBox.critical(None, "Unexpected Error", msg[:2000])
        except Exception:
            pass
    sys.excepthook = _hook

# -------------------------------------------------------------------
# Argümanlar
# -------------------------------------------------------------------
def parse_args():
    import argparse
    p = argparse.ArgumentParser()
    p.add_argument("--no-splash", action="store_true", help="Splash ekranını gösterme")
    p.add_argument("--font-dir", default="assets/fonts", help="Inter fontlarının olduğu klasör")
    p.add_argument("--icon", default="assets/app_icon.png", help="Uygulama ikon yolu (PNG önerilir)")
    return p.parse_args()

# -------------------------------------------------------------------
# main — Login yok, Splash en önde (≥1200 ms)
# -------------------------------------------------------------------
def main():
    set_qt_attributes()
    set_app_identity()
    install_exception_hook()

    args = parse_args()

    app = QtWidgets.QApplication(sys.argv)
    app.setStyle("Fusion")

    # Yol çözümü
    base_dir = os.path.dirname(os.path.abspath(__file__))
    icon_path = args.icon if os.path.isabs(args.icon) else os.path.join(base_dir, args.icon)
    font_dir  = args.font_dir if os.path.isabs(args.font_dir) else os.path.join(base_dir, args.font_dir)

    # Uygulama ikonu (HiDPI çoklu boyut)
    if os.path.exists(icon_path):
        app.setWindowIcon(make_app_icon_png(icon_path))

    # Fontlar
    if load_inter_font(font_dir):
        apply_default_font("Inter", 14)
    else:
        apply_default_font(point_size=14)

    # Tema/QSS
    apply_palette(app)
    apply_global_qss(app)

    # Splash (her durumda min 1200 ms, ve en önde)
    splash = None
    timer = QtCore.QElapsedTimer(); timer.start()
    MIN_SPLASH_MS = 1200
    if not args.no_splash:
        splash = SplashScreen(icon_path=icon_path, title="Personal Assistant", subtitle="Loading modules…")
        splash.show()
        splash.raise_()
        splash.activateWindow()
        QtWidgets.QApplication.processEvents(QtCore.QEventLoop.ProcessEventsFlag.AllEvents)

    # Splash minimum süresini bekle
    if splash:
        elapsed = timer.elapsed()
        if elapsed < MIN_SPLASH_MS:
            QtCore.QThread.msleep(MIN_SPLASH_MS - elapsed)

    # Ana pencere
    win = MainWindow()
    win.resize(1400, 900)
    win.show()

    if splash:
        splash.finish(win)

    return app.exec()

if __name__ == "__main__":
    sys.exit(main())
