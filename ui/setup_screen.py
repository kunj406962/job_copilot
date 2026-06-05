from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QPushButton, QMessageBox, QScrollArea, QFrame
)
from PyQt6.QtCore import Qt
from core.profile import Profile, Education


class EducationEntry(QWidget):
    def __init__(self, on_remove):
        super().__init__()
        self.on_remove = on_remove
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)

        # Card frame
        card = QFrame()
        card.setObjectName("card")
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(16, 16, 16, 16)
        card_layout.setSpacing(6)

        # Degree + Institution
        self.degree = self._field(card_layout, "Degree (e.g. BSc Computer Science) *")
        self.institution = self._field(card_layout, "Institution *")

        # Year + GPA row
        row = QHBoxLayout()
        self.year = self._field_widget("e.g. 2025")
        self.gpa = self._field_widget("e.g. 3.8  (optional)")
        row.addWidget(self._labelled(self.year, "Graduation Year *"))
        row.addWidget(self._labelled(self.gpa, "GPA"))
        card_layout.addLayout(row)

        # Remove button
        remove_btn = QPushButton("Remove")
        remove_btn.setObjectName("danger")
        
        remove_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        remove_btn.clicked.connect(self.on_remove)
        card_layout.addSpacing(4)
        card_layout.addWidget(remove_btn, alignment=Qt.AlignmentFlag.AlignRight)

        layout.addWidget(card)

    def _field(self, layout, label: str) -> QLineEdit:
        field = QLineEdit()
        field.setFixedHeight(40)
        layout.addWidget(QLabel(label))
        layout.addWidget(field)
        return field

    def _field_widget(self, placeholder: str = "") -> QLineEdit:
        field = QLineEdit()
        field.setFixedHeight(40)
        field.setPlaceholderText(placeholder)
        return field

    def _labelled(self, field: QLineEdit, label: str) -> QWidget:
        wrapper = QWidget()
        layout = QVBoxLayout(wrapper)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)
        layout.addWidget(QLabel(label))
        layout.addWidget(field)
        return wrapper

    def get_data(self) -> dict:
        return {
            "degree": self.degree.text().strip(),
            "institution": self.institution.text().strip(),
            "year": self.year.text().strip(),
            "gpa": self.gpa.text().strip() or None,
        }


