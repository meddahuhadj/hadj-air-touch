"""Gesture recognizers – pure detection functions.

Each function takes a HandData + optional previous state and returns a bool
or a named gesture (string).  The engine dispatches these.
"""
from __future__ import annotations

import time
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Optional

from app.tracking.models import HandData
from app.utils.vectors import vec_distance, vec_length, vec_sub


class GestureType(Enum):
    NONE = auto()
    POINT = auto()
    PINCH = auto()
    DOUBLE_PINCH = auto()
    RIGHT_CLICK = auto()
    GRAB = auto()
    OPEN_PALM = auto()
    FIST = auto()
    SWIPE_LEFT = auto()
    SWIPE_RIGHT = auto()
    SWIPE_UP = auto()
    SWIPE_DOWN = auto()
    TWO_FINGER_PINCH_IN = auto()
    TWO_FINGER_PINCH_OUT = auto()
    THUMBS_UP = auto()
    PEACE = auto()
    WAVE = auto()


# ---------------------------------------------------------------------------
# Individual detectors
# ---------------------------------------------------------------------------

def is_pointing(hand: HandData) -> bool:
    """Index finger extended, others folded (or at least middle folded)."""
    fs = hand.finger_states
    if not fs:
        return False
    index_ext = fs.get("index") is not None and fs["index"].value == "extended"
    middle_folded = fs.get("middle") is None or fs["middle"].value == "folded"
    ring_folded = fs.get("ring") is None or fs["ring"].value == "folded"
    pinky_folded = fs.get("pinky") is None or fs["pinky"].value == "folded"
    return index_ext and middle_folded and ring_folded and pinky_folded


def is_pinching(hand: HandData, threshold: float = 0.06) -> bool:
    """Thumb and index finger tips are very close together."""
    d = hand.pinch_distance
    return d is not None and d < threshold


def is_two_finger_pinch(hand: HandData, threshold: float = 0.06) -> bool:
    """Thumb + middle finger close (right-click gesture)."""
    from app.tracking.models import MIDDLE_TIP, THUMB_TIP
    t = hand.thumb_tip
    m = hand._pos(MIDDLE_TIP)
    if t is None or m is None:
        return False
    return vec_distance(t, m) < threshold


def is_grabbing(hand: HandData) -> bool:
    """All fingers folded."""
    fs = hand.finger_states
    if not fs:
        return False
    return all(
        fs.get(k) is not None and fs[k].value == "folded"
        for k in ("index", "middle", "ring", "pinky")
    )


def is_open_palm(hand: HandData) -> bool:
    """All five fingers extended."""
    fs = hand.finger_states
    if not fs:
        return False
    return all(
        fs.get(k) is not None and fs[k].value == "extended"
        for k in ("thumb", "index", "middle", "ring", "pinky")
    )


def is_fist(hand: HandData) -> bool:
    """All fingers folded + thumb folded (different from grab which allows thumb out)."""
    fs = hand.finger_states
    if not fs:
        return False
    return all(
        fs.get(k) is not None and fs[k].value == "folded"
        for k in ("thumb", "index", "middle", "ring", "pinky")
    )


def is_peace_sign(hand: HandData) -> bool:
    fs = hand.finger_states
    if not fs:
        return False
    return (
        fs.get("index") is not None and fs["index"].value == "extended"
        and fs.get("middle") is not None and fs["middle"].value == "extended"
        and fs.get("ring") is not None and fs["ring"].value == "folded"
        and fs.get("pinky") is not None and fs["pinky"].value == "folded"
    )


def is_thumbs_up(hand: HandData) -> bool:
    """Thumb extended, all other fingers folded, thumb pointing up/away."""
    fs = hand.finger_states
    if not fs:
        return False
    thumb_ext = fs.get("thumb") is not None and fs["thumb"].value == "extended"
    folded_others = all(
        fs.get(k) is not None and fs[k].value == "folded"
        for k in ("index", "middle", "ring", "pinky")
    )
    if not (thumb_ext and folded_others):
        return False

    # Geometry guard: the thumb must stick out clearly past the folded fingers
    # so a simple grab (thumb resting against the fingers) is not confused.
    t = hand.thumb_tip
    m = hand.middle_finger_tip
    w = hand.wrist
    if t is None or m is None or w is None:
        return True  # fall back to finger states only
    return vec_distance(t, w) > vec_distance(m, w)


# ---------------------------------------------------------------------------
# Swipe detection using velocity history
# ---------------------------------------------------------------------------

