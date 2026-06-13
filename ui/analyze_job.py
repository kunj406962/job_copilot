from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QTextEdit, QScrollArea, QFrame, QProgressBar, QMessageBox,
    QCheckBox, QLineEdit
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal
from core.generator import extract_skills, analyze_gaps, search_entries, generate_documents
from core.docx_builder import build_resume, build_cover_letter
from core.history import save_analysis
from core.profile import Profile
from core.skills import load_skills
import os


class SearchWorker(QThread):
    finished = pyqtSignal(dict, dict, dict)  # skills, gap_analysis, search_results
    error = pyqtSignal(str)
    status = pyqtSignal(str)

    def __init__(self, jd_text: str, profile: Profile):
        super().__init__()
        self.jd_text = jd_text
        self.profile = profile

    def run(self):
        try:
            import core.embeddings as emb
            emb._status_callback = lambda msg: self.status.emit(msg)

            skills_data = load_skills()
            self.status.emit("Extracting skills from job description...")
            skills = extract_skills(self.jd_text)
            gap_analysis = analyze_gaps(skills, skills_data)

            self.status.emit("Searching your experience...")
            search_results = search_entries(self.jd_text, skills)

            emb._status_callback = None
            self.finished.emit(skills, gap_analysis, search_results)
        except Exception as e:
            self.error.emit(str(e))


class GenerateWorker(QThread):
    finished = pyqtSignal(dict)
    error = pyqtSignal(str)
    status = pyqtSignal(str)

    def __init__(self, jd_text: str, profile: Profile, selected_entries: list):
        super().__init__()
        self.jd_text = jd_text
        self.profile = profile
        self.selected_entries = selected_entries

    def run(self):
        try:
            import core.embeddings as emb
            emb._status_callback = lambda msg: self.status.emit(msg)
            skills_data = load_skills()
            self.status.emit("Generating resume content...")
            docs = generate_documents(
                self.jd_text, self.profile,
                self.selected_entries, skills_data
            )
            emb._status_callback = None
            self.finished.emit(docs)
        except Exception as e:
            self.error.emit(str(e))


class SkillRow(QWidget):
    def __init__(self, skill: str, status: str, confidence: int, skill_type: str):
        super().__init__()
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 4, 0, 4)
        layout.setSpacing(12)

        icons = {"strong": "✅", "partial": "⚠️", "missing": "❌"}
        icon = QLabel(icons.get(status, "❌"))
        icon.setFixedWidth(24)
        layout.addWidget(icon)

        name_col = QVBoxLayout()
        name_col.setSpacing(0)
        skill_label = QLabel(skill)
        skill_label.setStyleSheet("font-weight: 600; font-size: 12px; color: #1A1A2E;")
        type_label = QLabel(skill_type.replace("_", " ").title())
        type_label.setStyleSheet("font-size: 10px; color: #6C757D;")
        name_col.addWidget(skill_label)
        name_col.addWidget(type_label)
        name_widget = QWidget()
        name_widget.setLayout(name_col)
        name_widget.setFixedWidth(160)
        layout.addWidget(name_widget)

        bar = QProgressBar()
        bar.setValue(confidence)
        bar.setFixedHeight(8)
        bar.setTextVisible(False)
        color = "#2E7D32" if status == "strong" else "#F57F17" if status == "partial" else "#E63946"
        bar.setStyleSheet(
            f"QProgressBar::chunk {{ background-color: {color}; border-radius: 4px; }}"
            "QProgressBar { background-color: #DEE2E6; border-radius: 4px; border: none; }"
        )
        layout.addWidget(bar, stretch=1)

        pct = QLabel(f"{confidence}%")
        pct.setFixedWidth(40)
        pct.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        pct.setStyleSheet("font-size: 12px; color: #6C757D;")
        layout.addWidget(pct)


