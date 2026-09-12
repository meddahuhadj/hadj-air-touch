"""Shared mutable application state."""
from __future__ import annotations

import enum
import threading
from dataclasses import dataclass, field
from typing import Any


class AppStatus(enum.Enum):
    IDLE = "idle"
    RUNNING = "running"
    PAUSED = "paused"
    CALIBRATING = "calibrating"
    ERROR = "error"


class Mode(enum.Enum):
    AIR_MOUSE = "air_mouse"
    VIRTUAL_TOUCH = "virtual_touch"
    PRESENTATION = "presentation"
    GESTURE_MEDIA = "gesture_media"


@dataclass
class PipelineStats:
    fps: float = 0.0
    latency_ms: float = 0.0
    hands_detected: int = 0
    confidence: float = 0.0
    gesture: str = ""
    tracking_quality: str = "GOOD"


@dataclass
class AppState:
    status: AppStatus = AppStatus.IDLE
    mode: Mode = Mode.AIR_MOUSE
    camera_active: bool = False
    tracking_active: bool = False
    cursor_visible: bool = False
    cursor_x: int = 0
    cursor_y: int = 0
    stats: PipelineStats = field(default_factory=PipelineStats)
    _lock: Any = field(default_factory=threading.Lock, repr=False)

    def update(self, **kwargs: Any) -> None:
        with self._lock:
            for k, v in kwargs.items():
                setattr(self, k, v)

    def snapshot(self) -> AppState:
        with self._lock:
            import copy
            return copy.copy(self)