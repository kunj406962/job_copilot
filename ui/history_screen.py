from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QScrollArea, QFrame, QMessageBox, QTextEdit, QDialog,
    QDialogButtonBox
)
from PyQt6.QtCore import Qt
from core.history import load_all, delete_analysis


class HistoryDetailDialog(QDialog):
    def __init__(self, record: dict, parent=None):
        super().__init__(parent)
        self.setWindowTitle(record["job_name"])
        self.setMinimumSize(700, 600)
        layout = QVBoxLayout(self)
        layout.setSpacing(12)
        layout.setContentsMargins(24, 24, 24, 24)

        # Header
        title = QLabel(record["job_name"])
        title.setObjectName("title")
        layout.addWidget(title)

        date = QLabel(record["date"])
        date.setObjectName("subtitle")
        layout.addWidget(date)

        score = record.get("gap_analysis", {}).get("overall_match", 0)
        score_label = QLabel(f"Match Score: {score}%")
        color = "#2E7D32" if score >= 70 else "#F57F17" if score >= 40 else "#E63946"
        score_label.setStyleSheet(f"font-size: 16px; font-weight: 700; color: {color};")
        layout.addWidget(score_label)

        # Selected entries
        entries = record.get("selected_entries", [])
        if entries:
            entries_label = QLabel("Experience Used:")
            entries_label.setStyleSheet("font-weight: 700; color: #1A1A2E;")
            layout.addWidget(entries_label)
            for e in entries:
                pill = QLabel(f"  {e['name']}  ")
                pill.setStyleSheet(
                    "background-color: #EEF1FD; color: #4361EE; border-radius: 6px;"
                    "padding: 4px 10px; font-size: 12px; font-weight: 600;"
                )
                layout.addWidget(pill, alignment=Qt.AlignmentFlag.AlignLeft)

        # Summary
        if record.get("summary"):
            sum_label = QLabel("Summary:")
            sum_label.setStyleSheet("font-weight: 700; color: #1A1A2E; margin-top: 8px;")
            layout.addWidget(sum_label)
            summary_box = QTextEdit()
            summary_box.setPlainText(record["summary"])
            summary_box.setReadOnly(True)
            summary_box.setFixedHeight(100)
            layout.addWidget(summary_box)

        # Cover letter
        if record.get("cover_letter"):
            cl_label = QLabel("Cover Letter:")
            cl_label.setStyleSheet("font-weight: 700; color: #1A1A2E; margin-top: 8px;")
            layout.addWidget(cl_label)
            cl_box = QTextEdit()
            cl_box.setPlainText(record["cover_letter"])
            cl_box.setReadOnly(True)
            layout.addWidget(cl_box)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)


class HistoryCard(QFrame):
    def __init__(self, record: dict, on_view, on_delete):
        super().__init__()
        self.record = record
        self.setObjectName("card")
        layout = QHBoxLayout(self)
        layout.setContentsMargins(20, 16, 20, 16)
        layout.setSpacing(16)
        layout.setAlignment(Qt.AlignmentFlag.AlignVCenter)

        # Info
        info = QVBoxLayout()
        info.setSpacing(4)

        name = QLabel(record["job_name"])
        name.setStyleSheet("font-weight: 700; font-size: 14px; color: #1A1A2E;")
        info.addWidget(name)

        date = QLabel(record["date"])
        date.setStyleSheet("font-size: 12px; color: #6C757D;")
        info.addWidget(date)

        entries = record.get("selected_entries", [])
        if entries:
            entry_names = ", ".join(e["name"] for e in entries[:3])
            if len(entries) > 3:
                entry_names += f" +{len(entries) - 3} more"
            entry_label = QLabel(entry_names)
            entry_label.setStyleSheet("font-size: 11px; color: #6C757D;")
            info.addWidget(entry_label)

        layout.addLayout(info, stretch=1)

        # Score badge
        score = record.get("gap_analysis", {}).get("overall_match", 0)
        color = "#2E7D32" if score >= 70 else "#F57F17" if score >= 40 else "#E63946"
        score_label = QLabel(f"{score}%")
        score_label.setStyleSheet(
            f"font-size: 20px; font-weight: 700; color: {color}; min-width: 60px;"
        )
        score_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(score_label)

        # Buttons
        btn_col = QVBoxLayout()
        btn_col.setSpacing(6)

        view_btn = QPushButton("View")
        view_btn.setObjectName("secondary")
        view_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        view_btn.clicked.connect(on_view)
        btn_col.addWidget(view_btn)

        del_btn = QPushButton("Delete")
        del_btn.setObjectName("danger")
        del_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        del_btn.clicked.connect(on_delete)
        btn_col.addWidget(del_btn)

        layout.addLayout(btn_col)


class HistoryScreen(QWidget):
    def __init__(self):
        super().__init__()
        self._build_ui()
        self._load()

    def _build_ui(self):
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        # Top bar
        top = QWidget()
        top_layout = QHBoxLayout(top)
        top_layout.setContentsMargins(32, 20, 32, 20)

        title = QLabel("History")
        title.setObjectName("title")
        top_layout.addWidget(title)

        self.count_label = QLabel("")
        self.count_label.setObjectName("subtitle")
        self.count_label.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        top_layout.addWidget(self.count_label)

        outer.addWidget(top)

        line = QFrame()
        line.setFrameShape(QFrame.Shape.HLine)
        line.setStyleSheet("color: #DEE2E6;")
        outer.addWidget(line)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)

        self.container = QWidget()
        self.cards_layout = QVBoxLayout(self.container)
        self.cards_layout.setContentsMargins(32, 24, 32, 24)
        self.cards_layout.setSpacing(12)
        self.cards_layout.addStretch()

        scroll.setWidget(self.container)
        outer.addWidget(scroll)

    def _load(self):
        while self.cards_layout.count() > 1:
            item = self.cards_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        records = load_all()
        self.count_label.setText(f"{len(records)} applications")

        if not records:
            empty = QLabel("No history yet.\nAnalyse a job to get started.")
            empty.setObjectName("subtitle")
            empty.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self.cards_layout.insertWidget(0, empty)
            return

        for record in records:
            card = HistoryCard(
                record=record,
                on_view=lambda r=record: self._view(r),
                on_delete=lambda r=record: self._delete(r),
            )
            self.cards_layout.insertWidget(self.cards_layout.count() - 1, card)

    def _view(self, record: dict):
        dialog = HistoryDetailDialog(record, parent=self)
        dialog.exec()

    def _delete(self, record: dict):
        reply = QMessageBox.question(
            self, "Delete",
            f"Delete '{record['job_name']}' from history?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply == QMessageBox.StandardButton.Yes:
            delete_analysis(record["id"])
            self._load()
