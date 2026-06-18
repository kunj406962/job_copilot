from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QTextEdit, QScrollArea, QFrame, QProgressBar, QMessageBox,
    QCheckBox, QLineEdit
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal
from core.generator import (
    extract_skills, analyze_gaps, search_entries, generate_documents,
    suggest_gap_fixes,
)
from core.docx_builder import build_resume, build_cover_letter
from core.history import save_progress, save_docs
from core.profile import Profile
from core.skills import load_skills, add_skill
from core.database import update_bullet
import os


class SearchWorker(QThread):
    finished = pyqtSignal(dict, dict, dict)
    error = pyqtSignal(str)
    status = pyqtSignal(str)

    def __init__(self, jd_text: str, profile: Profile, skills: dict = None):
        super().__init__()
        self.jd_text = jd_text
        self.profile = profile
        self.skills = skills  # if provided, skip extraction

    def run(self):
        try:
            import core.embeddings as emb
            emb._status_callback = lambda msg: self.status.emit(msg)

            skills_data = load_skills()

            if self.skills is None:
                self.status.emit("Extracting skills from job description...")
                skills = extract_skills(self.jd_text)
            else:
                skills = self.skills

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


class GapFixWorker(QThread):
    finished = pyqtSignal(list)
    error = pyqtSignal(str)

    def __init__(self, gap_analysis: dict, selected_entries: list, skills_data: dict):
        super().__init__()
        self.gap_analysis = gap_analysis
        self.selected_entries = selected_entries
        self.skills_data = skills_data

    def run(self):
        try:
            suggestions = suggest_gap_fixes(self.gap_analysis, self.selected_entries, self.skills_data)
            self.finished.emit(suggestions)
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
    def __init__(self, entry: dict, checked: bool = None):
        super().__init__()
        self.entry = entry
        self.setObjectName("card")
        layout = QHBoxLayout(self)
        layout.setContentsMargins(12, 10, 12, 10)
        layout.setSpacing(12)

        self.checkbox = QCheckBox()
        if checked is None:
            checked = entry.get("ai_pick", False)
        self.checkbox.setChecked(checked)
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


class SuggestionCard(QFrame):
    def __init__(self, suggestion: dict, on_accept, on_reject):
        super().__init__()
        self.suggestion = suggestion
        self.on_accept = on_accept
        self.on_reject = on_reject
        self.setObjectName("card")
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 14, 16, 14)
        layout.setSpacing(8)

        header = QHBoxLayout()
        skill_label = QLabel(self.suggestion["skill"])
        skill_label.setStyleSheet("font-weight: 700; font-size: 13px; color: #1A1A2E;")
        header.addWidget(skill_label)

        verdict = self.suggestion.get("verdict", "genuine_gap")
        if verdict == "phrasing_gap":
            badge = QLabel("Fillable")
            badge.setStyleSheet(
                "background-color: #E8F5E9; color: #2E7D32; border-radius: 4px;"
                "padding: 2px 8px; font-size: 10px; font-weight: 700;"
            )
        else:
            badge = QLabel("Genuine Gap")
            badge.setStyleSheet(
                "background-color: #FCE4EC; color: #C62828; border-radius: 4px;"
                "padding: 2px 8px; font-size: 10px; font-weight: 700;"
            )
        header.addWidget(badge)
        header.addStretch()
        layout.addLayout(header)

        reasoning = QLabel(self.suggestion.get("reasoning", ""))
        reasoning.setWordWrap(True)
        reasoning.setStyleSheet("font-size: 12px; color: #6C757D;")
        layout.addWidget(reasoning)

        if verdict == "phrasing_gap":
            fix_type = self.suggestion.get("fix_type")

            if fix_type == "add_skill" and self.suggestion.get("suggested_skill"):
                fix_label = QLabel(f'Suggested fix: Add "{self.suggestion["suggested_skill"]}" to your Skills')
                fix_label.setWordWrap(True)
                fix_label.setStyleSheet("font-size: 12px; color: #1A1A2E; font-weight: 600;")
                layout.addWidget(fix_label)

            elif fix_type == "reword_bullet" and self.suggestion.get("suggested_bullet"):
                orig = QLabel(f"Original: {self.suggestion.get('original_bullet', '')}")
                orig.setWordWrap(True)
                orig.setStyleSheet("font-size: 11px; color: #6C757D;")
                layout.addWidget(orig)

                suggested = QLabel(f"Suggested: {self.suggestion['suggested_bullet']}")
                suggested.setWordWrap(True)
                suggested.setStyleSheet("font-size: 12px; color: #1A1A2E; font-weight: 600;")
                layout.addWidget(suggested)

            btn_row = QHBoxLayout()
            accept_btn = QPushButton("This is true, apply it")
            accept_btn.setCursor(Qt.CursorShape.PointingHandCursor)
            accept_btn.clicked.connect(self._on_accept_clicked)
            btn_row.addWidget(accept_btn)

            reject_btn = QPushButton("Not applicable")
            reject_btn.setObjectName("secondary")
            reject_btn.setCursor(Qt.CursorShape.PointingHandCursor)
            reject_btn.clicked.connect(self._on_reject_clicked)
            btn_row.addWidget(reject_btn)

            layout.addLayout(btn_row)

    def _on_accept_clicked(self):
        self.on_accept(self.suggestion)

    def _on_reject_clicked(self):
        self.on_reject(self.suggestion)


