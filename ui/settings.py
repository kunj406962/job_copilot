"""Profile editing screen for updating saved contact and education data.

This module mirrors the first-run setup screen but loads existing profile data
and writes changes back to the local profile store.
"""

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QPushButton, QMessageBox, QScrollArea, QFrame
)
from PyQt6.QtCore import Qt
from core.profile import Profile, Education


class EducationEntry(QWidget):
    """Render one editable education block inside the settings screen."""

    def __init__(self, on_remove, degree="", institution="", year="", gpa=""):
        """Create an education entry prefilled with existing values.

        Args:
            on_remove: Callback to invoke when the entry is removed.
            degree: Existing degree value.
            institution: Existing institution value.
            year: Existing graduation year value.
            gpa: Existing GPA value.

        Returns:
            None
        """
        super().__init__()
        self.on_remove = on_remove
        self._build_ui(degree, institution, year, gpa)

    def _build_ui(self, degree, institution, year, gpa):
        """Build the settings education card and its inputs.

        Args:
            degree: Prefilled degree text.
            institution: Prefilled institution text.
            year: Prefilled graduation year text.
            gpa: Prefilled GPA text.

        Returns:
            None
        """
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        card = QFrame()
        card.setObjectName("card")
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(16, 16, 16, 16)
        card_layout.setSpacing(6)

        self.degree = self._field(card_layout, "Degree *", degree)
        self.institution = self._field(card_layout, "Institution *", institution)

        row = QHBoxLayout()
        self.year = self._field_widget(year, "e.g. 2025")
        self.gpa = self._field_widget(gpa, "e.g. 3.8  (optional)")
        row.addWidget(self._labelled(self.year, "Graduation Year *"))
        row.addWidget(self._labelled(self.gpa, "GPA"))
        card_layout.addLayout(row)

        remove_btn = QPushButton("Remove")
        remove_btn.setObjectName("danger")
        
        remove_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        remove_btn.clicked.connect(self.on_remove)
        card_layout.addSpacing(4)
        card_layout.addWidget(remove_btn, alignment=Qt.AlignmentFlag.AlignRight)

        layout.addWidget(card)

    def _field(self, layout, label, value="") -> QLineEdit:
        """Create a labeled text field with an initial value.

        Args:
            layout: Parent layout to receive the label and field.
            label: Label text to display.
            value: Initial field value.

        Returns:
            The created QLineEdit.
        """
        field = QLineEdit()
        field.setFixedHeight(40)
        field.setText(value)
        layout.addWidget(QLabel(label))
        layout.addWidget(field)
        return field

    def _field_widget(self, value="", placeholder="") -> QLineEdit:
        """Create a line edit with an initial value and placeholder.

        Args:
            value: Initial field value.
            placeholder: Placeholder text to show when empty.

        Returns:
            The created QLineEdit.
        """
        field = QLineEdit()
        field.setFixedHeight(40)
        field.setText(value)
        field.setPlaceholderText(placeholder)
        return field

    def _labelled(self, field, label) -> QWidget:
        """Wrap an input field with a label for compact layout placement.

        Args:
            field: The field to wrap.
            label: Label text to display.

        Returns:
            A QWidget containing the label and field.
        """
        wrapper = QWidget()
        layout = QVBoxLayout(wrapper)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)
        layout.addWidget(QLabel(label))
        layout.addWidget(field)
        return wrapper

    def get_data(self) -> dict:
        """Collect the current education entry values.

        Returns:
            A dictionary containing degree, institution, year, and GPA.
        """
        return {
            "degree": self.degree.text().strip(),
            "institution": self.institution.text().strip(),
            "year": self.year.text().strip(),
            "gpa": self.gpa.text().strip() or None,
        }


