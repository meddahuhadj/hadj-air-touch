"""Windows 11-inspired theme for PySide6 (dark + light mode)."""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QPalette, QFont
from PySide6.QtWidgets import QApplication


# Windows 11 inspired colours
DARK_BG = "#1c1c1c"
DARK_CARD = "#2d2d2d"
DARK_TEXT = "#ffffff"
DARK_ACCENT = "#0078d4"
DARK_ACCENT_HOVER = "#1a8ae8"
DARK_BORDER = "#3d3d3d"
DARK_INPUT_BG = "#383838"
DARK_SUCCESS = "#4cc764"
DARK_WARNING = "#f5a623"
DARK_ERROR = "#e81123"

LIGHT_BG = "#f3f3f3"
LIGHT_CARD = "#ffffff"
LIGHT_TEXT = "#1a1a1a"
LIGHT_ACCENT = "#0078d4"
LIGHT_ACCENT_HOVER = "#1a8ae8"
LIGHT_BORDER = "#d1d1d1"
LIGHT_INPUT_BG = "#f9f9f9"
LIGHT_SUCCESS = "#4cc764"
LIGHT_WARNING = "#f5a623"
LIGHT_ERROR = "#e81123"


class Theme:
    def __init__(self, dark: bool = True) -> None:
        self.dark = dark
        if dark:
            self.bg = DARK_BG
            self.card = DARK_CARD
            self.text = DARK_TEXT
            self.accent = DARK_ACCENT
            self.accent_hover = DARK_ACCENT_HOVER
            self.border = DARK_BORDER
            self.input_bg = DARK_INPUT_BG
            self.success = DARK_SUCCESS
            self.warning = DARK_WARNING
            self.error = DARK_ERROR
        else:
            self.bg = LIGHT_BG
            self.card = LIGHT_CARD
            self.text = LIGHT_TEXT
            self.accent = LIGHT_ACCENT
            self.accent_hover = LIGHT_ACCENT_HOVER
            self.border = LIGHT_BORDER
            self.input_bg = LIGHT_INPUT_BG
            self.success = LIGHT_SUCCESS
            self.warning = LIGHT_WARNING
            self.error = LIGHT_ERROR

    def apply(self) -> str:
        return f"""
        QMainWindow, QWidget {{
            background-color: {self.bg};
            color: {self.text};
            font-family: 'Segoe UI Variable', 'Segoe UI', sans-serif;
            font-size: 13px;
        }}
        QFrame#Card {{
            background-color: {self.card};
            border: 1px solid {self.border};
            border-radius: 8px;
            padding: 16px;
        }}
        QLabel {{
            color: {self.text};
            background: transparent;
        }}
        QLabel#Title {{
            font-size: 22px;
            font-weight: 600;
        }}
        QLabel#Subtitle {{
            font-size: 14px;
            color: {self.text}88;
        }}
        QLabel#StatusGood {{
            color: {self.success};
            font-weight: 600;
        }}
        QLabel#StatusWarning {{
            color: {self.warning};
            font-weight: 600;
        }}
        QLabel#StatusError {{
            color: {self.error};
            font-weight: 600;
        }}
        QPushButton {{
            background-color: {self.accent};
            color: white;
            border: none;
            border-radius: 6px;
            padding: 10px 24px;
            font-size: 13px;
            font-weight: 600;
            min-height: 20px;
        }}
        QPushButton:hover {{
            background-color: {self.accent_hover};
        }}
        QPushButton:pressed {{
            background-color: {self.accent};
        }}
        QPushButton:disabled {{
            background-color: {self.border};
            color: {self.text}44;
        }}
        QPushButton#Secondary {{
            background-color: {self.card};
            color: {self.text};
            border: 1px solid {self.border};
        }}
        QPushButton#Secondary:hover {{
            border-color: {self.accent};
            color: {self.accent};
        }}
        QPushButton#Danger {{
            background-color: {self.error};
        }}
        QComboBox {{
            background-color: {self.input_bg};
            border: 1px solid {self.border};
            border-radius: 6px;
            padding: 8px 12px;
            color: {self.text};
            min-height: 20px;
        }}
        QComboBox:hover {{
            border-color: {self.accent};
        }}
        QComboBox::drop-down {{
            border: none;
        }}
        QComboBox QAbstractItemView {{
            background-color: {self.card};
            color: {self.text};
            border: 1px solid {self.border};
            border-radius: 6px;
            selection-background-color: {self.accent};
        }}
        QLineEdit {{
            background-color: {self.input_bg};
            border: 1px solid {self.border};
            border-radius: 6px;
            padding: 8px 12px;
            color: {self.text};
            min-height: 20px;
        }}
        QLineEdit:focus {{
            border-color: {self.accent};
        }}
        QSlider::groove:horizontal {{
            border: none;
            height: 4px;
            background: {self.border};
            border-radius: 2px;
        }}
        QSlider::handle:horizontal {{
            background: {self.accent};
            width: 16px;
            height: 16px;
            margin: -6px 0;
            border-radius: 8px;
        }}
        QCheckBox {{
            spacing: 8px;
            color: {self.text};
        }}
        QCheckBox::indicator {{
            width: 18px;
            height: 18px;
            border-radius: 4px;
            border: 2px solid {self.border};
            background: {self.input_bg};
        }}
        QCheckBox::indicator:checked {{
            background: {self.accent};
            border-color: {self.accent};
        }}
        QTabWidget::pane {{
            border: 1px solid {self.border};
            border-radius: 8px;
            background: {self.card};
        }}
        QTabBar::tab {{
            background: {self.bg};
            color: {self.text};
            border: 1px solid {self.border};
            border-bottom: none;
            padding: 8px 16px;
            border-top-left-radius: 8px;
            border-top-right-radius: 8px;
            margin-right: 2px;
        }}
        QTabBar::tab:selected {{
            background: {self.card};
            color: {self.accent};
            border-color: {self.accent};
        }}
        QProgressBar {{
            border: none;
            border-radius: 4px;
            background-color: {self.border};
            text-align: center;
            color: {self.text};
            height: 8px;
        }}
        QProgressBar::chunk {{
            border-radius: 4px;
            background-color: {self.accent};
        }}
        QScrollArea {{
            border: none;
            background: transparent;
        }}
        QScrollBar:vertical {{
            background: transparent;
            width: 8px;
        }}
        QScrollBar::handle:vertical {{
            background: {self.border};
            border-radius: 4px;
            min-height: 30px;
        }}
        QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
            height: 0;
        }}
        QToolTip {{
            background-color: {self.card};
            color: {self.text};
            border: 1px solid {self.border};
            border-radius: 4px;
            padding: 6px;
        }}
        """


def apply_theme(dark: bool = True) -> None:
    theme = Theme(dark)
    app = QApplication.instance()
    if app is None:
        return
    app.setStyleSheet(theme.apply())
    if dark:
        palette = QPalette()
        palette.setColor(QPalette.Window, QColor(DARK_BG))
        palette.setColor(QPalette.WindowText, QColor(DARK_TEXT))
        palette.setColor(QPalette.Base, QColor(DARK_CARD))
        palette.setColor(QPalette.AlternateBase, QColor(DARK_INPUT_BG))
        palette.setColor(QPalette.Text, QColor(DARK_TEXT))
        palette.setColor(QPalette.Button, QColor(DARK_CARD))
        palette.setColor(QPalette.ButtonText, QColor(DARK_TEXT))
        palette.setColor(QPalette.Highlight, QColor(DARK_ACCENT))
        palette.setColor(QPalette.HighlightedText, QColor("#ffffff"))
        app.setPalette(palette)
    font = QFont("Segoe UI Variable", 10)
    app.setFont(font)