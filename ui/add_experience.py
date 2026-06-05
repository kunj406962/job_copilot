from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QPushButton, QTextEdit, QComboBox, QScrollArea, QFrame,
    QMessageBox
)
from PyQt6.QtCore import Qt
from core.database import add_chunk, get_all_chunks


CATEGORY_OPTIONS = [
    ("Project", "project"),
    ("Work Experience / Job", "job"),
    ("Technical Skill", "skill"),
    ("Soft Skill", "softskill"),
]

CATEGORY_HINTS = {
    "project":   "e.g. Built a React frontend with Node.js",
    "job":       "e.g. Processed customer transactions and resolved complaints",
    "skill":     "e.g. React, Node.js, Express, MongoDB",
    "softskill": "e.g. Led sprint planning and coordinated 3 developers",
}


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


class ChunkCard(QFrame):
    def __init__(self, text: str, category: str):
        super().__init__()
        self.setObjectName("card")
        layout = QHBoxLayout(self)
        layout.setContentsMargins(16, 12, 16, 12)
        layout.setSpacing(12)

        badge = QLabel(category.upper())
        badge.setFixedWidth(90)
        badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
        badge.setStyleSheet(self._badge_style(category))
        layout.addWidget(badge)

        text_label = QLabel(text)
        text_label.setWordWrap(True)
        text_label.setStyleSheet("color: #1A1A2E; font-size: 12px;")
        layout.addWidget(text_label, stretch=1)

    def _badge_style(self, category: str) -> str:
        colors = {
            "project":   "background-color: #EEF1FD; color: #4361EE;",
            "job":       "background-color: #E8F5E9; color: #2E7D32;",
            "skill":     "background-color: #FFF8E1; color: #F57F17;",
            "softskill": "background-color: #FCE4EC; color: #C62828;",
        }
        base = colors.get(category, "background-color: #F1F3F5; color: #6C757D;")
        return f"{base} border-radius: 6px; padding: 4px 8px; font-size: 11px; font-weight: 700;"


class AddExperienceScreen(QWidget):
    def __init__(self):
        super().__init__()
        self.bullet_entries = []
        self._build_ui()
        self._load_chunks()

    def _build_ui(self):
        outer = QHBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        # ── Left Panel ──
        left_scroll = QScrollArea()
        left_scroll.setWidgetResizable(True)
        left_scroll.setFrameShape(QFrame.Shape.NoFrame)
        left_scroll.setFixedWidth(440)

        left = QWidget()
        self.left_layout = QVBoxLayout(left)
        self.left_layout.setContentsMargins(32, 32, 32, 32)
        self.left_layout.setSpacing(8)

        title = QLabel("Add Experience")
        title.setObjectName("title")
        self.left_layout.addWidget(title)

        subtitle = QLabel("Add one entry per project or job. Use separate bullets for each point.")
        subtitle.setObjectName("subtitle")
        subtitle.setWordWrap(True)
        self.left_layout.addWidget(subtitle)

        self.left_layout.addSpacing(16)

        self.left_layout.addWidget(self._label("Category"))
        self.category_combo = QComboBox()
        for display, _ in CATEGORY_OPTIONS:
            self.category_combo.addItem(display)
        self.category_combo.currentIndexChanged.connect(self._on_category_change)
        self.left_layout.addWidget(self.category_combo)

        self.left_layout.addSpacing(4)

        self.left_layout.addWidget(self._label("Project / Job Name"))
        self.source_input = QLineEdit()
        self.source_input.setPlaceholderText("e.g. YYC Track, Superstore, Tech Skills")
        self.left_layout.addWidget(self.source_input)

        self.left_layout.addSpacing(12)

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
        save_btn.clicked.connect(self._save_all)
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
        chunks_title = QLabel("Stored Experience")
        chunks_title.setObjectName("title")
        right_header.addWidget(chunks_title)

        self.count_label = QLabel("0 entries")
        self.count_label.setObjectName("subtitle")
        self.count_label.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        right_header.addWidget(self.count_label)
        right_layout.addLayout(right_header)

        right_layout.addSpacing(8)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)

        self.chunks_container = QWidget()
        self.chunks_layout_right = QVBoxLayout(self.chunks_container)
        self.chunks_layout_right.setSpacing(8)
        self.chunks_layout_right.setContentsMargins(0, 0, 0, 0)
        self.chunks_layout_right.addStretch()

        scroll.setWidget(self.chunks_container)
        right_layout.addWidget(scroll)
        outer.addWidget(right, stretch=1)

    def _label(self, text: str) -> QLabel:
        label = QLabel(text)
        label.setStyleSheet("font-weight: 600; color: #1A1A2E;")
        return label

    def _on_category_change(self, index: int):
        _, category = CATEGORY_OPTIONS[index]
        hint = CATEGORY_HINTS[category]
        for entry in self.bullet_entries:
            entry.text_input.setPlaceholderText(hint)

    def _add_bullet(self):
        _, category = CATEGORY_OPTIONS[self.category_combo.currentIndex()]
        hint = CATEGORY_HINTS[category]
        entry = BulletEntry(
            placeholder=hint,
            on_remove=lambda: self._remove_bullet(entry),
        )
        self.bullet_entries.append(entry)
        self.bullets_layout.addWidget(entry)

    def _remove_bullet(self, entry):
        if len(self.bullet_entries) == 1:
            QMessageBox.warning(self, "Cannot Remove", "At least one bullet point is required.")
            return
        self.bullet_entries.remove(entry)
        self.bullets_layout.removeWidget(entry)
        entry.deleteLater()

    def _save_all(self):
        _, category = CATEGORY_OPTIONS[self.category_combo.currentIndex()]
        source = self.source_input.text().strip()
        bullets = [e.text() for e in self.bullet_entries if e.text()]

        if not bullets:
            QMessageBox.warning(self, "Missing Content", "Please enter at least one bullet point.")
            return

        errors = []
        for bullet in bullets:
            full_text = f"{bullet} — {source}" if source else bullet
            try:
                add_chunk(full_text, category)
            except Exception as e:
                errors.append(str(e))

        if errors:
            QMessageBox.critical(self, "Error", "Some bullets failed:\n\n" + "\n".join(errors))
        else:
            self.source_input.clear()
            for entry in self.bullet_entries:
                entry.text_input.clear()
            while len(self.bullet_entries) > 1:
                entry = self.bullet_entries[-1]
                self.bullet_entries.remove(entry)
                self.bullets_layout.removeWidget(entry)
                entry.deleteLater()

        self._load_chunks()

    def _load_chunks(self):
        while self.chunks_layout_right.count() > 1:
            item = self.chunks_layout_right.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        chunks = get_all_chunks()
        self.count_label.setText(f"{len(chunks)} entries")

        for chunk in reversed(chunks):
            card = ChunkCard(chunk["text"], chunk["category"])
            self.chunks_layout_right.insertWidget(0, card)