class SettingsScreen(QWidget):
    """Edit the saved profile and education data."""

    def __init__(self):
        """Create the settings screen and load any saved profile.

        Returns:
            None
        """
        super().__init__()
        self.edu_entries = []
        self._build_ui()
        self._load_profile()

    def _build_ui(self):
        """Build the settings form and scrollable content area.

        Returns:
            None
        """
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)

        self.container = QWidget()
        self.layout = QVBoxLayout(self.container)
        self.layout.setSpacing(6)
        self.layout.setContentsMargins(48, 40, 48, 40)

        title = QLabel("Settings")
        title.setObjectName("title")
        self.layout.addWidget(title)

        subtitle = QLabel("Update your profile and education details.")
        subtitle.setObjectName("subtitle")
        self.layout.addWidget(subtitle)

        self.layout.addSpacing(24)

        # ── Contact ──
        self.layout.addWidget(self._section_label("Contact Information"))
        self.layout.addSpacing(8)

        self.name_input = self._field(self.layout, "Full Name *")
        self.email_input = self._field(self.layout, "Email *")

        row1 = QHBoxLayout()
        self.phone_input = self._field_widget()
        self.location_input = self._field_widget()
        row1.addWidget(self._labelled(self.phone_input, "Phone"))
        row1.addWidget(self._labelled(self.location_input, "Location"))
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

        self.edu_container = QVBoxLayout()
        self.edu_container.setSpacing(12)
        self.layout.addLayout(self.edu_container)

        add_edu_btn = QPushButton("+ Add Another Degree")
        add_edu_btn.setObjectName("secondary")
        
        add_edu_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        add_edu_btn.clicked.connect(lambda: self._add_education())
        self.layout.addWidget(add_edu_btn)

        self.layout.addSpacing(32)

        save_btn = QPushButton("Save Changes")
        save_btn.setFixedHeight(48)
        save_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        save_btn.clicked.connect(self._save)
        self.layout.addWidget(save_btn)

        self.layout.addStretch()
        scroll.setWidget(self.container)
        outer.addWidget(scroll)

    def _load_profile(self):
        """Populate the form with the saved profile if one exists.

        Returns:
            None
        """
        try:
            p = Profile.load()
        except Exception:
            return

        self.name_input.setText(p.name or "")
        self.email_input.setText(p.email or "")
        self.phone_input.setText(p.phone or "")
        self.location_input.setText(p.location or "")
        self.linkedin_input.setText(p.linkedin or "")
        self.github_input.setText(p.github or "")

        for edu in p.education:
            self._add_education(
                degree=edu.degree,
                institution=edu.institution,
                year=edu.graduation_year,
                gpa=edu.gpa or "",
            )

        if not p.education:
            self._add_education()

    def _add_education(self, degree="", institution="", year="", gpa=""):
        """Append a new education entry to the settings form.

        Args:
            degree: Prefilled degree text.
            institution: Prefilled institution text.
            year: Prefilled graduation year text.
            gpa: Prefilled GPA text.

        Returns:
            None
        """
        entry = EducationEntry(
            on_remove=lambda: self._remove_education(entry),
            degree=degree,
            institution=institution,
            year=year,
            gpa=gpa,
        )
        self.edu_entries.append(entry)
        self.edu_container.addWidget(entry)

    def _remove_education(self, entry):
        """Remove an education entry unless it is the last one.

        Args:
            entry: The education widget to remove.

        Returns:
            None
        """
        if len(self.edu_entries) == 1:
            QMessageBox.warning(self, "Cannot Remove", "At least one education entry is required.")
            return
        self.edu_entries.remove(entry)
        self.edu_container.removeWidget(entry)
        entry.deleteLater()

    def _section_label(self, text) -> QLabel:
        """Create a consistent section label for the settings form.

        Args:
            text: Label text to display.

        Returns:
            The configured QLabel.
        """
        label = QLabel(text)
        label.setObjectName("section_label")
        return label

    def _field(self, layout, label) -> QLineEdit:
        """Create a labeled required input field.

        Args:
            layout: Parent layout to receive the field.
            label: Label text to display.

        Returns:
            The created QLineEdit.
        """
        field = QLineEdit()
        field.setFixedHeight(40)
        layout.addWidget(QLabel(label))
        layout.addWidget(field)
        layout.addSpacing(4)
        return field

    def _field_widget(self, placeholder="") -> QLineEdit:
        """Create a plain line edit used inside a labeled wrapper.

        Args:
            placeholder: Placeholder text to show when empty.

        Returns:
            The created QLineEdit.
        """
        field = QLineEdit()
        field.setFixedHeight(40)
        field.setPlaceholderText(placeholder)
        return field

    def _labelled(self, field, label) -> QWidget:
        """Wrap a field with a label for compact row layouts.

        Args:
            field: The field to wrap.
            label: Label text to display.

        Returns:
            A QWidget containing the label and field.
        """
        wrapper = QWidget()
        layout = QVBoxLayout(wrapper)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)
        layout.addWidget(QLabel(label))
        layout.addWidget(field)
        return wrapper

    def _save(self):
        """Validate the form and persist the updated profile.

        Returns:
            None

        Side Effects:
            Shows validation dialogs, writes profile.json, and displays a
            success dialog after saving.
        """
        name = self.name_input.text().strip()
        email = self.email_input.text().strip()

        missing = []
        if not name:  missing.append("Full Name")
        if not email: missing.append("Email")

        education_list = []
        for i, entry in enumerate(self.edu_entries):
            data = entry.get_data()
            if not data["degree"]:   missing.append(f"Degree (Education #{i+1})")
            if not data["institution"]: missing.append(f"Institution (Education #{i+1})")
            if not data["year"]:     missing.append(f"Graduation Year (Education #{i+1})")
            if not any([not data["degree"], not data["institution"], not data["year"]]):
                education_list.append(Education(
                    degree=data["degree"],
                    institution=data["institution"],
                    graduation_year=data["year"],
                    gpa=data["gpa"],
                ))

        if missing:
            QMessageBox.warning(self, "Missing Fields",
                "Please fill in:\n\n" + "\n".join(f"  • {f}" for f in missing))
            return

        Profile(
            name=name,
            email=email,
            phone=self.phone_input.text().strip() or None,
            linkedin=self.linkedin_input.text().strip() or None,
            github=self.github_input.text().strip() or None,
            location=self.location_input.text().strip() or None,
            education=education_list,
        ).save()

        QMessageBox.information(self, "Saved", "Profile updated successfully.")