class EntryCheckbox(QFrame):
    def __init__(self, entry: dict):
        super().__init__()
        self.entry = entry
        self.setObjectName("card")
        layout = QHBoxLayout(self)
        layout.setContentsMargins(12, 10, 12, 10)
        layout.setSpacing(12)

        self.checkbox = QCheckBox()
        self.checkbox.setChecked(entry.get("ai_pick", False))
        layout.addWidget(self.checkbox)

        info = QVBoxLayout()
        info.setSpacing(2)

        name_row = QHBoxLayout()
        name = QLabel(entry["name"])
        name.setStyleSheet("font-weight: 700; font-size: 12px; color: #1A1A2E;")
        name_row.addWidget(name)

        if entry.get("ai_pick"):
            ai_badge = QLabel("AI Pick")
            ai_badge.setStyleSheet(
                "background-color: #EEF1FD; color: #4361EE; border-radius: 4px;"
                "padding: 2px 6px; font-size: 10px; font-weight: 700;"
            )
            name_row.addWidget(ai_badge)
        name_row.addStretch()

        score = QLabel(f"Score: {round(entry.get('score', 0) * 100)}%")
        score.setStyleSheet("font-size: 10px; color: #6C757D;")
        name_row.addWidget(score)

        info.addLayout(name_row)

        if entry.get("stack"):
            stack = QLabel(entry["stack"])
            stack.setStyleSheet("font-size: 11px; color: #6C757D;")
            stack.setWordWrap(True)
            info.addWidget(stack)

        type_badge = QLabel(entry["type"].upper())
        colors = {
            "project":   "background-color: #EEF1FD; color: #4361EE;",
            "job":       "background-color: #E8F5E9; color: #2E7D32;",
            "softskill": "background-color: #FCE4EC; color: #C62828;",
        }
        type_badge.setStyleSheet(
            f"{colors.get(entry['type'], '')} border-radius: 4px;"
            "padding: 2px 6px; font-size: 10px; font-weight: 700;"
        )
        info.addWidget(type_badge)
        layout.addLayout(info, stretch=1)

    def is_checked(self) -> bool:
        return self.checkbox.isChecked()