class SetupScreen(QWidget):
    def __init__(self, on_complete):
        super().__init__()
        self.on_complete = on_complete
        self.edu_entries = []
        self.setWindowTitle("Job Copilot — First Time Setup")
        self.setMinimumWidth(560)
        self.setMinimumHeight(680)
        self._build_ui()

    def _build_ui(self):
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)

        self.container = QWidget()
        self.layout = QVBoxLayout(self.container)
        self.layout.setSpacing(6)
        self.layout.setContentsMargins(48, 40, 48, 40)

        # ── Title ──
        title = QLabel("Welcome to Job Copilot")
        title.setObjectName("title")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.layout.addWidget(title)

        subtitle = QLabel("Set up your profile to get started. You can edit this anytime in Settings.")
        subtitle.setObjectName("subtitle")
        subtitle.setAlignment(Qt.AlignmentFlag.AlignCenter)
        subtitle.setWordWrap(True)
        self.layout.addWidget(subtitle)

        self.layout.addSpacing(24)

        # ── Contact Information ──
        self.layout.addWidget(self._section_label("Contact Information"))
        self.layout.addSpacing(8)

        self.name_input = self._field(self.layout, "Full Name *")
        self.email_input = self._field(self.layout, "Email *")

        row1 = QHBoxLayout()
        self.phone_input = self._field_widget()
        self.location_input = self._field_widget()
        row1.addWidget(self._labelled(self.phone_input, "Phone"))
        row1.addWidget(self._labelled(self.location_input, "Location (e.g. Calgary, AB)"))
        self.layout.addLayout(row1)

        row2 = QHBoxLayout()
        self.linkedin_input = self._field_widget()
        self.github_input = self._field_widget()
        row2.addWidget(self._labelled(self.linkedin_input, "LinkedIn URL"))
        row2.addWidget(self._labelled(self.github_input, "GitHub URL"))
        self.layout.addLayout(row2)

        self.layout.addSpacing(24)

        # ── Education ──
        self.layout.addWidget(self._section_label("Education"))
        self.layout.addSpacing(8)

        # Container for dynamic education entries
        self.edu_container = QVBoxLayout()
        self.edu_container.setSpacing(12)
        self.layout.addLayout(self.edu_container)

        # Add first entry by default
        self._add_education()

        # Add Education button
        add_edu_btn = QPushButton("+ Add Another Degree")
        add_edu_btn.setObjectName("secondary")
        
        add_edu_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        add_edu_btn.clicked.connect(self._add_education)
        self.layout.addWidget(add_edu_btn)

        self.layout.addSpacing(32)

        # ── Save Button ──
        save_btn = QPushButton("Save & Continue →")
        save_btn.setFixedHeight(48)
        save_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        save_btn.clicked.connect(self._save)
        self.layout.addWidget(save_btn)

        self.layout.addStretch()
        scroll.setWidget(self.container)
        outer.addWidget(scroll)

    def _add_education(self):
        entry = EducationEntry(on_remove=lambda: self._remove_education(entry))
        self.edu_entries.append(entry)
        self.edu_container.addWidget(entry)

    def _remove_education(self, entry: EducationEntry):
        if len(self.edu_entries) == 1:
            QMessageBox.warning(self, "Cannot Remove", "At least one education entry is required.")
            return
        self.edu_entries.remove(entry)
        self.edu_container.removeWidget(entry)
        entry.deleteLater()

    def _section_label(self, text: str) -> QLabel:
        label = QLabel(text)
        label.setObjectName("section_label")
        return label

    def _field(self, layout, label: str) -> QLineEdit:
        field = QLineEdit()
        field.setFixedHeight(40)
        layout.addWidget(QLabel(label))
        layout.addWidget(field)
        layout.addSpacing(4)
        return field

    def _field_widget(self, placeholder: str = "") -> QLineEdit:
        field = QLineEdit()
        field.setFixedHeight(40)
        field.setPlaceholderText(placeholder)
        return field

    def _labelled(self, field: QLineEdit, label: str) -> QWidget:
        wrapper = QWidget()
        layout = QVBoxLayout(wrapper)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)
        layout.addWidget(QLabel(label))
        layout.addWidget(field)
        return wrapper

    def _save(self):
        name = self.name_input.text().strip()
        email = self.email_input.text().strip()

        missing = []
        if not name:
            missing.append("Full Name")
        if not email:
            missing.append("Email")

        # Validate all education entries
        education_list = []
        for i, entry in enumerate(self.edu_entries):
            data = entry.get_data()
            edu_missing = []
            if not data["degree"]:
                edu_missing.append(f"Degree (Education #{i+1})")
            if not data["institution"]:
                edu_missing.append(f"Institution (Education #{i+1})")
            if not data["year"]:
                edu_missing.append(f"Graduation Year (Education #{i+1})")
            missing.extend(edu_missing)

            if not edu_missing:
                education_list.append(Education(
                    degree=data["degree"],
                    institution=data["institution"],
                    graduation_year=data["year"],
                    gpa=data["gpa"],
                ))

        if missing:
            QMessageBox.warning(
                self,
                "Missing Fields",
                "Please fill in the following required fields:\n\n" +
                "\n".join(f"  • {f}" for f in missing)
            )
            return

        profile = Profile(
            name=name,
            email=email,
            phone=self.phone_input.text().strip() or None,
            linkedin=self.linkedin_input.text().strip() or None,
            github=self.github_input.text().strip() or None,
            location=self.location_input.text().strip() or None,
            education=education_list,
        )
        profile.save()
        self.on_complete()
