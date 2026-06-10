from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QPushButton, QTextEdit, QComboBox, QScrollArea, QFrame,
    QMessageBox, QStackedWidget
)
from PyQt6.QtCore import Qt
from core.database import add_entry, get_all_entries, entry_count


TYPE_OPTIONS = [
    ("Project", "project"),
    ("Work Experience / Job", "job"),
    ("Soft Skill", "softskill"),
]


class BulletEntry(QWidget):
    def __init__(self, placeholder: str, on_remove):
        super().__init__()
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)
        layout.setAlignment(Qt.AlignmentFlag.AlignVCenter)

        self.text_input = QTextEdit()
        self.text_input.setFixedHeight(68)
        self.text_input.setPlaceholderText(placeholder)
        layout.addWidget(self.text_input, stretch=1)

        remove_btn = QPushButton("Remove")
        remove_btn.setObjectName("danger")
        remove_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        remove_btn.clicked.connect(on_remove)
        layout.addWidget(remove_btn, alignment=Qt.AlignmentFlag.AlignVCenter)

    def text(self) -> str:
        return self.text_input.toPlainText().strip()


class EntryCard(QFrame):
    def __init__(self, entry: dict):
        super().__init__()
        self.setObjectName("card")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 12, 16, 12)
        layout.setSpacing(6)

        # Header row
        header = QHBoxLayout()
        badge = QLabel(entry["type"].upper())
        badge.setStyleSheet(self._badge_style(entry["type"]))
        header.addWidget(badge)

        name = QLabel(entry["name"])
        name.setStyleSheet("font-weight: 700; font-size: 13px; color: #1A1A2E;")
        header.addWidget(name)
        header.addStretch()
        layout.addLayout(header)

        if entry.get("stack"):
            stack = QLabel(entry["stack"])
            stack.setStyleSheet("font-size: 11px; color: #6C757D;")
            stack.setWordWrap(True)
            layout.addWidget(stack)

        for bullet in entry["bullets"]:
            b = QLabel(f"• {bullet}")
            b.setWordWrap(True)
            b.setStyleSheet("font-size: 12px; color: #1A1A2E; padding-left: 4px;")
            layout.addWidget(b)

    def _badge_style(self, entry_type: str) -> str:
        colors = {
            "project":   "background-color: #EEF1FD; color: #4361EE;",
            "job":       "background-color: #E8F5E9; color: #2E7D32;",
            "softskill": "background-color: #FCE4EC; color: #C62828;",
        }
        base = colors.get(entry_type, "background-color: #F1F3F5; color: #6C757D;")
        return f"{base} border-radius: 6px; padding: 4px 10px; font-size: 11px; font-weight: 700;"


