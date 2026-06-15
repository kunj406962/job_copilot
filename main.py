"""Application entry point for Job Copilot.

This module boots the Qt application, applies the global stylesheet, and
chooses the first window based on whether a local profile already exists.
It depends on the UI layer and profile storage helpers.
"""

import sys
from PyQt6.QtWidgets import QApplication
from PyQt6.QtGui import QFont
from ui.styles import STYLESHEET
from ui.setup_screen import SetupScreen
from ui.main_window import MainWindow
from core.profile import profile_exists


def main():
    """Start the application and display the correct initial window.

    Returns:
        None

    Side Effects:
        Creates the QApplication, applies styling, shows a window, and exits
        the process when the Qt event loop finishes.
    """
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
    """Close setup and open the main window after first-run onboarding.

    Args:
        app: The active QApplication instance.
        setup_window: The onboarding window to close before opening main UI.

    Returns:
        None

    Side Effects:
        Replaces the setup window with the persistent main window and stores a
        reference on the application object to keep it alive.
    """
    setup_window.close()
    main_window = MainWindow()
    main_window.show()
    app._main_window = main_window  # keep reference alive


if __name__ == "__main__":
    main()
