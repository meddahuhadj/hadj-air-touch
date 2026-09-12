"""Frameless on-screen keyboard overlay for air-touch typing.

The overlay is a top-most window that never takes input focus
(Qt.WindowDoesNotAcceptFocus), so keys typed via mouse clicks or air-mouse
pinches go to whatever application has focus underneath.

Each key emits a `keyPressed(code, label)` signal; the caller is expected to
inject the key via the KeyboardController (virtual-key code or Unicode).
"""
from __future__ import annotations

import logging

from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtWidgets import (
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from app.keyboard.virtual_keyboard import (
    KeyboardLayout,
    VirtualKeyboard,
)
from app.ui.theme import DARK_CARD, DARK_BORDER

_LOG = logging.getLogger(__name__)

_KEY_BG = "#2b2b2b"
_KEY_HOVER = "#3f6bff"
_KEY_ACTIVE = "#c9a227"


class _KeyButton(QPushButton):
    """A single keyboard key with hover highlighting."""

    def __init__(self, label: str, code: str, width: int, parent: QWidget | None = None) -> None:
        super().__init__(label, parent)
        self.code = code
        self.width = width
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setProperty("kbHovered", False)
        self.setStyleSheet(self._base_style(False))

    @staticmethod
    def _base_style(hovered: bool) -> str:
        bg = _KEY_HOVER if hovered else _KEY_BG
        return f"""
            QPushButton {{
                background-color: {bg};
                color: #e8e8e8;
                border: 1px solid {DARK_BORDER};
                border-radius: 6px;
                font-size: 15px;
                font-weight: 600;
                padding: 4px;
            }}
            QPushButton:hover {{
                background-color: {_KEY_HOVER};
            }}
            QPushButton:pressed {{
                background-color: {_KEY_ACTIVE};
            }}
        """

    def set_hovered(self, hovered: bool) -> None:
        self.setStyleSheet(self._base_style(hovered))


class OverlayKeyboard(QWidget):
    """Top-most, borderless on-screen keyboard."""

    keyPressed = Signal(str, str)  # (code, label)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent, Qt.WindowType.Tool | Qt.WindowType.WindowStaysOnTopHint
                          | Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowDoesNotAcceptFocus)
        self.setWindowTitle("HADJ Keyboard")
        self._vk = VirtualKeyboard()
        self._buttons: list[list[_KeyButton]] = []
        self._hover_timer = QTimer(self)
        self._hover_timer.setInterval(80)
        self._hover_timer.timeout.connect(self._track_hover)
        self._current_hover_code: str | None = None

        self._unit_width = 56
        self._unit_height = 44

        self._build()
        self.setStyleSheet(f"background-color: {DARK_CARD};")

    # -- construction --

    def _build(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(10, 8, 10, 10)
        root.setSpacing(6)

        header = QHBoxLayout()
        title = QLabel("HADJ VIRTUAL KEYBOARD")
        title.setStyleSheet("color:#888; font-size:11px; font-weight:700;")
        header.addWidget(title)
        header.addStretch()
        close_btn = QPushButton("✕")
        close_btn.setFixedSize(24, 24)
        close_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        close_btn.setStyleSheet(
            "background:#3a3a3a; color:#ccc; border:1px solid #555; border-radius:4px;")
        close_btn.clicked.connect(self.hide)
        header.addWidget(close_btn)
        root.addLayout(header)

        grid = QGridLayout()
        grid.setSpacing(5)
        grid.setContentsMargins(0, 0, 0, 0)
        for row_idx, row in enumerate(self._vk.keys):
            col = 0
            buttons: list[_KeyButton] = []
            for kd in row:
                btn = _KeyButton(kd.label, kd.code, kd.width)
                btn.clicked.connect(
                    lambda _checked=False, code=kd.code, label=kd.label: self._emit_key(code, label))
                grid.addWidget(btn, row_idx, col, 1, kd.width)
                buttons.append(btn)
                col += kd.width
            self._buttons.append(buttons)
        root.addLayout(grid)

        self._unit_width = 56
        self._unit_height = 44
        self.setFixedSize(*self._compute_size())

    def _compute_size(self) -> tuple[int, int]:
        max_width = max((sum(k.width for k in row) for row in self._vk.keys),
                        default=16)
        rows = len(self._vk.keys)
        margin = 20
        return (max_width * self._unit_width + margin + 80,
                rows * self._unit_height + 60)

    # -- layout switching --

    def set_layout(self, layout: KeyboardLayout) -> None:
        self._vk.set_layout(layout)
        self.close_current()

    def close_current(self) -> None:
        # Simplest robust approach: rebuild the whole widget for a new layout.
        _LOG.debug("Rebuilding overlay keyboard for %s", self._vk.layout)
        self._rebuild()

    def _rebuild(self) -> None:
        old = self._buttons
        self._buttons = []
        self._current_hover_code = None
        layout = self.layout()
        # Drop all current widgets and rebuild grid
        self._clear()
        self._build()

    def _clear(self) -> None:
        while self.layout().count():
            item = self.layout().takeAt(0)
            w = item.widget()
            if w is not None:
                w.deleteLater()
            elif item.layout() is not None:
                sub = item.layout()
                while sub.count():
                    si = sub.takeAt(0)
                    if si.widget() is not None:
                        si.widget().deleteLater()

    # -- interaction --

    def _emit_key(self, code: str, label: str) -> None:
        self.keyPressed.emit(code, label)

    def set_hover(self, key_code: str | None) -> None:
        """Externally-driven hover highlight (e.g. from hand tracking)."""
        if key_code == self._current_hover_code:
            return
        for row in self._buttons:
            for b in row:
                b.set_hovered(b.code == key_code)
        self._current_hover_code = key_code

    def _track_hover(self) -> None:
        """Highlight the key currently under the system cursor."""
        pos = self.mapFromGlobal(self.cursor().pos())
        code: str | None = None
        if self.rect().contains(pos):
            w = self.childAt(pos)
            if isinstance(w, _KeyButton):
                code = w.code
        self.set_hover(code)

    def toggle(self) -> None:
        if self.isVisible():
            self.hide()
        else:
            self._position_and_show()

    def show_overlay(self) -> None:
        self._position_and_show()

    def _position_and_show(self) -> None:
        screen = self.screen() or self.windowHandle().screen()
        if screen is None:
            self.show()
            return
        geo = screen.availableGeometry()
        x = geo.x() + (geo.width() - self.width()) // 2
        y = geo.y() + geo.height() - self.height() - 40
        self.move(x, y)
        self.show()
        self.raise_()
        self._hover_timer.start()

    def hideEvent(self, event) -> None:  # noqa: N802
        self._hover_timer.stop()
        super().hideEvent(event)

    def showEvent(self, event) -> None:  # noqa: N802
        self._hover_timer.start()
        super().showEvent(event)