class AddExperienceScreen(QWidget):
    def __init__(self):
        super().__init__()
        self.bullet_entries = []
        self._build_ui()
        self._load_entries()

    def _build_ui(self):
        outer = QHBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        # ── Left Panel ──
        left_scroll = QScrollArea()
        left_scroll.setWidgetResizable(True)
        left_scroll.setFrameShape(QFrame.Shape.NoFrame)
        left_scroll.setFixedWidth(460)

        left = QWidget()
        self.left_layout = QVBoxLayout(left)
        self.left_layout.setContentsMargins(32, 32, 32, 32)
        self.left_layout.setSpacing(8)

        title = QLabel("Add Experience")
        title.setObjectName("title")
        self.left_layout.addWidget(title)

        subtitle = QLabel("Add one entry per project or job with all its bullets.")
        subtitle.setObjectName("subtitle")
        subtitle.setWordWrap(True)
        self.left_layout.addWidget(subtitle)

        self.left_layout.addSpacing(16)

        # Type dropdown
        self.left_layout.addWidget(self._label("Type"))
        self.type_combo = QComboBox()
        for display, _ in TYPE_OPTIONS:
            self.type_combo.addItem(display)
        self.type_combo.currentIndexChanged.connect(self._on_type_change)
        self.left_layout.addWidget(self.type_combo)

        self.left_layout.addSpacing(4)

        # Name field (always shown)
        self.left_layout.addWidget(self._label("Name *"))
        self.name_input = QLineEdit()
        self.name_input.setPlaceholderText("e.g. YYC Track, Superstore")
        self.left_layout.addWidget(self.name_input)

        self.left_layout.addSpacing(4)

        # Swappable fields — project vs job
        self.stack_label = self._label("Tech Stack")
        self.left_layout.addWidget(self.stack_label)
        self.stack_input = QLineEdit()
        self.stack_input.setPlaceholderText("e.g. React, Node.js, MongoDB, Docker")
        self.left_layout.addWidget(self.stack_input)

        self.left_layout.addSpacing(4)

        self.role_label = self._label("Role / Job Title")
        self.left_layout.addWidget(self.role_label)
        self.role_input = QLineEdit()
        self.role_input.setPlaceholderText("e.g. Team Member, Sales Associate")
        self.left_layout.addWidget(self.role_input)

        self.left_layout.addSpacing(4)

        self.desc_label = self._label("Description")
        self.left_layout.addWidget(self.desc_label)
        self.desc_input = QLineEdit()
        self.desc_input.setPlaceholderText("e.g. Capstone Web Application (Live)")
        self.left_layout.addWidget(self.desc_input)

        self.left_layout.addSpacing(12)

        # Bullets
        self.left_layout.addWidget(self._label("Bullet Points"))
        self.bullets_layout = QVBoxLayout()
        self.bullets_layout.setSpacing(8)
        self.left_layout.addLayout(self.bullets_layout)
        self._add_bullet()

        self.left_layout.addSpacing(4)

        add_bullet_btn = QPushButton("+ Add Bullet")
        add_bullet_btn.setObjectName("secondary")
        add_bullet_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        add_bullet_btn.clicked.connect(self._add_bullet)
        self.left_layout.addWidget(add_bullet_btn)

        self.left_layout.addSpacing(16)

        save_btn = QPushButton("Save to Profile")
        save_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        save_btn.clicked.connect(self._save)
        self.left_layout.addWidget(save_btn)

        self.left_layout.addStretch()
        left_scroll.setWidget(left)
        outer.addWidget(left_scroll)

        # ── Divider ──
        divider = QFrame()
        divider.setFrameShape(QFrame.Shape.VLine)
        divider.setStyleSheet("color: #DEE2E6;")
        outer.addWidget(divider)

        # ── Right Panel ──
        right = QWidget()
        right_layout = QVBoxLayout(right)
        right_layout.setContentsMargins(32, 32, 32, 32)
        right_layout.setSpacing(8)

        right_header = QHBoxLayout()
        right_title = QLabel("Stored Experience")
        right_title.setObjectName("title")
        right_header.addWidget(right_title)

        self.count_label = QLabel("0 entries")
        self.count_label.setObjectName("subtitle")
        self.count_label.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        right_header.addWidget(self.count_label)
        right_layout.addLayout(right_header)

        right_layout.addSpacing(8)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)

        self.entries_container = QWidget()
        self.entries_layout = QVBoxLayout(self.entries_container)
        self.entries_layout.setSpacing(12)
        self.entries_layout.setContentsMargins(0, 0, 0, 0)
        self.entries_layout.addStretch()

        scroll.setWidget(self.entries_container)
        right_layout.addWidget(scroll)
        outer.addWidget(right, stretch=1)

        # Set initial field visibility
        self._on_type_change(0)

    def _label(self, text: str) -> QLabel:
        label = QLabel(text)
        label.setStyleSheet("font-weight: 600; color: #1A1A2E;")
        return label

    def _on_type_change(self, index: int):
        _, entry_type = TYPE_OPTIONS[index]

        if entry_type == "softskill":
            self.stack_label.hide()
            self.stack_input.hide()
            self.role_label.hide()
            self.role_input.hide()
            self.desc_label.hide()
            self.desc_input.hide()
        elif entry_type == "job":
            self.stack_label.setText("Tech Stack (optional)")
            self.stack_input.setPlaceholderText("e.g. Python, Excel, Salesforce")
            self.stack_label.show()
            self.stack_input.show()
            self.role_label.setText("Job Title *")
            self.role_input.setPlaceholderText("e.g. Sales Associate, Cashier")
            self.role_label.show()
            self.role_input.show()
            self.desc_label.setText("Company")
            self.desc_input.setPlaceholderText("e.g. Superstore, Tim Hortons")
            self.desc_label.show()
            self.desc_input.show()
        else:  # project
            self.stack_label.setText("Tech Stack")
            self.stack_input.setPlaceholderText("e.g. React, Node.js, MongoDB, Docker")
            self.stack_label.show()
            self.stack_input.show()
            self.role_label.setText("Role")
            self.role_input.setPlaceholderText("e.g. Team Member, Solo Developer")
            self.role_label.show()
            self.role_input.show()
            self.desc_label.setText("Description")
            self.desc_input.setPlaceholderText("e.g. Capstone Web Application (Live)")
            self.desc_label.show()
            self.desc_input.show()

    def _add_bullet(self):
        _, entry_type = TYPE_OPTIONS[self.type_combo.currentIndex()]
        hints = {
            "project": "e.g. Built a full-stack MERN web application...",
            "job": "e.g. Processed customer transactions and resolved complaints...",
            "softskill": "e.g. Led sprint planning and coordinated 3 developers...",
        }
        entry = BulletEntry(
            placeholder=hints.get(entry_type, "Enter bullet point..."),
            on_remove=lambda: self._remove_bullet(entry),
        )
        self.bullet_entries.append(entry)
        self.bullets_layout.addWidget(entry)

    def _remove_bullet(self, entry):
        if len(self.bullet_entries) == 1:
            QMessageBox.warning(self, "Cannot Remove", "At least one bullet is required.")
            return
        self.bullet_entries.remove(entry)
        self.bullets_layout.removeWidget(entry)
        entry.deleteLater()

    def _save(self):
        _, entry_type = TYPE_OPTIONS[self.type_combo.currentIndex()]
        name = self.name_input.text().strip()
        stack = self.stack_input.text().strip()
        role = self.role_input.text().strip()
        desc = self.desc_input.text().strip()
        bullets = [e.text() for e in self.bullet_entries if e.text()]

        if not name:
            QMessageBox.warning(self, "Missing Field", "Please enter a name.")
            return
        if not bullets:
            QMessageBox.warning(self, "Missing Content", "Please enter at least one bullet.")
            return

        try:
            add_entry(
                entry_type=entry_type,
                name=name,
                bullets=bullets,
                stack=stack,
                role=role,
                description=desc,
            )
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to save:\n{e}")
            return

        # Clear form
        self.name_input.clear()
        self.stack_input.clear()
        self.role_input.clear()
        self.desc_input.clear()
        for entry in self.bullet_entries:
            entry.text_input.clear()
        while len(self.bullet_entries) > 1:
            entry = self.bullet_entries[-1]
            self.bullet_entries.remove(entry)
            self.bullets_layout.removeWidget(entry)
            entry.deleteLater()

        self._load_entries()

    def _load_entries(self):
        while self.entries_layout.count() > 1:
            item = self.entries_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        entries = get_all_entries()
        self.count_label.setText(f"{len(entries)} entries")

        for entry in reversed(entries):
            card = EntryCard(entry)
            self.entries_layout.insertWidget(0, card)