@dataclass
class _SwipeState:
    positions: list[tuple[float, float, float]] = field(default_factory=list)  # (t, x, y)
    cooldown: float = 0.0


class SwipeDetector:
    """Track index fingertip over time and detect directional swipes."""

    def __init__(
        self,
        max_age_s: float = 0.5,
        min_distance: float = 0.08,
        cooldown_s: float = 0.6,
    ) -> None:
        self.max_age = max_age_s
        self.min_distance = min_distance
        self.cooldown_s = cooldown_s
        self._state = _SwipeState()
        self._last_result: GestureType | None = None

    def update(self, hand: HandData, now: float) -> Optional[GestureType]:
        tip = hand.index_finger_tip
        if tip is None:
            self._state.positions.clear()
            return None

        self._state.positions.append((now, tip[0], tip[1]))

        # Prune old
        self._state.positions = [
            p for p in self._state.positions if now - p[0] < self.max_age
        ]

        if len(self._state.positions) < 3:
            return None

        if now < self._state.cooldown:
            return None

        first = self._state.positions[0]
        last = self._state.positions[-1]
        dx = last[1] - first[1]
        dy = last[2] - first[2]
        dist = (dx ** 2 + dy ** 2) ** 0.5

        if dist < self.min_distance:
            return None

        # Determine dominant axis
        if abs(dx) > abs(dy):
            gesture = GestureType.SWIPE_RIGHT if dx > 0 else GestureType.SWIPE_LEFT
        else:
            gesture = GestureType.SWIPE_DOWN if dy > 0 else GestureType.SWIPE_UP

        self._state.cooldown = now + self.cooldown_s
        self._state.positions.clear()
        return gesture


# ---------------------------------------------------------------------------
# Two-finger distance (pinch-in / pinch-out for zoom)
# ---------------------------------------------------------------------------

class TwoFingerZoomDetector:
    def __init__(self, cooldown_s: float = 0.5) -> None:
        self.cooldown_s = cooldown_s
        self._prev_dist: Optional[float] = None
        self._cooldown: float = 0.0

    def update(self, hand: HandData, now: float) -> Optional[GestureType]:
        t = hand.thumb_tip
        i = hand.index_finger_tip
        if t is None or i is None:
            self._prev_dist = None
            return None

        dist = vec_distance(t, i)
        if self._prev_dist is None or now < self._cooldown:
            self._prev_dist = dist
            return None

        delta = dist - self._prev_dist
        self._prev_dist = dist

        threshold = 0.03
        if abs(delta) > threshold:
            self._cooldown = now + self.cooldown_s
            return GestureType.TWO_FINGER_PINCH_OUT if delta > 0 else GestureType.TWO_FINGER_PINCH_IN
        return None


@dataclass
class _WaveState:
    positions: list[tuple[float, float]] = field(default_factory=list)  # (t, x)


class WaveDetector:
    """Detect a waving hand (rapid horizontal oscillation of the palm/ fingertip)."""

    def __init__(
        self,
        window_s: float = 0.8,
        min_reversals: int = 3,
        min_span: float = 0.12,
        step_threshold: float = 0.01,
        cooldown_s: float = 1.5,
    ) -> None:
        self.window_s = window_s
        self.min_reversals = min_reversals
        self.min_span = min_span
        self.step_threshold = step_threshold
        self.cooldown_s = cooldown_s
        self._state = _WaveState()
        self._cooldown: float = 0.0

    def update(self, hand: HandData, now: float) -> Optional[GestureType]:
        if now < self._cooldown:
            return None

        anchor = hand.palm_center if hand.palm_center is not None else hand.index_finger_tip
        if anchor is None:
            self._state.positions.clear()
            return None

        self._state.positions.append((now, anchor[0]))
        self._state.positions = [
            p for p in self._state.positions if now - p[0] < self.window_s
        ]

        if len(self._state.positions) < 6:
            return None

        # Sign of the horizontal movement between consecutive samples.
        signs: list[int] = []
        for a, b in zip(self._state.positions[:-1], self._state.positions[1:]):
            dx = b[1] - a[1]
            if abs(dx) > self.step_threshold:
                signs.append(1 if dx > 0 else -1)

        reversals = sum(
            1 for a, b in zip(signs[:-1], signs[1:]) if a != b
        )
        xs = [p[1] for p in self._state.positions]
        span = max(xs) - min(xs)

        if reversals >= self.min_reversals and span >= self.min_span:
            self._state.positions.clear()
            self._cooldown = now + self.cooldown_s
            return GestureType.WAVE
        return None