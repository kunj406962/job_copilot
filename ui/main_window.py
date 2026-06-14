from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QHBoxLayout, QVBoxLayout,
    QPushButton, QLabel, QStackedWidget, QFrame
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont
from ui.add_experience import AddExperienceScreen
from ui.analyze_job import AnalyzeJobScreen
from ui.skills_screen import SkillsScreen
from ui.settings import SettingsScreen
from ui.history_screen import HistoryScreen


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Job Copilot")
        self.setMinimumSize(1100, 700)
        self._build_ui()
        self._switch(0)

    def _build_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        layout = QHBoxLayout(central)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # ── Sidebar ──
        sidebar = QWidget()
        sidebar.setObjectName("sidebar")
        sidebar.setFixedWidth(220)
        sidebar_layout = QVBoxLayout(sidebar)
        sidebar_layout.setContentsMargins(16, 24, 16, 24)
        sidebar_layout.setSpacing(4)

        app_name = QLabel("Job Copilot")
        app_name.setFont(QFont("Segoe UI", 16, QFont.Weight.Bold))
        app_name.setStyleSheet("color: #4361EE; padding: 0 8px 16px 8px;")
        sidebar_layout.addWidget(app_name)

        self.nav_buttons = []
        nav_items = [
            ("Add Experience", 0),
            ("Analyze Job", 1),
            ("History", 2),
            ("Skills", 3),
            ("Settings", 4),
        ]
        for label, index in nav_items:
            btn = QPushButton(label)
            btn.setObjectName("nav_btn")
            btn.setCheckable(True)
            btn.setFixedHeight(44)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.clicked.connect(lambda _, i=index: self._switch(i))
            sidebar_layout.addWidget(btn)
            self.nav_buttons.append(btn)

        sidebar_layout.addStretch()

        version = QLabel("v1.0.0")
        version.setObjectName("subtitle")
        version.setAlignment(Qt.AlignmentFlag.AlignCenter)
        sidebar_layout.addWidget(version)

        layout.addWidget(sidebar)

        divider = QFrame()
        divider.setFrameShape(QFrame.Shape.VLine)
        divider.setStyleSheet("color: #DEE2E6;")
        layout.addWidget(divider)

        self.stack = QStackedWidget()
        self.analyze_screen = AnalyzeJobScreen()

        self.stack.addWidget(AddExperienceScreen())
        self.stack.addWidget(self.analyze_screen)
        self.stack.addWidget(HistoryScreen(on_open_record=self._open_history_record))
        self.stack.addWidget(SkillsScreen())
        self.stack.addWidget(SettingsScreen())
        layout.addWidget(self.stack, stretch=1)

    def _switch(self, index: int):
        self.stack.setCurrentIndex(index)
        for i, btn in enumerate(self.nav_buttons):
            btn.setChecked(i == index)

    def _open_history_record(self, record: dict):
        self.analyze_screen.load_record(record)
        self._switch(1)
