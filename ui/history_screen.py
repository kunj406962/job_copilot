from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QScrollArea, QFrame, QMessageBox
)
from PyQt6.QtCore import Qt
from core.history import load_all, delete_analysis


class HistoryCard(QFrame):
    def __init__(self, record: dict, on_open, on_delete):
        super().__init__()
        self.record = record
        self.on_open = on_open
        self.on_delete = on_delete
        self.setObjectName("card")
        self._build_ui()

    def _build_ui(self):
        layout = QHBoxLayout(self)
        layout.setContentsMargins(20, 16, 20, 16)
        layout.setSpacing(16)
        layout.setAlignment(Qt.AlignmentFlag.AlignVCenter)

        info = QVBoxLayout()
        info.setSpacing(4)

        name_row = QHBoxLayout()
        name = QLabel(self.record["job_name"])
        name.setStyleSheet("font-weight: 700; font-size: 14px; color: #1A1A2E;")
        name_row.addWidget(name)

        status = self.record.get("status", "search_done")
        status_label = QLabel("Docs Ready" if status == "docs_done" else "In Progress")
        status_color = "#2E7D32" if status == "docs_done" else "#F57F17"
        status_bg = "#E8F5E9" if status == "docs_done" else "#FFF8E1"
        status_label.setStyleSheet(
            f"background-color: {status_bg}; color: {status_color}; border-radius: 4px;"
            "padding: 2px 8px; font-size: 10px; font-weight: 700;"
        )
        name_row.addWidget(status_label)
        name_row.addStretch()
        info.addLayout(name_row)

        date_text = self.record.get("updated", self.record.get("date", ""))
        date = QLabel(date_text)
        date.setStyleSheet("font-size: 12px; color: #6C757D;")
        info.addWidget(date)

        selected_ids = set(self.record.get("selected_ids", []))
        entries = [e for e in self.record.get("ranked_entries", []) if e.get("id") in selected_ids]
        if entries:
            entry_names = ", ".join(e["name"] for e in entries[:3])
            if len(entries) > 3:
                entry_names += f" +{len(entries) - 3} more"
            entry_label = QLabel(entry_names)
            entry_label.setStyleSheet("font-size: 11px; color: #6C757D;")
            info.addWidget(entry_label)

        layout.addLayout(info, stretch=1)

        score = self.record.get("gap_analysis", {}).get("overall_match", 0)
        color = "#2E7D32" if score >= 70 else "#F57F17" if score >= 40 else "#E63946"
        score_label = QLabel(f"{score}%")
        score_label.setStyleSheet(
            f"font-size: 20px; font-weight: 700; color: {color}; min-width: 60px;"
        )
        score_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(score_label)

        btn_col = QVBoxLayout()
        btn_col.setSpacing(6)

        open_btn = QPushButton("Open")
        open_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        open_btn.clicked.connect(self._on_open_clicked)
        btn_col.addWidget(open_btn)

        del_btn = QPushButton("Delete")
        del_btn.setObjectName("danger")
        del_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        del_btn.clicked.connect(self._on_delete_clicked)
        btn_col.addWidget(del_btn)

        layout.addLayout(btn_col)

    def _on_open_clicked(self):
        self.on_open(self.record)

    def _on_delete_clicked(self):
        self.on_delete(self.record)


class HistoryScreen(QWidget):
    def __init__(self, on_open_record=None):
        super().__init__()
        self.on_open_record = on_open_record
        self._build_ui()
        self._load()

    def _build_ui(self):
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

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

    def showEvent(self, event):
        super().showEvent(event)
        self._load()

    def _load(self):
        for i in reversed(range(self.cards_layout.count())):
            item = self.cards_layout.itemAt(i)
            if item.widget():
                item.widget().deleteLater()
            self.cards_layout.removeItem(item)

        records = load_all()
        self.count_label.setText(f"{len(records)} applications")

        if not records:
            empty = QLabel("No history yet.\nAnalyse a job to get started.")
            empty.setObjectName("subtitle")
            empty.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self.cards_layout.addWidget(empty)
            self.cards_layout.addStretch()
            return

        for record in records:
            card = HistoryCard(
                record=record,
                on_open=self._open,
                on_delete=self._delete,
            )
            self.cards_layout.addWidget(card)

        self.cards_layout.addStretch()

    def _open(self, record: dict):
        if self.on_open_record:
            self.on_open_record(record)

    def _delete(self, record: dict):
        reply = QMessageBox.question(
            self, "Delete",
            f"Delete '{record['job_name']}' from history?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply == QMessageBox.StandardButton.Yes:
            delete_analysis(record["id"])
            self._load()
