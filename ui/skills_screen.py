"""Skills registry management screen for categorized local skill data.

This module lets users add and remove skill categories and individual skills,
and it depends on the skills persistence helpers in core.skills.
"""

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QPushButton, QScrollArea, QFrame, QMessageBox
)
from PyQt6.QtCore import Qt
from core.skills import load_skills, add_category, remove_category, add_skill, remove_skill


class SkillPill(QWidget):
    """Render one removable skill chip inside a category card."""

    def __init__(self, skill: str, category: str, on_remove):
        """Create a pill for a single skill.

        Args:
            skill: The skill label to display.
            category: The owning category name.
            on_remove: Callback to invoke when the pill is removed.

        Returns:
            None
        """
        super().__init__()
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 2, 0, 2)
        layout.setSpacing(0)

        pill = QFrame()
        pill.setStyleSheet("background-color: #EEF1FD; border-radius: 6px;")
        pill_layout = QHBoxLayout(pill)
        pill_layout.setContentsMargins(10, 5, 8, 5)
        pill_layout.setSpacing(6)

        label = QLabel(skill)
        label.setStyleSheet("color: #4361EE; font-size: 12px; font-weight: 600; background: transparent;")
        pill_layout.addWidget(label)

        remove_btn = QPushButton("x")
        remove_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        remove_btn.setStyleSheet(
            "QPushButton { background: transparent; color: #4361EE; font-weight: 700;"
            "border: none; font-size: 12px; padding: 0px 2px; min-height: 0px; }"
            "QPushButton:hover { color: #E63946; }"
        )
        remove_btn.clicked.connect(on_remove)
        pill_layout.addWidget(remove_btn)

        layout.addWidget(pill)
        layout.addStretch()


class CategoryCard(QFrame):
    """Render one skills category, its pills, and its add/remove controls."""

    def __init__(self, category: str, skills: list, on_refresh):
        """Create a category card for the provided skill list.

        Args:
            category: The category name to display.
            skills: Skills currently stored in the category.
            on_refresh: Callback to reload the screen after edits.

        Returns:
            None
        """
        super().__init__()
        self.category = category
        self.on_refresh = on_refresh
        self.setObjectName("card")
        self._build_ui(skills)

    def _build_ui(self, skills: list):
        """Build the category card layout.

        Args:
            skills: Skills currently stored in the category.

        Returns:
            None
        """
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 16, 20, 16)
        layout.setSpacing(10)

        # Header
        header = QHBoxLayout()
        header.setAlignment(Qt.AlignmentFlag.AlignVCenter)

        cat_label = QLabel(self.category)
        cat_label.setStyleSheet("font-size: 13px; font-weight: 700; color: #1A1A2E;")
        header.addWidget(cat_label)

        header.addStretch()

        remove_cat_btn = QPushButton("Remove Category")
        remove_cat_btn.setObjectName("danger")
        remove_cat_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        remove_cat_btn.clicked.connect(self._remove_category)
        header.addWidget(remove_cat_btn)

        layout.addLayout(header)

        # Pills
        self.pills_layout = QVBoxLayout()
        self.pills_layout.setSpacing(4)
        layout.addLayout(self.pills_layout)

        if skills:
            for skill in skills:
                self._add_pill(skill)
        else:
            empty = QLabel("No skills yet — add one below.")
            empty.setStyleSheet("color: #6C757D; font-size: 12px;")
            self.pills_layout.addWidget(empty)

        # Add skill row
        add_row = QHBoxLayout()
        add_row.setSpacing(8)

        self.skill_input = QLineEdit()
        self.skill_input.setPlaceholderText("e.g. Python, React, Software Testing...")
        self.skill_input.returnPressed.connect(self._add_skill)
        add_row.addWidget(self.skill_input, stretch=1)

        add_btn = QPushButton("Add")
        add_btn.setObjectName("secondary")
        add_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        add_btn.clicked.connect(self._add_skill)
        add_row.addWidget(add_btn)

        layout.addLayout(add_row)

    def _add_pill(self, skill: str):
        """Add a rendered pill for one stored skill.

        Args:
            skill: The skill label to display.

        Returns:
            None
        """
        pill = SkillPill(
            skill=skill,
            category=self.category,
            on_remove=lambda: self._remove_skill(skill),
        )
        self.pills_layout.addWidget(pill)

    def _add_skill(self):
        """Persist a new skill from the input field.

        Returns:
            None
        """
        skill = self.skill_input.text().strip()
        if not skill:
            return
        add_skill(self.category, skill)
        self.skill_input.clear()
        self.on_refresh()

    def _remove_skill(self, skill: str):
        """Remove a skill from the category and refresh the screen.

        Args:
            skill: The skill label to remove.

        Returns:
            None
        """
        remove_skill(self.category, skill)
        self.on_refresh()

    def _remove_category(self):
        """Confirm and remove the entire category.

        Returns:
            None
        """
        reply = QMessageBox.question(
            self, "Remove Category",
            f"Remove '{self.category}' and all its skills?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply == QMessageBox.StandardButton.Yes:
            remove_category(self.category)
            self.on_refresh()


class SkillsScreen(QWidget):
    """Manage the categorized skills registry stored on disk."""

    def __init__(self):
        """Create the skills screen and load existing categories.

        Returns:
            None
        """
        super().__init__()
        self._build_ui()
        self._load()

    def _build_ui(self):
        """Build the skills screen layout.

        Returns:
            None
        """
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        # Top bar
        top_bar = QWidget()
        top_layout = QHBoxLayout(top_bar)
        top_layout.setContentsMargins(32, 20, 32, 20)
        top_layout.setSpacing(12)
        top_layout.setAlignment(Qt.AlignmentFlag.AlignVCenter)

        title = QLabel("Skills")
        title.setObjectName("title")
        top_layout.addWidget(title)

        top_layout.addStretch()

        self.cat_input = QLineEdit()
        self.cat_input.setFixedWidth(220)
        self.cat_input.setPlaceholderText("New category name...")
        self.cat_input.returnPressed.connect(self._add_category)
        top_layout.addWidget(self.cat_input)

        add_cat_btn = QPushButton("+ Add Category")
        add_cat_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        add_cat_btn.clicked.connect(self._add_category)
        top_layout.addWidget(add_cat_btn)

        outer.addWidget(top_bar)

        line = QFrame()
        line.setFrameShape(QFrame.Shape.HLine)
        line.setStyleSheet("color: #DEE2E6;")
        outer.addWidget(line)

        # Cards
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)

        self.cards_container = QWidget()
        self.cards_layout = QVBoxLayout(self.cards_container)
        self.cards_layout.setContentsMargins(32, 24, 32, 24)
        self.cards_layout.setSpacing(16)
        self.cards_layout.addStretch()

        scroll.setWidget(self.cards_container)
        outer.addWidget(scroll)

    def _add_category(self):
        """Persist a new category from the input field.

        Returns:
            None
        """
        category = self.cat_input.text().strip()
        if not category:
            return
        add_category(category)
        self.cat_input.clear()
        self._load()

    def _load(self):
        """Reload all category cards from the saved skills file.

        Returns:
            None
        """
        while self.cards_layout.count() > 1:
            item = self.cards_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        skills_data = load_skills()

        if not skills_data:
            empty = QLabel("No skill categories yet.\nClick '+ Add Category' to get started.")
            empty.setObjectName("subtitle")
            empty.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self.cards_layout.insertWidget(0, empty)
            return

        for category, skills in skills_data.items():
            card = CategoryCard(category=category, skills=skills, on_refresh=self._load)
            self.cards_layout.insertWidget(self.cards_layout.count() - 1, card)
