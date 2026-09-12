"""Qt-free shared state for the cursor halo overlay.

The pipeline thread (real cursor pos, gesture, clicks) writes here; the
overlay's GUI-thread timer reads it. Keeping it free of Qt/PySide means it can
be unit-tested without a GUI environment.
"""
from __future__ import annotations

import threading
import time
from typing import Callable

PositionSink = Callable[[tuple[float, float]], None]


class OverlayPositionStore:
    """Thread-safe store for the current cursor position + interaction state."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._x = 0.0
        self._y = 0.0
        self._ts = 0.0
        self._active = False
        self._gesture: str | None = None
        self._gesture_ts = 0.0
        self._click_ts = 0.0

    def update(self, pos: tuple[float, float]) -> None:
        """Record the latest cursor position (called from any thread)."""
        with self._lock:
            self._x = float(pos[0])
            self._y = float(pos[1])
            self._ts = time.monotonic()
            self._active = True

    def set_gesture(self, gesture: str | None) -> None:
        with self._lock:
            self._gesture = gesture
            self._gesture_ts = time.monotonic()

    def notify_click(self) -> None:
        with self._lock:
            self._click_ts = time.monotonic()

    def set_clear(self) -> None:
        with self._lock:
            self._active = False

    def read(self) -> tuple[float, float, float, bool, str | None, float, float]:
        """Return (x, y, ts, active, gesture, gesture_ts, click_ts)."""
        with self._lock:
            return (
                self._x,
                self._y,
                self._ts,
                self._active,
                self._gesture,
                self._gesture_ts,
                self._click_ts,
            )