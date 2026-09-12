"""Transparent full-screen cursor halo overlay (HUD).

Shows a soft glowing halo at the position where the application currently
directs the Windows cursor, plus a gesture accent ring and a click pulse, so
the user always sees what the camera sees.

The overlay is click-through and focus-less: it never steals mouse events or
keyboard focus (`WindowTransparentForInput` + `WindowDoesNotAcceptFocus`), so
it can sit above other windows while the user interacts normally.
"""
from __future__ import annotations

import logging
import time

from PySide6.QtCore import QPointF, Qt, QTimer
from PySide6.QtGui import QColor, QGuiApplication, QPainter, QPen, QRadialGradient
from PySide6.QtWidgets import QWidget

from app.ui.overlay_state import OverlayPositionStore

_LOG = logging.getLogger(__name__)

_MAX_AGE_S = 0.25  # halo fades out if no position update for this long
_LERP = 0.35       # smoothing factor for the halo chasing the target


class CursorHaloOverlay(QWidget):
    """Borderless, top-most, click-through overlay drawing the cursor halo."""

    def __init__(self, store: OverlayPositionStore, size: int = 64,
                 opacity: float = 0.85, parent: QWidget | None = None) -> None:
        super().__init__(parent, Qt.WindowType.Tool | Qt.WindowType.FramelessWindowHint
                          | Qt.WindowType.WindowStaysOnTopHint
                          | Qt.WindowType.WindowDoesNotAcceptFocus
                          | Qt.WindowType.WindowTransparentForInput)
        self.setWindowTitle("HADJ Cursor Halo")
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)

        self._store = store
        self._size = size
        self._opacity = opacity

        screen = QGuiApplication.primaryScreen()
        geo = screen.geometry() if screen else None
        if geo is None:
            geo = self.screen().geometry() if self.screen() else None
        width = geo.width() if geo else 1920
        height = geo.height() if geo else 1080
        x = geo.x() if geo else 0
        y = geo.y() if geo else 0
        self.setGeometry(x, y, width, height)

        self._cx = width / 2.0
        self._cy = height / 2.0
        self._target = (self._cx, self._cy)
        self._visible_alpha = 0.0

        self._timer = QTimer(self)
        self._timer.setInterval(16)
        self._timer.timeout.connect(self._tick)

    # -- lifecycle --

    def start(self) -> None:
        self._store.set_clear()
        self._visible_alpha = 0.0
        self.show()
        self.raise_()
        self._timer.start()
        _LOG.info("Cursor halo overlay started")

    def stop(self) -> None:
        self._timer.stop()
        self.hide()
        _LOG.info("Cursor halo overlay stopped")

    # -- animation loop --

    def _tick(self) -> None:
        x, y, ts, active, _g, _gts, _cts = self._store.read()
        now = time.monotonic()
        fresh = active and (now - ts) <= _MAX_AGE_S

        if fresh:
            self._target = (x, y)
            self._visible_alpha = min(1.0, self._visible_alpha + 0.2)
        else:
            self._visible_alpha = max(0.0, self._visible_alpha - 0.06)

        self._cx += (self._target[0] - self._cx) * _LERP
        self._cy += (self._target[1] - self._cy) * _LERP

        self.setWindowOpacity(max(0.0, min(1.0, self._opacity * self._visible_alpha)))
        self.update()

    # -- painting --

    def _gesture_accent(self, gesture: str | None) -> QColor:
        if not gesture:
            return QColor(0, 229, 255)
        g = gesture.lower()
        if g in ("pinch", "double_pinch", "point"):
            return QColor(255, 179, 0)
        if g in ("grab", "fist", "open_palm"):
            return QColor(255, 82, 82)
        if g in ("thumbs_up", "wave", "peace"):
            return QColor(85, 239, 196)
        return QColor(0, 229, 255)

    def paintEvent(self, _event) -> None:  # noqa: N802
        if self._visible_alpha <= 0.01:
            return
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        _x, _y, _ts, _active, gesture, _gts, click_ts = self._store.read()
        now = time.monotonic()
        center = QPointF(self._cx, self._cy)
        r = float(self._size)

        # Soft halo
        grad = QRadialGradient(center, r)
        grad.setColorAt(0.0, QColor(0, 229, 255, 90))
        grad.setColorAt(0.7, QColor(0, 229, 255, 26))
        grad.setColorAt(1.0, QColor(0, 229, 255, 0))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(grad)
        painter.drawEllipse(center, r, r)

        # Gesture accent ring
        if gesture and (now - _gts) < 0.4:
            painter.setPen(QPen(self._gesture_accent(gesture), 3))
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawEllipse(center, r + 8, r + 8)

        # Click pulse (expanding ring)
        age = now - click_ts
        if click_ts > 0 and 0 <= age < 0.4:
            p = age / 0.4
            radius = r + 12 + p * 26
            pen = QPen(QColor(255, 255, 255, int(180 * (1 - p))), 2)
            painter.setPen(pen)
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawEllipse(center, radius, radius)

        # Precise crosshair at the exact target point
        pen = QPen(QColor(255, 255, 255, 140), 1)
        painter.setPen(pen)
        for d in (4, 8):
            painter.drawLine(center.x() - d, center.y(), center.x() - 2, center.y())
            painter.drawLine(center.x() + 2, center.y(), center.x() + d, center.y())
            painter.drawLine(center.x(), center.y() - d, center.x(), center.y() - 2)
            painter.drawLine(center.x(), center.y() + 2, center.x(), center.y() + d)

        painter.end()