"""Reusable UI widgets with Windows 11 styling."""
from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSlider,
    QVBoxLayout,
    QWidget,
)


class StatusDot(QLabel):
    """A small coloured circle indicating status."""

    def __init__(self, color: str = "#4cc764", parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._color = color
        self.setFixedSize(10, 10)
        self._update_style()

    def set_color(self, color: str) -> None:
        self._color = color
        self._update_style()

    def _update_style(self) -> None:
        self.setStyleSheet(f"""
            QLabel {{
                background-color: {self._color};
                border-radius: 5px;
                min-width: 10px;
                max-width: 10px;
                min-height: 10px;
                max-height: 10px;
            }}
        """)


class Card(QFrame):
    """A rounded card container."""

    def __init__(self, title: str = "", parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("Card")
        self._layout = QVBoxLayout(self)
        self._layout.setSpacing(8)
        self._layout.setContentsMargins(16, 16, 16, 16)
        if title:
            lbl = QLabel(title)
            lbl.setObjectName("Title")
            self._layout.addWidget(lbl)

    @property
    def card_layout(self) -> QVBoxLayout:
        return self._layout

    def add_row(self, *widgets: QWidget) -> QHBoxLayout:
        row = QHBoxLayout()
        row.setSpacing(8)
        for w in widgets:
            row.addWidget(w)
        self._layout.addLayout(row)
        return row


class StatusRow(QWidget):
    """Label + StatusDot + value label for the dashboard."""

    def __init__(self, label: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 2, 0, 2)

        self.dot = StatusDot()
        self.label = QLabel(label)
        self.value = QLabel("--")
        self.value.setAlignment(Qt.AlignmentFlag.AlignRight)

        layout.addWidget(self.dot)
        layout.addWidget(self.label, 1)
        layout.addWidget(self.value)

    def update(self, status: str, value: str) -> None:
        self.value.setText(value)
        color_map = {
            "good": "#4cc764", "excellent": "#4cc764",
            "warning": "#f5a623",
            "poor": "#e81123", "error": "#e81123", "inactive": "#888888",
        }
        self.dot.set_color(color_map.get(status.lower(), "#888888"))


class PrimaryButton(QPushButton):
    def __init__(self, text: str, parent: QWidget | None = None) -> None:
        super().__init__(text, parent)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setMinimumHeight(36)


class SecondaryButton(QPushButton):
    def __init__(self, text: str, parent: QWidget | None = None) -> None:
        super().__init__(text, parent)
        self.setObjectName("Secondary")
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setMinimumHeight(36)


class DangerButton(QPushButton):
    def __init__(self, text: str, parent: QWidget | None = None) -> None:
        super().__init__(text, parent)
        self.setObjectName("Danger")
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setMinimumHeight(36)


class SliderRow(QWidget):
    """Label + value + horizontal slider."""

    valueChanged = Signal(float)

    def __init__(self, label: str, min_val: float = 0, max_val: float = 100,
                 initial: float = 50, decimals: int = 1, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 4, 0, 4)

        self.label = QLabel(label)
        self.label.setFixedWidth(160)
        self.slider = QSlider(Qt.Orientation.Horizontal)
        self.slider.setRange(int(min_val * 10**decimals), int(max_val * 10**decimals))
        self.slider.setValue(int(initial * 10**decimals))
        self.value_label = QLabel(f"{initial:.{decimals}f}")
        self.value_label.setFixedWidth(50)
        self.value_label.setAlignment(Qt.AlignmentFlag.AlignRight)
        self._decimals = decimals

        self.slider.valueChanged.connect(self._on_change)

        layout.addWidget(self.label)
        layout.addWidget(self.slider, 1)
        layout.addWidget(self.value_label)

    def _on_change(self, val: int) -> None:
        fval = val / (10 ** self._decimals)
        self.value_label.setText(f"{fval:.{self._decimals}f}")
        self.valueChanged.emit(fval)

    def set_value(self, value: float, silent: bool = False) -> None:
        """Programmatically set the slider value (optionally without emitting)."""
        val = int(round(value * (10 ** self._decimals)))
        val = max(self.slider.minimum(), min(self.slider.maximum(), val))
        if silent:
            self.slider.blockSignals(True)
            self.slider.setValue(val)
            self.slider.blockSignals(False)
            self.value_label.setText(f"{val / (10 ** self._decimals):.{self._decimals}f}")
        else:
            self.slider.setValue(val)

    @property
    def value(self) -> float:
        return self.slider.value() / (10 ** self._decimals)


class SectionHeader(QLabel):
    def __init__(self, text: str, parent: QWidget | None = None) -> None:
        super().__init__(text, parent)
        self.setStyleSheet("font-size: 15px; font-weight: 600; margin-top: 12px; margin-bottom: 4px;")