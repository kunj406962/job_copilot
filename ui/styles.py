"""Global Qt stylesheet for the Job Copilot desktop UI.

This module defines the shared light theme, component styling, and layout
constants used across the PyQt screens.
"""

STYLESHEET = """
/* ── App-wide ── */
QWidget {
    background-color: #F8F9FA;
    color: #1A1A2E;
    font-family: 'Segoe UI', Arial, sans-serif;
    font-size: 13px;
}

QMainWindow {
    background-color: #F8F9FA;
}

/* ── Labels ── */
QLabel {
    color: #1A1A2E;
    font-size: 13px;
}

QLabel#title {
    font-size: 24px;
    font-weight: 700;
    color: #1A1A2E;
}

QLabel#subtitle {
    font-size: 13px;
    color: #6C757D;
}

QLabel#section_label {
    font-size: 11px;
    font-weight: 700;
    color: #6C757D;
    letter-spacing: 1px;
}

/* ── Input Fields ── */
QLineEdit, QTextEdit, QPlainTextEdit {
    background-color: #FFFFFF;
    border: 1.5px solid #DEE2E6;
    border-radius: 8px;
    padding: 8px 12px;
    font-size: 13px;
    color: #1A1A2E;
    selection-background-color: #4361EE;
}

QLineEdit:focus, QTextEdit:focus, QPlainTextEdit:focus {
    border: 1.5px solid #4361EE;
    background-color: #FFFFFF;
}

QLineEdit:disabled, QTextEdit:disabled {
    background-color: #F1F3F5;
    color: #ADB5BD;
}

/* ── Buttons — base ── */
QPushButton {
    background-color: #4361EE;
    color: #FFFFFF;
    border: none;
    border-radius: 8px;
    padding: 8px 18px;
    font-size: 13px;
    font-weight: 600;
    min-height: 36px;
}

QPushButton:hover {
    background-color: #3A56D4;
}

QPushButton:pressed {
    background-color: #2F44B0;
}

QPushButton:disabled {
    background-color: #ADB5BD;
    color: #F8F9FA;
}

QPushButton#secondary {
    background-color: #FFFFFF;
    color: #4361EE;
    border: 1.5px solid #4361EE;
    padding: 8px 18px;
    min-height: 36px;
}

QPushButton#secondary:hover {
    background-color: #EEF1FD;
}

QPushButton#danger {
    background-color: #FFFFFF;
    color: #E63946;
    border: 1.5px solid #E63946;
    padding: 6px 14px;
    min-height: 32px;
}

QPushButton#danger:hover {
    background-color: #FFF0F1;
}

/* ── Cards ── */
QFrame#card {
    background-color: #FFFFFF;
    border: 1.5px solid #DEE2E6;
    border-radius: 12px;
}

/* ── Scroll Area ── */
QScrollArea {
    border: none;
    background-color: transparent;
}

QScrollBar:vertical {
    background-color: #F1F3F5;
    width: 8px;
    border-radius: 4px;
}

QScrollBar::handle:vertical {
    background-color: #CED4DA;
    border-radius: 4px;
    min-height: 30px;
}

QScrollBar::handle:vertical:hover {
    background-color: #ADB5BD;
}

QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
    height: 0px;
}

/* ── ComboBox ── */
QComboBox {
    background-color: #FFFFFF;
    border: 1.5px solid #DEE2E6;
    border-radius: 8px;
    padding: 8px 12px;
    font-size: 13px;
    color: #1A1A2E;
    min-height: 36px;
}

QComboBox:focus {
    border: 1.5px solid #4361EE;
}

QComboBox::drop-down {
    border: none;
    width: 24px;
}

QComboBox QAbstractItemView {
    background-color: #FFFFFF;
    border: 1.5px solid #DEE2E6;
    border-radius: 8px;
    selection-background-color: #EEF1FD;
    selection-color: #1A1A2E;
}

/* ── Progress Bar ── */
QProgressBar {
    background-color: #DEE2E6;
    border: none;
    border-radius: 6px;
    height: 10px;
    text-align: center;
    font-size: 11px;
    color: transparent;
}

QProgressBar::chunk {
    border-radius: 6px;
    background-color: #4361EE;
}

/* ── Message Box ── */
QMessageBox {
    background-color: #F8F9FA;
}

QMessageBox QPushButton {
    min-width: 80px;
}

/* ── Sidebar ── */
QWidget#sidebar {
    background-color: #FFFFFF;
    border-right: 1.5px solid #DEE2E6;
}

QPushButton#nav_btn {
    background-color: transparent;
    color: #6C757D;
    border: none;
    border-radius: 8px;
    padding: 10px 16px;
    font-size: 13px;
    font-weight: 600;
    text-align: left;
    min-height: 44px;
}

QPushButton#nav_btn:hover {
    background-color: #F1F3F5;
    color: #1A1A2E;
}

QPushButton#nav_btn:checked {
    background-color: #EEF1FD;
    color: #4361EE;
}
"""
