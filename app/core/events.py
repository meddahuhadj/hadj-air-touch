"""Lightweight in-process event bus (pub-sub)."""
from __future__ import annotations

import logging
import threading
from collections import defaultdict
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Any, Callable

_LOG = logging.getLogger(__name__)


class EventType(Enum):
    CAMERA_FRAME = auto()
    HAND_DETECTED = auto()
    HAND_LOST = auto()
    GESTURE_DETECTED = auto()
    GESTURE_COMPLETED = auto()
    TOUCH_DOWN = auto()
    TOUCH_UP = auto()
    DRAG_START = auto()
    DRAG_END = auto()
    CALIBRATION_STARTED = auto()
    CALIBRATION_STEP = auto()
    CALIBRATION_COMPLETE = auto()
    CALIBRATION_FAILED = auto()
    CURSOR_MOVE = auto()
    MOUSE_CLICK = auto()
    MOUSE_DOUBLE_CLICK = auto()
    MOUSE_RIGHT_CLICK = auto()
    MOUSE_SCROLL = auto()
    KEYBOARD_SHORTCUT = auto()
    STATE_CHANGED = auto()
    QUALITY_CHANGED = auto()
    PROFILE_CHANGED = auto()
    EMERGENCY_STOP = auto()
    SETTINGS_CHANGED = auto()


@dataclass
class Event:
    type: EventType
    data: dict[str, Any] = field(default_factory=dict)


Callback = Callable[[Event], None]


class EventBus:
    """Thread-safe minimal event bus."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._subs: dict[EventType, list[Callback]] = defaultdict(list)

    def subscribe(self, event_type: EventType, callback: Callback) -> Callable:
        with self._lock:
            self._subs[event_type].append(callback)

        def _unsub() -> None:
            with self._lock:
                try:
                    self._subs[event_type].remove(callback)
                except ValueError:
                    pass
        return _unsub

    def emit(self, event: Event) -> None:
        with self._lock:
            callbacks = list(self._subs.get(event.type, []))
        for cb in callbacks:
            try:
                cb(event)
            except Exception:
                _LOG.exception("Event handler error for %s", event.type.name)

    def emit_simple(self, event_type: EventType, **data: Any) -> None:
        self.emit(Event(type=event_type, data=data))