from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QTextEdit, QScrollArea, QFrame, QProgressBar, QMessageBox,
    QCheckBox, QLineEdit
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal
from PyQt6.QtGui import QPalette, QColor
from core.generator import (
    extract_skills, analyze_gaps, search_entries,
    generate_documents, suggest_gap_fixes,
)
from core.docx_builder import build_resume, build_cover_letter
from core.history import save_progress, save_docs, save_suggestions
from core.profile import Profile
from core.skills import load_skills, add_skill, add_category
import os


class SearchWorker(QThread):
    finished = pyqtSignal(dict, dict, dict)
    error = pyqtSignal(str)
    status = pyqtSignal(str)

    def __init__(self, jd_text, profile, skills=None):
        super().__init__()
        self.jd_text = jd_text
        self.profile = profile
        self.skills = skills

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

    def __init__(self, jd_text, profile, selected_entries, accepted_rewrites):
        super().__init__()
        self.jd_text = jd_text
        self.profile = profile
        self.selected_entries = selected_entries
        self.accepted_rewrites = accepted_rewrites

    def run(self):
        try:
            import core.embeddings as emb
            emb._status_callback = lambda msg: self.status.emit(msg)
            skills_data = load_skills()
            self.status.emit("Generating resume content...")
            docs = generate_documents(
                self.jd_text, self.profile,
                self.selected_entries, skills_data,
                accepted_rewrites=self.accepted_rewrites,
            )
            emb._status_callback = None
            self.finished.emit(docs)
        except Exception as e:
            self.error.emit(str(e))


class GapFixWorker(QThread):
    finished = pyqtSignal(list)
    error = pyqtSignal(str)

    def __init__(self, gap_analysis, selected_entries, skills_data):
        super().__init__()
        self.gap_analysis = gap_analysis
        self.selected_entries = selected_entries
        self.skills_data = skills_data

    def run(self):
        try:
            suggestions = suggest_gap_fixes(
                self.gap_analysis, self.selected_entries, self.skills_data
            )
            self.finished.emit(suggestions)
        except Exception as e:
            self.error.emit(str(e))


class SkillRow(QWidget):
    def __init__(self, skill, status, confidence, skill_type):
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
    def __init__(self, entry, checked=None):
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

        colors = {
            "project":   "background-color: #EEF1FD; color: #4361EE;",
            "job":       "background-color: #E8F5E9; color: #2E7D32;",
            "softskill": "background-color: #FCE4EC; color: #C62828;",
        }
        type_badge = QLabel(entry["type"].upper())
        type_badge.setStyleSheet(
            f"{colors.get(entry['type'], '')} border-radius: 4px;"
            "padding: 2px 6px; font-size: 10px; font-weight: 700;"
        )
        info.addWidget(type_badge)
        layout.addLayout(info, stretch=1)

    def is_checked(self):
        return self.checkbox.isChecked()


