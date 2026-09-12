"""Gesture recognition engine – runs individual detectors, manages cooldowns."""
from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from typing import Optional

from app.gestures.gestures import (
    GestureType,
    SwipeDetector,
    TwoFingerZoomDetector,
    WaveDetector,
    is_pointing,
    is_pinching,
    is_grabbing,
    is_open_palm,
    is_fist,
    is_two_finger_pinch,
    is_peace_sign,
    is_thumbs_up,
)
from app.tracking.models import HandData

_LOG = logging.getLogger(__name__)


@dataclass
class GestureResult:
    name: GestureType
    confidence: float = 1.0
    timestamp: float = 0.0


class GestureEngine:
    """Evaluates all gesture detectors each frame.

    Supports configurable cooldowns, double-pinch detection and swipe history.
    """

    def __init__(self) -> None:
        self._swipe = SwipeDetector()
        self._zoom = TwoFingerZoomDetector()
        self._wave = WaveDetector()

        self._last_pinch_time: float = 0.0
        self._double_pinch_window: float = 0.4
        self._pinch_cooldown: float = 0.25
        self._generic_cooldown: float = 0.3
        self._last_gesture_time: float = 0.0
        self._last_gesture: GestureType | None = None
        self._last_hand: Optional[HandData] = None

        # Edge-triggered pinch state machine (supports double-pinch)
        self._pinching_now: bool = False
        self._was_pinching: bool = False
        self._last_release_time: float = 0.0

        # Configurable gesture mapping (name -> enabled)
        self.configured_gestures: dict[str, bool] = {
            "point": True,
            "pinch": True,
            "double_pinch": True,
            "right_click": True,
            "grab": True,
            "open_palm": True,
            "fist": False,
            "swipe": True,
            "zoom": True,
            "peace": False,
            "thumbs_up": False,
            "wave": False,
        }

    def update(self, hand: HandData, now: float | None = None) -> Optional[GestureResult]:
        """Evaluate the frame.  Returns a GestureResult if a gesture fires."""
        if now is None:
            now = time.perf_counter()

        self._last_hand = hand

        # Swipe (has internal cooldown)
        if self.configured_gestures.get("swipe"):
            swipe_gesture = self._swipe.update(hand, now)
            if swipe_gesture is not None:
                return self._emit(swipe_gesture, now)

        # Zoom
        if self.configured_gestures.get("zoom"):
            zoom_gesture = self._zoom.update(hand, now)
            if zoom_gesture is not None:
                return self._emit(zoom_gesture, now)

        # Wave (motion gesture: rapid horizontal oscillation)
        if self.configured_gestures.get("wave"):
            wave_gesture = self._wave.update(hand, now)
            if wave_gesture is not None:
                return self._emit(wave_gesture, now)

        # Pinch is edge-triggered so a quick press/release/press
        # is detected as a double-pinch instead of being muted by cooldowns.
        if self.configured_gestures.get("pinch"):
            self._pinching_now = is_pinching(hand)
            if self._pinching_now and not self._was_pinching:
                # Pinch just pressed
                self._was_pinching = True
                if (self.configured_gestures.get("double_pinch")
                        and now - self._last_pinch_time < self._double_pinch_window
                        and self._last_pinch_time > 0.0):
                    self._last_pinch_time = now
                    return self._emit(GestureType.DOUBLE_PINCH, now)
                self._last_pinch_time = now
                return self._emit(GestureType.PINCH, now)
            if not self._pinching_now and self._was_pinching:
                self._was_pinching = False
                self._last_release_time = now

        # Static gestures with cooldown
        if now - self._last_gesture_time < self._generic_cooldown:
            return None

        # Priority order: open_palm > fist > thumbs_up > right_click > grab > point
        if self.configured_gestures.get("open_palm") and is_open_palm(hand):
            return self._emit(GestureType.OPEN_PALM, now)

        if self.configured_gestures.get("fist") and is_fist(hand):
            return self._emit(GestureType.FIST, now)

        if self.configured_gestures.get("thumbs_up") and is_thumbs_up(hand):
            return self._emit(GestureType.THUMBS_UP, now)

        if self.configured_gestures.get("right_click") and is_two_finger_pinch(hand):
            self._was_pinching = False
            return self._emit(GestureType.RIGHT_CLICK, now)

        if self.configured_gestures.get("grab") and is_grabbing(hand):
            return self._emit(GestureType.GRAB, now)

        if self.configured_gestures.get("point") and is_pointing(hand):
            return self._emit(GestureType.POINT, now)

        return None

    def _emit(self, gesture: GestureType, now: float) -> GestureResult:
        self._last_gesture = gesture
        self._last_gesture_time = now
        return GestureResult(name=gesture, timestamp=now)

    def configure(self, gesture_name: str, enabled: bool) -> None:
        self.configured_gestures[gesture_name] = enabled

    def get_active_gesture(self) -> Optional[GestureType]:
        return self._last_gesture