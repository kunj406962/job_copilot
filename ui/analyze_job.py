from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QTextEdit, QScrollArea, QFrame, QProgressBar, QMessageBox
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal
from PyQt6.QtGui import QFont
from core.generator import run_analysis
from core.docx_builder import build_resume, build_cover_letter
from core.profile import Profile
import os


class AnalysisWorker(QThread):
    finished = pyqtSignal(dict)
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
            result = run_analysis(self.jd_text, self.profile)
            emb._status_callback = None
            self.finished.emit(result)
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
        if status == "strong":
            bar.setStyleSheet("QProgressBar::chunk { background-color: #2E7D32; border-radius: 4px; } QProgressBar { background-color: #DEE2E6; border-radius: 4px; border: none; }")
        elif status == "partial":
            bar.setStyleSheet("QProgressBar::chunk { background-color: #F57F17; border-radius: 4px; } QProgressBar { background-color: #DEE2E6; border-radius: 4px; border: none; }")
        else:
            bar.setStyleSheet("QProgressBar::chunk { background-color: #E63946; border-radius: 4px; } QProgressBar { background-color: #DEE2E6; border-radius: 4px; border: none; }")
        layout.addWidget(bar, stretch=1)

        pct = QLabel(f"{confidence}%")
        pct.setFixedWidth(40)
        pct.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        pct.setStyleSheet("font-size: 12px; color: #6C757D;")
        layout.addWidget(pct)


class AnalyzeJobScreen(QWidget):
    def __init__(self):
        super().__init__()
        self.result = None
        self.worker = None
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

        left_layout.addWidget(self._label("Job Description"))
        self.jd_input = QTextEdit()
        self.jd_input.setPlaceholderText("Paste the full job description here...")
        left_layout.addWidget(self.jd_input, stretch=1)

        left_layout.addSpacing(12)

        self.analyze_btn = QPushButton("Analyse →")
        self.analyze_btn.setFixedHeight(44)
        self.analyze_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.analyze_btn.clicked.connect(self._run_analysis)
        left_layout.addWidget(self.analyze_btn)

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

        right = QWidget()
        self.right_layout = QVBoxLayout(right)
        self.right_layout.setContentsMargins(32, 32, 32, 32)
        self.right_layout.setSpacing(16)

        self.placeholder = QLabel("Run an analysis to see your results here.")
        self.placeholder.setObjectName("subtitle")
        self.placeholder.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.right_layout.addWidget(self.placeholder)
        self.right_layout.addStretch()

        right_scroll.setWidget(right)
        outer.addWidget(right_scroll, stretch=1)

    def _label(self, text: str) -> QLabel:
        label = QLabel(text)
        label.setStyleSheet("font-weight: 600; color: #1A1A2E;")
        return label

    def _run_analysis(self):
        jd_text = self.jd_input.toPlainText().strip()
        if not jd_text:
            QMessageBox.warning(self, "Missing Input", "Please paste a job description first.")
            return

        try:
            profile = Profile.load()
        except Exception as e:
            QMessageBox.critical(self, "Profile Error", str(e))
            return

        self.analyze_btn.setEnabled(False)
        self.analyze_btn.setText("Analysing...")
        self.status_label.setText("Extracting skills from job description...")
        self._clear_results()

        self.worker = AnalysisWorker(jd_text, profile)
        self.worker.finished.connect(self._on_analysis_done)
        self.worker.error.connect(self._on_analysis_error)
        self.worker.status.connect(self._on_status_update)
        self.worker.start()

    def _on_status_update(self, msg: str):
        self.status_label.setText(msg)

    def _on_analysis_done(self, result: dict):
        self.result = result
        self.analyze_btn.setEnabled(True)
        self.analyze_btn.setText("Analyse →")
        self.status_label.setText("")
        self._render_results(result)

    def _on_analysis_error(self, error: str):
        self.analyze_btn.setEnabled(True)
        self.analyze_btn.setText("Analyse →")
        self.status_label.setText("")
        QMessageBox.critical(self, "Analysis Failed", f"Something went wrong:\n\n{error}")

    def _clear_results(self):
        while self.right_layout.count():
            item = self.right_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

    def _render_results(self, result: dict):
        gap = result["gap_analysis"]

        # ── Overall Score ──
        score_card = QFrame()
        score_card.setObjectName("card")
        score_layout = QVBoxLayout(score_card)
        score_layout.setContentsMargins(24, 20, 24, 20)
        score_layout.setSpacing(4)

        score_title = QLabel("Overall Match")
        score_title.setObjectName("section_label")
        score_layout.addWidget(score_title)

        score = gap["overall_match"]
        score_label = QLabel(f"{score}%")
        score_label.setStyleSheet(
            f"font-size: 48px; font-weight: 700; color: "
            f"{'#2E7D32' if score >= 70 else '#F57F17' if score >= 40 else '#E63946'};"
        )
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

        for skill_data in gap["skills"]:
            row = SkillRow(
                skill=skill_data["skill"],
                status=skill_data["status"],
                confidence=skill_data["confidence"],
                skill_type=skill_data["type"],
            )
            skills_layout.addWidget(row)

        self.right_layout.addWidget(skills_card)

        # ── Missing Skills ──
        if gap["missing_skills"]:
            missing_card = QFrame()
            missing_card.setObjectName("card")
            missing_layout = QVBoxLayout(missing_card)
            missing_layout.setContentsMargins(24, 20, 24, 20)
            missing_layout.setSpacing(8)

            missing_title = QLabel("Gaps to Address")
            missing_title.setObjectName("section_label")
            missing_layout.addWidget(missing_title)

            for skill in gap["missing_skills"]:
                pill = QLabel(f"  {skill}  ")
                pill.setStyleSheet(
                    "background-color: #FCE4EC; color: #C62828; border-radius: 6px;"
                    "padding: 4px 10px; font-size: 12px; font-weight: 600;"
                )
                pill.setFixedHeight(28)
                missing_layout.addWidget(pill, alignment=Qt.AlignmentFlag.AlignLeft)

            self.right_layout.addWidget(missing_card)

        # ── Generate Button ──
        generate_btn = QPushButton("Generate Resume & Cover Letter →")
        generate_btn.setFixedHeight(48)
        generate_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        generate_btn.clicked.connect(self._generate_docs)
        self.right_layout.addWidget(generate_btn)

        self.right_layout.addStretch()

    def _generate_docs(self):
        if not self.result:
            return

        try:
            profile = Profile.load()
        except Exception as e:
            QMessageBox.critical(self, "Profile Error", str(e))
            return

        try:
            resume_path = build_resume(
                profile,
                self.result["summary"],
                self.result["projects"],
                self.result["experience"],
                "resume.docx",
            )
            cover_path = build_cover_letter(
                profile,
                self.result["cover_letter"],
                "cover_letter.docx",
            )
        except Exception as e:
            QMessageBox.critical(self, "Generation Failed", str(e))
            return

        output_dir = os.path.abspath("./output/resumes")
        if os.name == "nt":
            os.startfile(output_dir)
        else:
            os.system(f"xdg-open '{output_dir}'")

        QMessageBox.information(
            self, "Done!",
            f"Files saved to:\n\n{resume_path}\n{cover_path}"
        )