class SuggestionCard(QWidget):
    STATUS_COLORS = {
        "pending":  "#4361EE",
        "accepted": "#2E7D32",
        "declined": "#E63946",
    }
    STATUS_BG = {
        "pending":  "#F0F3FF",
        "accepted": "#F0FAF0",
        "declined": "#FFF0F0",
    }

    def __init__(self, suggestion, on_accept, on_decline, on_status_change):
        super().__init__()
        self.suggestion = suggestion
        self.on_accept = on_accept
        self.on_decline = on_decline
        self.on_status_change = on_status_change
        self._build_ui()

    def _build_ui(self):
        status = self.suggestion.get("status", "pending")
        border_color = self.STATUS_COLORS.get(status, "#4361EE")
        bg_color = self.STATUS_BG.get(status, "#F0F3FF")

        outer = QHBoxLayout(self)
        outer.setContentsMargins(0, 4, 0, 4)
        outer.setSpacing(0)

        # Colored left strip
        strip = QFrame()
        strip.setFixedWidth(5)
        strip.setStyleSheet(f"QFrame {{ background-color: {border_color}; border: none; }}")
        outer.addWidget(strip)

        # Card body
        body = QWidget()
        body.setStyleSheet(f"QWidget {{ background-color: {bg_color}; border: none; }}")
        body_layout = QVBoxLayout(body)
        body_layout.setContentsMargins(14, 12, 14, 12)
        body_layout.setSpacing(8)

        # Header
        header = QHBoxLayout()

        skill_label = QLabel(self.suggestion["skill"])
        skill_label.setStyleSheet(
            "font-weight: 700; font-size: 13px; color: #1A1A2E;"
            "background: transparent; border: none;"
        )
        header.addWidget(skill_label)

        verdict = self.suggestion.get("verdict", "genuine_gap")
        verdict_badge = QLabel("Fillable" if verdict == "phrasing_gap" else "Genuine Gap")
        verdict_color = "#1A5C1A" if verdict == "phrasing_gap" else "#8B0000"
        verdict_bg = "#C8EFC8" if verdict == "phrasing_gap" else "#FCCACA"
        verdict_badge.setStyleSheet(
            f"background-color: {verdict_bg}; color: {verdict_color}; border-radius: 4px;"
            "padding: 2px 8px; font-size: 10px; font-weight: 700; border: none;"
        )
        header.addWidget(verdict_badge)

        status_lbl = QLabel(status.capitalize())
        status_lbl.setStyleSheet(
            f"color: {border_color}; font-size: 10px; font-weight: 700;"
            "padding: 2px 6px; background: transparent; border: none;"
        )
        header.addWidget(status_lbl)
        header.addStretch()
        body_layout.addLayout(header)

        # Reasoning
        reasoning = QLabel(self.suggestion.get("reasoning", ""))
        reasoning.setWordWrap(True)
        reasoning.setStyleSheet(
            "font-size: 12px; color: #444; background: transparent; border: none;"
        )
        body_layout.addWidget(reasoning)

        if verdict == "phrasing_gap":
            fix_type = self.suggestion.get("fix_type")

            if fix_type == "add_skill" and self.suggestion.get("suggested_skill"):
                cat = self.suggestion.get("suggested_category") or "General"
                fix_lbl = QLabel(
                    f'Add "{self.suggestion["suggested_skill"]}" → category "{cat}"'
                )
                fix_lbl.setWordWrap(True)
                fix_lbl.setStyleSheet(
                    "font-size: 12px; color: #1A1A2E; font-weight: 600;"
                    "background-color: #FFFFFF; border-radius: 4px;"
                    "padding: 6px; border: 1px solid #DEE2E6;"
                )
                body_layout.addWidget(fix_lbl)

            elif fix_type == "reword_bullet" and self.suggestion.get("suggested_bullet"):
                orig_lbl = QLabel(f"Before: {self.suggestion.get('original_bullet', '')}")
                orig_lbl.setWordWrap(True)
                orig_lbl.setStyleSheet(
                    "font-size: 11px; color: #666; background-color: #FFF5F5;"
                    "border-radius: 4px; padding: 6px; border: 1px solid #FFCCCC;"
                )
                body_layout.addWidget(orig_lbl)

                sug_lbl = QLabel(f"After: {self.suggestion['suggested_bullet']}")
                sug_lbl.setWordWrap(True)
                sug_lbl.setStyleSheet(
                    "font-size: 12px; color: #1A1A2E; font-weight: 600;"
                    "background-color: #F0FAF0; border-radius: 4px;"
                    "padding: 6px; border: 1px solid #AADDAA;"
                )
                body_layout.addWidget(sug_lbl)

            note = QLabel(
                "Accepting a reword applies only to this job's resume — "
                "your stored experience is unchanged."
            )
            note.setWordWrap(True)
            note.setStyleSheet(
                "font-size: 10px; color: #888; font-style: italic;"
                "background: transparent; border: none;"
            )
            body_layout.addWidget(note)

            if status == "pending":
                btn_row = QHBoxLayout()

                accept_btn = QPushButton("This is true, apply it")
                accept_btn.setCursor(Qt.CursorShape.PointingHandCursor)
                accept_btn.setStyleSheet(
                    "QPushButton { background-color: #4361EE; color: #FFFFFF; border: none;"
                    "border-radius: 8px; padding: 8px 18px; font-size: 13px;"
                    "font-weight: 600; min-height: 36px; }"
                    "QPushButton:hover { background-color: #3A56D4; }"
                )
                accept_btn.clicked.connect(self._on_accept_clicked)
                btn_row.addWidget(accept_btn)

                decline_btn = QPushButton("Not applicable")
                decline_btn.setCursor(Qt.CursorShape.PointingHandCursor)
                decline_btn.setStyleSheet(
                    "QPushButton { background-color: #FFFFFF; color: #4361EE;"
                    "border: 1.5px solid #4361EE; border-radius: 8px; padding: 8px 18px;"
                    "font-size: 13px; font-weight: 600; min-height: 36px; }"
                    "QPushButton:hover { background-color: #EEF1FD; }"
                )
                decline_btn.clicked.connect(self._on_decline_clicked)
                btn_row.addWidget(decline_btn)

                body_layout.addLayout(btn_row)
            else:
                undo_btn = QPushButton("Undo")
                undo_btn.setCursor(Qt.CursorShape.PointingHandCursor)
                undo_btn.setStyleSheet(
                    "QPushButton { background-color: #FFFFFF; color: #4361EE;"
                    "border: 1.5px solid #4361EE; border-radius: 8px; padding: 6px 16px;"
                    "font-size: 12px; font-weight: 600; min-height: 32px; }"
                    "QPushButton:hover { background-color: #EEF1FD; }"
                )
                undo_btn.clicked.connect(self._on_undo_clicked)
                body_layout.addWidget(undo_btn, alignment=Qt.AlignmentFlag.AlignLeft)

        outer.addWidget(body, stretch=1)

    def _on_accept_clicked(self):
        self.suggestion["status"] = "accepted"
        self.on_accept(self.suggestion)
        self.on_status_change()

    def _on_decline_clicked(self):
        self.suggestion["status"] = "declined"
        self.on_decline(self.suggestion)
        self.on_status_change()

    def _on_undo_clicked(self):
        self.suggestion["status"] = "pending"
        self.on_status_change()
    def _on_accept_clicked(self):
        self.suggestion["status"] = "accepted"
        self.on_accept(self.suggestion)
        self.on_status_change()

    def _on_decline_clicked(self):
        self.suggestion["status"] = "declined"
        self.on_decline(self.suggestion)
        self.on_status_change()

    def _on_undo_clicked(self):
        self.suggestion["status"] = "pending"
        self.on_status_change()


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
        self.gap_suggestions = []
        self.accepted_rewrites = {}
        self.search_worker = None
        self.generate_worker = None
        self.gap_fix_worker = None
        self.gap_suggestions_container = None
        self.check_gaps_btn = None
        # Live score display references for update-in-place
        self._score_label_ref = None
        self._score_bar_ref = None
        self._build_ui()

    def _build_ui(self):
        outer = QHBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        left_scroll = QScrollArea()
        left_scroll.setWidgetResizable(True)
        left_scroll.setFrameShape(QFrame.Shape.NoFrame)
        left_scroll.setFixedWidth(420)

        left = QWidget()
        left_layout = QVBoxLayout(left)
        left_layout.setContentsMargins(32, 32, 32, 32)
        left_layout.setSpacing(8)

        self.title_label = QLabel("Analyze Job")
        self.title_label.setObjectName("title")
        left_layout.addWidget(self.title_label)

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

        divider = QFrame()
        divider.setFrameShape(QFrame.Shape.VLine)
        divider.setStyleSheet("color: #DEE2E6;")
        outer.addWidget(divider)

        right_scroll = QScrollArea()
        right_scroll.setWidgetResizable(True)
        right_scroll.setFrameShape(QFrame.Shape.NoFrame)

        self.right = QWidget()
        self.right_layout = QVBoxLayout(self.right)
        self.right_layout.setContentsMargins(32, 32, 32, 32)
        self.right_layout.setSpacing(16)

        placeholder = QLabel("Run an analysis to see your results here.")
        placeholder.setObjectName("subtitle")
        placeholder.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.right_layout.addWidget(placeholder)
        self.right_layout.addStretch()

        right_scroll.setWidget(self.right)
        outer.addWidget(right_scroll, stretch=1)

    def _label(self, text):
        lbl = QLabel(text)
        lbl.setStyleSheet("font-weight: 600; color: #1A1A2E;")
        return lbl

    def _set_loading(self, loading, text=""):
        self.analyse_btn.setEnabled(not loading)
        self.reextract_btn.setEnabled(not loading)
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
        self.gap_suggestions = []
        self.accepted_rewrites = {}
        self.analyse_btn.setText("Analysing...")
        self._set_loading(True, "Extracting skills...")
        self._clear_results()
        self.search_worker = SearchWorker(self.jd_text, profile, skills=None)
        self.search_worker.finished.connect(self._on_search_done)
        self.search_worker.error.connect(self._on_error)
        self.search_worker.status.connect(self.status_label.setText)
        self.search_worker.start()

    def _run_research(self):
        self.jd_text = self.jd_input.toPlainText().strip()
        if not self.jd_text or not self.skills:
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

    def _run_reextract(self):
        self.jd_text = self.jd_input.toPlainText().strip()
        if not self.jd_text:
            return
        try:
            profile = Profile.load()
        except Exception as e:
            QMessageBox.critical(self, "Profile Error", str(e))
            return
        self.gap_suggestions = []
        self.accepted_rewrites = {}
        self._set_loading(True, "Re-extracting skills...")
        self.search_worker = SearchWorker(self.jd_text, profile, skills=None)
        self.search_worker.finished.connect(self._on_search_done)
        self.search_worker.error.connect(self._on_error)
        self.search_worker.status.connect(self.status_label.setText)
        self.search_worker.start()

    def _on_search_done(self, skills, gap_analysis, search_results):
        self.skills = skills
        self.gap_analysis = gap_analysis
        self.search_results = search_results
        self.analyse_btn.setText("Analyse →")
        self._set_loading(False)
        self.reextract_btn.show()
        self._render_results(gap_analysis, search_results, selected_ids=None)

    def _on_error(self, error):
        self.analyse_btn.setText("Analyse →")
        self._set_loading(False)
        QMessageBox.critical(self, "Error", f"Something went wrong:\n\n{error}")

    def _clear_results(self):
        self.entry_checkboxes = []
        self.gap_suggestions_container = None
        self.check_gaps_btn = None
        self._score_label_ref = None
        self._score_bar_ref = None
        while self.right_layout.count():
            item = self.right_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

    def _render_results(self, gap_analysis, search_results, selected_ids=None):
        self._clear_results()

        # ── Overall Score ──
        score_card = QFrame()
        score_card.setObjectName("card")
        sc_l = QVBoxLayout(score_card)
        sc_l.setContentsMargins(24, 20, 24, 20)
        sc_l.setSpacing(4)

        sc_title = QLabel("Overall Match")
        sc_title.setObjectName("section_label")
        sc_l.addWidget(sc_title)

        score = gap_analysis["overall_match"]
        color = "#2E7D32" if score >= 70 else "#F57F17" if score >= 40 else "#E63946"
        self._score_label_ref = QLabel(f"{score}%")
        self._score_label_ref.setStyleSheet(
            f"font-size: 48px; font-weight: 700; color: {color};"
        )
        sc_l.addWidget(self._score_label_ref)

        self._score_bar_ref = QProgressBar()
        self._score_bar_ref.setValue(score)
        self._score_bar_ref.setFixedHeight(10)
        self._score_bar_ref.setTextVisible(False)
        sc_l.addWidget(self._score_bar_ref)
        self.right_layout.addWidget(score_card)

        # ── Skill Breakdown ──
        sk_card = QFrame()
        sk_card.setObjectName("card")
        sk_l = QVBoxLayout(sk_card)
        sk_l.setContentsMargins(24, 20, 24, 20)
        sk_l.setSpacing(4)
        sk_title = QLabel("Skill Breakdown")
        sk_title.setObjectName("section_label")
        sk_l.addWidget(sk_title)
        sk_l.addSpacing(8)
        for sd in gap_analysis["skills"]:
            sk_l.addWidget(
                SkillRow(sd["skill"], sd["status"], sd["confidence"], sd["type"])
            )
        self.right_layout.addWidget(sk_card)

        # ── Missing Skills + gap checker ──
        if gap_analysis["missing_skills"]:
            miss_card = QFrame()
            miss_card.setObjectName("card")
            miss_l = QVBoxLayout(miss_card)
            miss_l.setContentsMargins(24, 20, 24, 20)
            miss_l.setSpacing(8)

            miss_header = QHBoxLayout()
            miss_title = QLabel("Gaps to Address")
            miss_title.setObjectName("section_label")
            miss_header.addWidget(miss_title)
            miss_header.addStretch()

            self.check_gaps_btn = QPushButton("Check for Fillable Gaps")
            self.check_gaps_btn.setObjectName("secondary")
            self.check_gaps_btn.setCursor(Qt.CursorShape.PointingHandCursor)
            self.check_gaps_btn.clicked.connect(self._run_gap_check)
            miss_header.addWidget(self.check_gaps_btn)
            miss_l.addLayout(miss_header)

            for skill in gap_analysis["missing_skills"]:
                pill = QLabel(f"  {skill}  ")
                pill.setStyleSheet(
                    "background-color: #FCE4EC; color: #C62828; border-radius: 6px;"
                    "padding: 4px 10px; font-size: 12px; font-weight: 600;"
                )
                miss_l.addWidget(pill, alignment=Qt.AlignmentFlag.AlignLeft)

            self.gap_suggestions_container = QVBoxLayout()
            self.gap_suggestions_container.setSpacing(8)
            miss_l.addLayout(self.gap_suggestions_container)

            # Restore saved suggestions immediately after container is set
            if self.gap_suggestions:
                self._render_suggestion_cards()

            self.right_layout.addWidget(miss_card)

        # ── Entry Selector ──
        sel_card = QFrame()
        sel_card.setObjectName("card")
        sel_l = QVBoxLayout(sel_card)
        sel_l.setContentsMargins(24, 20, 24, 20)
        sel_l.setSpacing(8)

        sel_header = QHBoxLayout()
        sel_title = QLabel("Select Experience to Include")
        sel_title.setObjectName("section_label")
        sel_header.addWidget(sel_title)
        sel_header.addStretch()

        research_btn = QPushButton("Re-search")
        research_btn.setObjectName("secondary")
        research_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        research_btn.clicked.connect(self._run_research)
        sel_header.addWidget(research_btn)
        sel_l.addLayout(sel_header)

        hint = QLabel("AI picks are pre-checked. Check or uncheck to customise.")
        hint.setObjectName("subtitle")
        sel_l.addWidget(hint)

        self.entry_checkboxes = []
        for entry in search_results["ranked"]:
            checked = None
            if selected_ids is not None:
                checked = entry.get("id") in selected_ids
            cb = EntryCheckbox(entry, checked=checked)
            self.entry_checkboxes.append(cb)
            sel_l.addWidget(cb)

        self.right_layout.addWidget(sel_card)

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

        if self.docs and any(self.docs.values()):
            self._render_docs(self.docs)

        self.right_layout.addStretch()

    def _render_docs(self, docs):
        docs_card = QFrame()
        docs_card.setObjectName("card")
        dl = QVBoxLayout(docs_card)
        dl.setContentsMargins(24, 20, 24, 20)
        dl.setSpacing(8)

        docs_title = QLabel("Generated Content")
        docs_title.setObjectName("section_label")
        dl.addWidget(docs_title)

        if docs.get("summary"):
            dl.addWidget(self._label("Summary"))
            sb = QTextEdit()
            sb.setPlainText(docs["summary"])
            sb.setReadOnly(True)
            sb.setFixedHeight(80)
            dl.addWidget(sb)

        if docs.get("cover_letter"):
            dl.addWidget(self._label("Cover Letter"))
            cb = QTextEdit()
            cb.setPlainText(docs["cover_letter"])
            cb.setReadOnly(True)
            cb.setFixedHeight(120)
            dl.addWidget(cb)

        regen_row = QHBoxLayout()
        regen_btn = QPushButton("Regenerate with current selection")
        regen_btn.setObjectName("secondary")
        regen_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        regen_btn.clicked.connect(self._run_generate)
        regen_row.addWidget(regen_btn)

        folder_btn = QPushButton("Open Output Folder")
        folder_btn.setObjectName("secondary")
        folder_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        folder_btn.clicked.connect(self._open_output_folder)
        regen_row.addWidget(folder_btn)

        dl.addLayout(regen_row)
        self.right_layout.addWidget(docs_card)

    def _open_output_folder(self):
        output_dir = os.path.abspath("./output/resumes")
        if os.name == "nt":
            os.startfile(output_dir)
        else:
            os.system(f"xdg-open '{output_dir}'")

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
            gap_suggestions=self.gap_suggestions,
        )
        QMessageBox.information(self, "Saved", "Progress saved to History.")

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
        self.generate_worker = GenerateWorker(
            self.jd_text, profile, selected, self.accepted_rewrites
        )
        self.generate_worker.finished.connect(self._on_generate_done)
        self.generate_worker.error.connect(self._on_generate_error)
        self.generate_worker.status.connect(self.status_label.setText)
        self.generate_worker.start()

    def _on_generate_done(self, docs):
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
                profile, docs["summary"], docs["projects"],
                docs["experience"], f"{slug}_resume.docx",
            )
            cover_path = build_cover_letter(
                profile, docs["cover_letter"], f"{slug}_cover_letter.docx"
            )
        except Exception as e:
            QMessageBox.critical(self, "Build Error", str(e))
            return

        selected_ids = [cb.entry.get("id") for cb in self.entry_checkboxes if cb.is_checked()]
        self.analysis_id = save_progress(
            job_name=job_name,
            jd_text=self.jd_text,
            skills=self.skills,
            gap_analysis=self.gap_analysis,
            ranked_entries=self.search_results["ranked"],
            selected_ids=selected_ids,
            analysis_id=self.analysis_id,
            gap_suggestions=self.gap_suggestions,
        )
        save_docs(
            self.analysis_id,
            summary=docs["summary"],
            projects=docs["projects"],
            experience=docs["experience"],
            cover_letter=docs["cover_letter"],
        )

        self._render_results(self.gap_analysis, self.search_results, selected_ids=selected_ids)
        self._open_output_folder()
        QMessageBox.information(self, "Done!", f"Files saved to:\n\n{resume_path}\n{cover_path}")

    def _on_generate_error(self, error):
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
        self.check_gaps_btn.setEnabled(False)
        self.check_gaps_btn.setText("Checking...")
        self.status_label.setText("Analysing fillable gaps...")
        self.gap_fix_worker = GapFixWorker(self.gap_analysis, selected, load_skills())
        self.gap_fix_worker.finished.connect(self._on_gap_check_done)
        self.gap_fix_worker.error.connect(self._on_gap_check_error)
        self.gap_fix_worker.start()

    def _on_gap_check_done(self, suggestions):
        self.check_gaps_btn.setEnabled(True)
        self.check_gaps_btn.setText("Check for Fillable Gaps")
        self.status_label.setText("")
        self.gap_suggestions = suggestions
        if self.analysis_id:
            save_suggestions(self.analysis_id, self.gap_suggestions)
        self._render_suggestion_cards()

    def _on_gap_check_error(self, error):
        self.check_gaps_btn.setEnabled(True)
        self.check_gaps_btn.setText("Check for Fillable Gaps")
        self.status_label.setText("")
        QMessageBox.critical(self, "Error", f"Could not check gaps:\n\n{error}")

    def _render_suggestion_cards(self):
        if self.gap_suggestions_container is None:
            return
        while self.gap_suggestions_container.count():
            item = self.gap_suggestions_container.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        fillable = [s for s in self.gap_suggestions if s.get("verdict") == "phrasing_gap"]

        if not fillable:
            lbl = QLabel("No fillable gaps found — remaining gaps appear to be genuine.")
            lbl.setObjectName("subtitle")
            lbl.setWordWrap(True)
            self.gap_suggestions_container.addWidget(lbl)
            return

        for suggestion in fillable:
            card = SuggestionCard(
                suggestion=suggestion,
                on_accept=self._accept_suggestion,
                on_decline=self._decline_suggestion,
                on_status_change=self._on_suggestion_status_changed,
            )
            self.gap_suggestions_container.addWidget(card)

    def _on_suggestion_status_changed(self):
        """Re-render cards and persist. Also update score if a skill was added."""
        self._render_suggestion_cards()
        if self.analysis_id:
            save_suggestions(self.analysis_id, self.gap_suggestions)
        self._refresh_score()

    def _refresh_score(self):
        """
        Recompute gap analysis against current skills.json (no API call)
        and update the score label + bar in place.
        """
        if not self.skills or self._score_label_ref is None:
            return

        skills_data = load_skills()
        updated_gap = analyze_gaps(self.skills, skills_data)
        self.gap_analysis = updated_gap

        score = updated_gap["overall_match"]
        color = "#2E7D32" if score >= 70 else "#F57F17" if score >= 40 else "#E63946"
        self._score_label_ref.setText(f"{score}%")
        self._score_label_ref.setStyleSheet(
            f"font-size: 48px; font-weight: 700; color: {color};"
        )
        self._score_bar_ref.setValue(score)

    def _accept_suggestion(self, suggestion):
        fix_type = suggestion.get("fix_type")
        if fix_type == "add_skill" and suggestion.get("suggested_skill"):
            skill_name = suggestion["suggested_skill"]
            category = suggestion.get("suggested_category") or "General"
            skills_data = load_skills()
            if category not in skills_data:
                add_category(category)
            add_skill(category, skill_name)
        elif fix_type == "reword_bullet":
            original = suggestion.get("original_bullet")
            reworded = suggestion.get("suggested_bullet")
            if original and reworded:
                self.accepted_rewrites[original] = reworded

    def _decline_suggestion(self, suggestion):
        pass

    def load_record(self, record):
        self.analysis_id = record["id"]
        self.jd_text = record["jd_text"]
        self.skills = record["skills"]
        self.gap_analysis = record["gap_analysis"]
        self.search_results = {"ranked": record["ranked_entries"]}
        self.gap_suggestions = record.get("gap_suggestions", [])

        self.accepted_rewrites = {
            s["original_bullet"]: s["suggested_bullet"]
            for s in self.gap_suggestions
            if s.get("status") == "accepted"
            and s.get("fix_type") == "reword_bullet"
            and s.get("original_bullet")
            and s.get("suggested_bullet")
        }

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