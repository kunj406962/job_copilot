import sys
from PyQt6.QtWidgets import QApplication
from PyQt6.QtGui import QFont
from ui.styles import STYLESHEET
from ui.setup_screen import SetupScreen
from ui.main_window import MainWindow
from core.profile import profile_exists


def main():
    app = QApplication(sys.argv)
    app.setStyleSheet(STYLESHEET)
    app.setFont(QFont("Segoe UI", 13))

    if not profile_exists():
        window = SetupScreen(on_complete=lambda: _launch_main(app, window))
    else:
        window = MainWindow()

    window.show()
    sys.exit(app.exec())


def _launch_main(app, setup_window):
    setup_window.close()
    main_window = MainWindow()
    main_window.show()
    app._main_window = main_window  # keep reference alive


if __name__ == "__main__":
    main()