class AnalyzeJobScreen(QWidget):
    def __init__(self):
        super().__init__()
        self.skills = None
        self.gap_analysis = None
        self.search_results = None
        self.docs = None
        self.jd_text = ""
        self.entry_checkboxes = []
        self.search_worker = None
        self.generate_worker = None
        self._build_ui()

    def _build_ui(self):
        outer = QHBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        # ── Left Panel ──
        left = QWidget()
        left.setFixedWidth(420)
        left_layout = QVBoxLayout(left)
        left_layout.setContentsMargins(32, 32, 32, 32)
        left_layout.setSpacing(8)

        title = QLabel("Analyze Job")
        title.setObjectName("title")
        left_layout.addWidget(title)

        subtitle = QLabel("Paste a job description to get your match score and tailored resume.")
        subtitle.setObjectName("subtitle")
        subtitle.setWordWrap(True)
        left_layout.addWidget(subtitle)

        left_layout.addSpacing(16)

        left_layout.addWidget(self._label("Job Name"))
        self.job_name_input = QLineEdit()
        self.job_name_input.setPlaceholderText("e.g. Senior Dev at Shopify")
        left_layout.addWidget(self.job_name_input)

        left_layout.addSpacing(4)

        left_layout.addWidget(self._label("Job Description"))
        self.jd_input = QTextEdit()
        self.jd_input.setPlaceholderText("Paste the full job description here...")
        left_layout.addWidget(self.jd_input, stretch=1)

        left_layout.addSpacing(12)

        self.analyse_btn = QPushButton("Analyse →")
        self.analyse_btn.setFixedHeight(44)
        self.analyse_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.analyse_btn.clicked.connect(self._run_search)
        left_layout.addWidget(self.analyse_btn)

        self.status_label = QLabel("")
        self.status_label.setObjectName("subtitle")
        self.status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.status_label.setWordWrap(True)
        left_layout.addWidget(self.status_label)

        outer.addWidget(left)

        # ── Divider ──
        divider = QFrame()
        divider.setFrameShape(QFrame.Shape.VLine)
        divider.setStyleSheet("color: #DEE2E6;")
        outer.addWidget(divider)

        # ── Right Panel ──
        right_scroll = QScrollArea()
        right_scroll.setWidgetResizable(True)
        right_scroll.setFrameShape(QFrame.Shape.NoFrame)

        self.right = QWidget()
        self.right_layout = QVBoxLayout(self.right)
        self.right_layout.setContentsMargins(32, 32, 32, 32)
        self.right_layout.setSpacing(16)

        self.placeholder = QLabel("Run an analysis to see your results here.")
        self.placeholder.setObjectName("subtitle")
        self.placeholder.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.right_layout.addWidget(self.placeholder)
        self.right_layout.addStretch()

        right_scroll.setWidget(self.right)
        outer.addWidget(right_scroll, stretch=1)

    def _label(self, text: str) -> QLabel:
        label = QLabel(text)
        label.setStyleSheet("font-weight: 600; color: #1A1A2E;")
        return label

    def _set_loading(self, loading: bool, text: str = ""):
        self.analyse_btn.setEnabled(not loading)
        self.analyse_btn.setText("Analysing..." if loading else "Analyse →")
        self.status_label.setText(text)

    def _run_search(self):
        self.jd_text = self.jd_input.toPlainText().strip()
        if not self.jd_text:
            QMessageBox.warning(self, "Missing Input", "Please paste a job description first.")
            return

        try:
            profile = Profile.load()
        except Exception as e:
            QMessageBox.critical(self, "Profile Error", str(e))
            return

        self._set_loading(True, "Extracting skills...")
        self._clear_results()

        self.search_worker = SearchWorker(self.jd_text, profile)
        self.search_worker.finished.connect(self._on_search_done)
        self.search_worker.error.connect(self._on_error)
        self.search_worker.status.connect(self.status_label.setText)
        self.search_worker.start()

    def _on_search_done(self, skills: dict, gap_analysis: dict, search_results: dict):
        self.skills = skills
        self.gap_analysis = gap_analysis
        self.search_results = search_results
        self._set_loading(False)
        self._render_results(gap_analysis, search_results)

    def _on_error(self, error: str):
        self._set_loading(False)
        QMessageBox.critical(self, "Error", f"Something went wrong:\n\n{error}")

    def _clear_results(self):
        self.entry_checkboxes = []
        while self.right_layout.count():
            item = self.right_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

    def _render_results(self, gap_analysis: dict, search_results: dict):
        # ── Overall Score ──
        score_card = QFrame()
        score_card.setObjectName("card")
        score_layout = QVBoxLayout(score_card)
        score_layout.setContentsMargins(24, 20, 24, 20)
        score_layout.setSpacing(4)

        score_title = QLabel("Overall Match")
        score_title.setObjectName("section_label")
        score_layout.addWidget(score_title)

        score = gap_analysis["overall_match"]
        color = "#2E7D32" if score >= 70 else "#F57F17" if score >= 40 else "#E63946"
        score_label = QLabel(f"{score}%")
        score_label.setStyleSheet(f"font-size: 48px; font-weight: 700; color: {color};")
        score_layout.addWidget(score_label)

        score_bar = QProgressBar()
        score_bar.setValue(score)
        score_bar.setFixedHeight(10)
        score_bar.setTextVisible(False)
        score_layout.addWidget(score_bar)
        self.right_layout.addWidget(score_card)

        # ── Skill Breakdown ──
        skills_card = QFrame()
        skills_card.setObjectName("card")
        skills_layout = QVBoxLayout(skills_card)
        skills_layout.setContentsMargins(24, 20, 24, 20)
        skills_layout.setSpacing(4)

        skills_title = QLabel("Skill Breakdown")
        skills_title.setObjectName("section_label")
        skills_layout.addWidget(skills_title)
        skills_layout.addSpacing(8)

        for skill_data in gap_analysis["skills"]:
            row = SkillRow(
                skill=skill_data["skill"],
                status=skill_data["status"],
                confidence=skill_data["confidence"],
                skill_type=skill_data["type"],
            )
            skills_layout.addWidget(row)
        self.right_layout.addWidget(skills_card)

        # ── Missing Skills ──
        if gap_analysis["missing_skills"]:
            missing_card = QFrame()
            missing_card.setObjectName("card")
            missing_layout = QVBoxLayout(missing_card)
            missing_layout.setContentsMargins(24, 20, 24, 20)
            missing_layout.setSpacing(8)

            missing_title = QLabel("Gaps to Address")
            missing_title.setObjectName("section_label")
            missing_layout.addWidget(missing_title)

            for skill in gap_analysis["missing_skills"]:
                pill = QLabel(f"  {skill}  ")
                pill.setStyleSheet(
                    "background-color: #FCE4EC; color: #C62828; border-radius: 6px;"
                    "padding: 4px 10px; font-size: 12px; font-weight: 600;"
                )
                missing_layout.addWidget(pill, alignment=Qt.AlignmentFlag.AlignLeft)
            self.right_layout.addWidget(missing_card)

        # ── Project Selector ──
        selector_card = QFrame()
        selector_card.setObjectName("card")
        selector_layout = QVBoxLayout(selector_card)
        selector_layout.setContentsMargins(24, 20, 24, 20)
        selector_layout.setSpacing(8)

        selector_header = QHBoxLayout()
        selector_title = QLabel("Select Experience to Include")
        selector_title.setObjectName("section_label")
        selector_header.addWidget(selector_title)

        research_btn = QPushButton("Re-search")
        research_btn.setObjectName("secondary")
        research_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        research_btn.clicked.connect(self._run_search)
        selector_header.addWidget(research_btn, alignment=Qt.AlignmentFlag.AlignRight)
        selector_layout.addLayout(selector_header)

        hint = QLabel("AI picks are pre-checked. Check or uncheck to customise.")
        hint.setObjectName("subtitle")
        selector_layout.addWidget(hint)

        self.entry_checkboxes = []
        for entry in search_results["ranked"]:
            cb = EntryCheckbox(entry)
            self.entry_checkboxes.append(cb)
            selector_layout.addWidget(cb)

        self.right_layout.addWidget(selector_card)

        # ── Generate Button ──
        self.generate_btn = QPushButton("Generate Resume & Cover Letter →")
        self.generate_btn.setFixedHeight(48)
        self.generate_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.generate_btn.clicked.connect(self._run_generate)
        self.right_layout.addWidget(self.generate_btn)

        self.right_layout.addStretch()

    def _run_generate(self):
        selected = [cb.entry for cb in self.entry_checkboxes if cb.is_checked()]

        if not selected:
            QMessageBox.warning(self, "Nothing Selected", "Please select at least one entry.")
            return

        try:
            profile = Profile.load()
        except Exception as e:
            QMessageBox.critical(self, "Profile Error", str(e))
            return

        self.generate_btn.setEnabled(False)
        self.generate_btn.setText("Generating...")
        self.status_label.setText("Generating resume content...")

        self.generate_worker = GenerateWorker(self.jd_text, profile, selected)
        self.generate_worker.finished.connect(self._on_generate_done)
        self.generate_worker.error.connect(self._on_generate_error)
        self.generate_worker.status.connect(self.status_label.setText)
        self.generate_worker.start()

    def _on_generate_done(self, docs: dict):
        self.docs = docs
        self.generate_btn.setEnabled(True)
        self.generate_btn.setText("Generate Resume & Cover Letter →")
        self.status_label.setText("")

        try:
            profile = Profile.load()
        except Exception as e:
            QMessageBox.critical(self, "Profile Error", str(e))
            return

        try:
            resume_path = build_resume(
                profile,
                docs["summary"],
                docs["projects"],
                docs["experience"],
                "resume.docx",
            )
            cover_path = build_cover_letter(
                profile,
                docs["cover_letter"],
                "cover_letter.docx",
            )
        except Exception as e:
            QMessageBox.critical(self, "Build Error", str(e))
            return

        # Save to history
        selected = [cb.entry for cb in self.entry_checkboxes if cb.is_checked()]
        job_name = self.job_name_input.text().strip() or "Untitled Job"
        try:
            save_analysis(
                job_name=job_name,
                jd_text=self.jd_text,
                skills=self.skills,
                gap_analysis=self.gap_analysis,
                selected_entries=selected,
                summary=docs["summary"],
                projects=docs["projects"],
                experience=docs["experience"],
                cover_letter=docs["cover_letter"],
            )
        except Exception:
            pass  # history save failure shouldn't block the user

        output_dir = os.path.abspath("./output/resumes")
        if os.name == "nt":
            os.startfile(output_dir)
        else:
            os.system(f"xdg-open '{output_dir}'")

        QMessageBox.information(
            self, "Done!",
            f"Files saved to:\n\n{resume_path}\n{cover_path}"
        )

    def _on_generate_error(self, error: str):
        self.generate_btn.setEnabled(True)
        self.generate_btn.setText("Generate Resume & Cover Letter →")
        self.status_label.setText("")
        QMessageBox.critical(self, "Generation Failed", f"Something went wrong:\n\n{error}")
