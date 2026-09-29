import time

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QPlainTextEdit, QPushButton, QVBoxLayout, QWidget

STYLE = """
* { font-family: 'Segoe UI', 'Inter', sans-serif; font-size: 13px; }
QWidget { background: #0b0f14; color: #e7edf5; }
QLabel { background: transparent; }
QLabel#title { font-size: 24px; font-weight: 700; }
QLabel#subtitle, QLabel#muted, QLabel#cardLabel { color: #8fa3b8; }
QLabel#cardLabel { font-size: 12px; }
QLabel#cardValue { font-size: 24px; font-weight: 700; }
QLabel#bigValue { font-size: 38px; font-weight: 700; color: #0a8be9; }
QLabel#warning { color: #fbbf24; background: #2b2208; border: 1px solid #5c4610; border-radius: 8px; padding: 10px 12px; }
QFrame#card { background: #101722; border: 1px solid #1c2a3a; border-radius: 10px; }
QFrame#card QLabel { background: transparent; }
QLabel#badge { border-radius: 10px; padding: 4px 12px; font-weight: 600; background: #1c2a3a; color: #8fa3b8; }
QLabel#badge[kind="running"] { background: #0f3d2a; color: #4ade80; }
QLabel#badge[kind="paused"] { background: #45330b; color: #fbbf24; }
QLabel#badge[kind="error"] { background: #4a1616; color: #f87171; }
QLabel#badge[kind="info"] { background: #0c3557; color: #60b4f5; }
QPushButton { background: #0879d1; color: white; border: 0; border-radius: 7px; padding: 9px 18px; font-weight: 600; }
QPushButton:hover { background: #0a8be9; }
QPushButton:disabled { background: #16212e; color: #56677a; }
QPushButton[variant="secondary"] { background: #16212e; color: #e7edf5; border: 1px solid #26384b; }
QPushButton[variant="secondary"]:hover { background: #1c2b3d; }
QPushButton[variant="secondary"]:disabled { color: #56677a; }
QPushButton[variant="danger"] { background: #8a2222; }
QPushButton[variant="danger"]:hover { background: #a82a2a; }
QPushButton[variant="danger"]:disabled { background: #16212e; color: #56677a; }
QPlainTextEdit, QTableWidget, QListWidget { background: #101722; border: 1px solid #1c2a3a; border-radius: 8px; }
QPlainTextEdit#log { font-family: Consolas, 'DejaVu Sans Mono', monospace; font-size: 12px; color: #b6c4d4; padding: 4px; }
QListWidget { outline: 0; padding: 4px; }
QListWidget::item { padding: 11px 12px; border-radius: 6px; }
QListWidget::item:selected { background: #0879d1; color: white; }
QListWidget::item:hover:!selected { background: #16212e; }
QTableWidget { gridline-color: #1c2a3a; }
QTableWidget::item { padding: 4px 10px; }
QHeaderView::section { background: #0e151e; color: #8fa3b8; border: 0; padding: 8px 10px; font-weight: 600; }
QTableCornerButton::section { background: #0e151e; border: 0; }
QDoubleSpinBox, QSpinBox, QLineEdit { background: #0e151e; border: 1px solid #26384b; border-radius: 6px; padding: 6px 8px; }
QDoubleSpinBox:focus, QSpinBox:focus, QLineEdit:focus { border: 1px solid #0879d1; }
QTabWidget::pane { border: 1px solid #1c2a3a; border-radius: 8px; top: -1px; }
QTabBar::tab { background: #0e151e; color: #8fa3b8; padding: 8px 16px; border: 1px solid #1c2a3a; border-bottom: 0; }
QTabBar::tab:selected { background: #101722; color: #e7edf5; }
QScrollBar:vertical { background: transparent; width: 10px; }
QScrollBar::handle:vertical { background: #26384b; border-radius: 5px; min-height: 24px; }
QScrollBar::add-line, QScrollBar::sub-line { height: 0; }
"""


def format_duration(seconds):
    hours, rest = divmod(int(seconds), 3600)
    minutes, secs = divmod(rest, 60)
    return f"{hours:02d}:{minutes:02d}:{secs:02d}"


def make_button(text, on_click=None, variant=None):
    button = QPushButton(text)
    if variant:
        button.setProperty("variant", variant)
    if on_click:
        button.clicked.connect(lambda _checked=False: on_click())
    button.setCursor(Qt.PointingHandCursor)
    return button


def repolish(widget):
    widget.style().unpolish(widget)
    widget.style().polish(widget)


class Badge(QLabel):
    def __init__(self, text="Arrêté", kind="idle"):
        super().__init__()
        self.setObjectName("badge")
        self.set_state(text, kind)

    def set_state(self, text, kind):
        self.setText(text)
        if self.property("kind") != kind:
            self.setProperty("kind", kind)
            repolish(self)


class PageHeader(QWidget):
    def __init__(self, title, subtitle):
        super().__init__()
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        text = QVBoxLayout()
        text.setSpacing(2)
        heading = QLabel(title)
        heading.setObjectName("title")
        self.subtitle = QLabel(subtitle)
        self.subtitle.setObjectName("subtitle")
        self.subtitle.setWordWrap(True)
        text.addWidget(heading)
        text.addWidget(self.subtitle)

        self.badge = Badge()
        layout.addLayout(text, 1)
        layout.addWidget(self.badge, 0, Qt.AlignTop)


class StatCard(QFrame):
    def __init__(self, label, value="—"):
        super().__init__()
        self.setObjectName("card")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 12, 16, 12)
        layout.setSpacing(2)
        self.label = QLabel(label)
        self.label.setObjectName("cardLabel")
        self.value = QLabel(value)
        self.value.setObjectName("cardValue")
        layout.addWidget(self.label)
        layout.addWidget(self.value)

    def set_value(self, text):
        self.value.setText(text)


class LogBox(QPlainTextEdit):
    def __init__(self, height=120):
        super().__init__()
        self.setObjectName("log")
        self.setReadOnly(True)
        self.setMaximumBlockCount(500)
        self.setMinimumHeight(height)

    def add(self, text):
        self.appendPlainText(f"[{time.strftime('%H:%M:%S')}] {text}")


def button_row(*widgets):
    row = QHBoxLayout()
    row.setSpacing(10)
    for widget in widgets:
        if widget is None:
            row.addStretch(1)
        else:
            row.addWidget(widget)
    return row


def card_row(*cards):
    row = QHBoxLayout()
    row.setSpacing(12)
    for card in cards:
        row.addWidget(card, 1)
    return row