class AnalyzeJobScreen(QWidget):
    def __init__(self):
        super().__init__()
        self.skills = None
        self.gap_analysis = None
        self.search_results = None
        self.docs = None
        self.jd_text = ""
        self.analysis_id = None
        self.entry_checkboxes = []
        self.search_worker = None
        self.generate_worker = None
        self.gap_fix_worker = None
        self.gap_suggestions_container = None
        self.check_gaps_btn = None
        self._build_ui()

    def _build_ui(self):
        outer = QHBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        # ── Left Panel ──
        left_scroll = QScrollArea()
        left_scroll.setWidgetResizable(True)
        left_scroll.setFrameShape(QFrame.Shape.NoFrame)
        left_scroll.setFixedWidth(420)

        left = QWidget()
        left_layout = QVBoxLayout(left)
        left_layout.setContentsMargins(32, 32, 32, 32)
        left_layout.setSpacing(8)

        self.title = QLabel("Analyze Job")
        self.title.setObjectName("title")
        left_layout.addWidget(self.title)

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
        self.jd_input.setMinimumHeight(200)
        left_layout.addWidget(self.jd_input, stretch=1)

        left_layout.addSpacing(12)

        self.analyse_btn = QPushButton("Analyse →")
        self.analyse_btn.setFixedHeight(44)
        self.analyse_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.analyse_btn.clicked.connect(self._run_search)
        left_layout.addWidget(self.analyse_btn)

        # Re-extract skills — only meaningful after a search has happened
        self.reextract_btn = QPushButton("Re-extract Skills from JD")
        self.reextract_btn.setObjectName("secondary")
        self.reextract_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.reextract_btn.clicked.connect(self._run_reextract)
        self.reextract_btn.hide()
        left_layout.addWidget(self.reextract_btn)

        self.status_label = QLabel("")
        self.status_label.setObjectName("subtitle")
        self.status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.status_label.setWordWrap(True)
        left_layout.addWidget(self.status_label)

        left_layout.addStretch()
        left_scroll.setWidget(left)
        outer.addWidget(left_scroll)

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
        self.reextract_btn.setEnabled(not loading)
        self.status_label.setText(text)

    # ── Fresh analysis ──
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

        self.analyse_btn.setText("Analysing...")
        self._set_loading(True, "Extracting skills...")
        self._clear_results()

        self.search_worker = SearchWorker(self.jd_text, profile, skills=None)
        self.search_worker.finished.connect(self._on_search_done)
        self.search_worker.error.connect(self._on_error)
        self.search_worker.status.connect(self.status_label.setText)
        self.search_worker.start()

    # ── Re-search using existing skills (no extraction call) ──
    def _run_research(self):
        self.jd_text = self.jd_input.toPlainText().strip()
        if not self.jd_text or not self.skills:
            QMessageBox.warning(self, "Cannot Re-search", "Run an analysis first.")
            return

        try:
            profile = Profile.load()
        except Exception as e:
            QMessageBox.critical(self, "Profile Error", str(e))
            return

        self._set_loading(True, "Re-searching your experience...")

        self.search_worker = SearchWorker(self.jd_text, profile, skills=self.skills)
        self.search_worker.finished.connect(self._on_search_done)
        self.search_worker.error.connect(self._on_error)
        self.search_worker.status.connect(self.status_label.setText)
        self.search_worker.start()

    # ── Re-extract skills (costs 1 Gemini call) — then re-search ──
    def _run_reextract(self):
        self.jd_text = self.jd_input.toPlainText().strip()
        if not self.jd_text:
            QMessageBox.warning(self, "Missing Input", "Please paste a job description first.")
            return

        try:
            profile = Profile.load()
        except Exception as e:
            QMessageBox.critical(self, "Profile Error", str(e))
            return

        self._set_loading(True, "Re-extracting skills from job description...")

        self.search_worker = SearchWorker(self.jd_text, profile, skills=None)
        self.search_worker.finished.connect(self._on_search_done)
        self.search_worker.error.connect(self._on_error)
        self.search_worker.status.connect(self.status_label.setText)
        self.search_worker.start()

    def _on_search_done(self, skills: dict, gap_analysis: dict, search_results: dict):
        self.skills = skills
        self.gap_analysis = gap_analysis
        self.search_results = search_results
        self.analyse_btn.setText("Analyse →")
        self._set_loading(False)
        self.reextract_btn.show()
        self._render_results(gap_analysis, search_results, selected_ids=None)

    def _on_error(self, error: str):
        self.analyse_btn.setText("Analyse →")
        self._set_loading(False)
        QMessageBox.critical(self, "Error", f"Something went wrong:\n\n{error}")

    def _clear_results(self):
        self.entry_checkboxes = []
        while self.right_layout.count():
            item = self.right_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

    def _render_results(self, gap_analysis: dict, search_results: dict, selected_ids=None):
        self._clear_results()

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

        # ── Missing Skills + Gap Fix Checker ──
        if gap_analysis["missing_skills"]:
            missing_card = QFrame()
            missing_card.setObjectName("card")
            missing_layout = QVBoxLayout(missing_card)
            missing_layout.setContentsMargins(24, 20, 24, 20)
            missing_layout.setSpacing(8)

            missing_header = QHBoxLayout()
            missing_title = QLabel("Gaps to Address")
            missing_title.setObjectName("section_label")
            missing_header.addWidget(missing_title)
            missing_header.addStretch()

            self.check_gaps_btn = QPushButton("Check for Fillable Gaps")
            self.check_gaps_btn.setObjectName("secondary")
            self.check_gaps_btn.setCursor(Qt.CursorShape.PointingHandCursor)
            self.check_gaps_btn.clicked.connect(self._run_gap_check)
            missing_header.addWidget(self.check_gaps_btn)
            missing_layout.addLayout(missing_header)

            for skill in gap_analysis["missing_skills"]:
                pill = QLabel(f"  {skill}  ")
                pill.setStyleSheet(
                    "background-color: #FCE4EC; color: #C62828; border-radius: 6px;"
                    "padding: 4px 10px; font-size: 12px; font-weight: 600;"
                )
                missing_layout.addWidget(pill, alignment=Qt.AlignmentFlag.AlignLeft)

            self.gap_suggestions_container = QVBoxLayout()
            self.gap_suggestions_container.setSpacing(8)
            missing_layout.addLayout(self.gap_suggestions_container)

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
        selector_header.addStretch()

        research_btn = QPushButton("Re-search")
        research_btn.setObjectName("secondary")
        research_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        research_btn.clicked.connect(self._run_research)
        selector_header.addWidget(research_btn)
        selector_layout.addLayout(selector_header)

        hint = QLabel("AI picks are pre-checked. Check or uncheck to customise.")
        hint.setObjectName("subtitle")
        selector_layout.addWidget(hint)

        self.entry_checkboxes = []
        for entry in search_results["ranked"]:
            checked = None
            if selected_ids is not None:
                checked = entry.get("id") in selected_ids
            cb = EntryCheckbox(entry, checked=checked)
            self.entry_checkboxes.append(cb)
            selector_layout.addWidget(cb)

        self.right_layout.addWidget(selector_card)

        # ── Action Buttons ──
        action_row = QHBoxLayout()
        action_row.setSpacing(8)

        save_btn = QPushButton("Save Progress")
        save_btn.setObjectName("secondary")
        save_btn.setFixedHeight(48)
        save_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        save_btn.clicked.connect(self._save_progress)
        action_row.addWidget(save_btn)

        self.generate_btn = QPushButton("Generate Resume & Cover Letter →")
        self.generate_btn.setFixedHeight(48)
        self.generate_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.generate_btn.clicked.connect(self._run_generate)
        action_row.addWidget(self.generate_btn, stretch=1)

        self.right_layout.addLayout(action_row)

        # ── Generated Docs (if any) ──
        if self.docs and any(self.docs.values()):
            self._render_docs(self.docs)

        self.right_layout.addStretch()

    def _render_docs(self, docs: dict):
        docs_card = QFrame()
        docs_card.setObjectName("card")
        docs_layout = QVBoxLayout(docs_card)
        docs_layout.setContentsMargins(24, 20, 24, 20)
        docs_layout.setSpacing(8)

        docs_title = QLabel("Generated Content")
        docs_title.setObjectName("section_label")
        docs_layout.addWidget(docs_title)

        if docs.get("summary"):
            docs_layout.addWidget(self._label("Summary"))
            summary_box = QTextEdit()
            summary_box.setPlainText(docs["summary"])
            summary_box.setReadOnly(True)
            summary_box.setFixedHeight(80)
            docs_layout.addWidget(summary_box)

        if docs.get("cover_letter"):
            docs_layout.addWidget(self._label("Cover Letter"))
            cl_box = QTextEdit()
            cl_box.setPlainText(docs["cover_letter"])
            cl_box.setReadOnly(True)
            cl_box.setFixedHeight(120)
            docs_layout.addWidget(cl_box)

        regen_row = QHBoxLayout()
        regen_btn = QPushButton("Regenerate with current selection")
        regen_btn.setObjectName("secondary")
        regen_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        regen_btn.clicked.connect(self._run_generate)
        regen_row.addWidget(regen_btn)

        open_folder_btn = QPushButton("Open Output Folder")
        open_folder_btn.setObjectName("secondary")
        open_folder_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        open_folder_btn.clicked.connect(self._open_output_folder)
        regen_row.addWidget(open_folder_btn)

        docs_layout.addLayout(regen_row)

        self.right_layout.addWidget(docs_card)

    def _open_output_folder(self):
        output_dir = os.path.abspath("./output/resumes")
        if os.name == "nt":
            os.startfile(output_dir)
        else:
            os.system(f"xdg-open '{output_dir}'")

    # ── Save progress without generating docs ──
    def _save_progress(self):
        if not self.skills or not self.search_results:
            QMessageBox.warning(self, "Nothing to Save", "Run an analysis first.")
            return

        job_name = self.job_name_input.text().strip() or "Untitled Job"
        selected_ids = [cb.entry.get("id") for cb in self.entry_checkboxes if cb.is_checked()]

        self.analysis_id = save_progress(
            job_name=job_name,
            jd_text=self.jd_text,
            skills=self.skills,
            gap_analysis=self.gap_analysis,
            ranked_entries=self.search_results["ranked"],
            selected_ids=selected_ids,
            analysis_id=self.analysis_id,
        )
        QMessageBox.information(self, "Saved", "Progress saved to History.")

    # ── Generate docs ──
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

        job_name = self.job_name_input.text().strip() or "Untitled Job"
        slug = "_".join(job_name.lower().split())
        slug = "".join(c for c in slug if c.isalnum() or c == "_")

        try:
            resume_path = build_resume(
                profile, docs["summary"], docs["projects"], docs["experience"], f"{slug}_resume.docx",
            )
            cover_path = build_cover_letter(profile, docs["cover_letter"], f"{slug}_cover_letter.docx")
        except Exception as e:
            QMessageBox.critical(self, "Build Error", str(e))
            return

        # Save progress + docs to history
        selected_ids = [cb.entry.get("id") for cb in self.entry_checkboxes if cb.is_checked()]

        self.analysis_id = save_progress(
            job_name=job_name,
            jd_text=self.jd_text,
            skills=self.skills,
            gap_analysis=self.gap_analysis,
            ranked_entries=self.search_results["ranked"],
            selected_ids=selected_ids,
            analysis_id=self.analysis_id,
        )
        save_docs(
            self.analysis_id,
            summary=docs["summary"],
            projects=docs["projects"],
            experience=docs["experience"],
            cover_letter=docs["cover_letter"],
        )

        # Re-render to show the docs section
        self._render_results(self.gap_analysis, self.search_results, selected_ids=selected_ids)

        self._open_output_folder()

        QMessageBox.information(
            self, "Done!",
            f"Files saved to:\n\n{resume_path}\n{cover_path}"
        )

    def _on_generate_error(self, error: str):
        self.generate_btn.setEnabled(True)
        self.generate_btn.setText("Generate Resume & Cover Letter →")
        self.status_label.setText("")
        QMessageBox.critical(self, "Generation Failed", f"Something went wrong:\n\n{error}")

    # ── Gap fix suggestions ──
    def _run_gap_check(self):
        selected = [cb.entry for cb in self.entry_checkboxes if cb.is_checked()]
        if not selected:
            QMessageBox.warning(self, "Nothing Selected", "Select at least one entry first.")
            return

        skills_data = load_skills()
        self.check_gaps_btn.setEnabled(False)
        self.check_gaps_btn.setText("Checking...")
        self.status_label.setText("Analysing fillable gaps...")

        self.gap_fix_worker = GapFixWorker(self.gap_analysis, selected, skills_data)
        self.gap_fix_worker.finished.connect(self._on_gap_check_done)
        self.gap_fix_worker.error.connect(self._on_gap_check_error)
        self.gap_fix_worker.start()

    def _on_gap_check_done(self, suggestions: list):
        self.check_gaps_btn.setEnabled(True)
        self.check_gaps_btn.setText("Check for Fillable Gaps")
        self.status_label.setText("")

        # Clear previous suggestions
        while self.gap_suggestions_container.count():
            item = self.gap_suggestions_container.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        fillable = [s for s in suggestions if s.get("verdict") == "phrasing_gap"]

        if not fillable:
            none_label = QLabel("No fillable gaps found — remaining gaps appear to be genuine.")
            none_label.setObjectName("subtitle")
            none_label.setWordWrap(True)
            self.gap_suggestions_container.addWidget(none_label)
            return

        for suggestion in fillable:
            card = SuggestionCard(
                suggestion=suggestion,
                on_accept=self._accept_suggestion,
                on_reject=self._reject_suggestion,
            )
            self.gap_suggestions_container.addWidget(card)

    def _on_gap_check_error(self, error: str):
        self.check_gaps_btn.setEnabled(True)
        self.check_gaps_btn.setText("Check for Fillable Gaps")
        self.status_label.setText("")
        QMessageBox.critical(self, "Error", f"Could not check gaps:\n\n{error}")

    def _accept_suggestion(self, suggestion: dict):
        fix_type = suggestion.get("fix_type")

        if fix_type == "add_skill" and suggestion.get("suggested_skill"):
            add_skill("General", suggestion["suggested_skill"])
            QMessageBox.information(
                self, "Added",
                f'Added "{suggestion["suggested_skill"]}" to your Skills under \'General\'. '
                "You can move it to a better category in the Skills tab."
            )
        elif fix_type == "reword_bullet":
            target = suggestion.get("target_entry")
            original = suggestion.get("original_bullet")
            new_bullet = suggestion.get("suggested_bullet")
            if target and original and new_bullet:
                success = update_bullet(target, original, new_bullet)
                if success:
                    QMessageBox.information(self, "Updated", f"Bullet updated in '{target}'.")
                else:
                    QMessageBox.warning(self, "Not Found", "Could not locate that bullet to update.")

        QMessageBox.information(self, "Tip", "Re-run analysis to see the updated match score.")

    def _reject_suggestion(self, suggestion: dict):
        pass  # no-op, suggestion just stays dismissed visually until next render

    # ── Load a saved record from History ──
    def load_record(self, record: dict):
        self.analysis_id = record["id"]
        self.jd_text = record["jd_text"]
        self.skills = record["skills"]
        self.gap_analysis = record["gap_analysis"]
        self.search_results = {"ranked": record["ranked_entries"]}

        if record.get("status") == "docs_done":
            self.docs = {
                "summary": record.get("summary", ""),
                "projects": record.get("projects", ""),
                "experience": record.get("experience", ""),
                "cover_letter": record.get("cover_letter", ""),
            }
        else:
            self.docs = None

        self.job_name_input.setText(record["job_name"])
        self.jd_input.setPlainText(record["jd_text"])

        self.reextract_btn.show()
        self._render_results(
            self.gap_analysis,
            self.search_results,
            selected_ids=record.get("selected_ids", []),
        )