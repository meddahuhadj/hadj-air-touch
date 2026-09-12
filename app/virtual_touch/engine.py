"""Virtual touch engine – state machine.

IDLE -> POINTING -> APPROACHING -> VIRTUAL_TOUCH -> HOLDING -> DRAGGING -> RELEASE -> IDLE
"""
from __future__ import annotations

import enum
import logging
import time

from app.tracking.models import HandData
from app.virtual_touch.smoothing import ExponentialSmoothingFilter

_LOG = logging.getLogger(__name__)


class TouchState(enum.Enum):
    IDLE = "idle"
    POINTING = "pointing"
    APPROACHING = "approaching"
    VIRTUAL_TOUCH = "virtual_touch"
    HOLDING = "holding"
    DRAGGING = "dragging"
    RELEASING = "releasing"


class VirtualTouchEngine:
    """Finite state machine governing virtual touch interactions.

    The caller provides per-frame cues (touching, finger_on_screen, elapsed_ms)
    and the engine returns the current state + actions.
    """

    def __init__(
        self,
        touch_threshold_ms: float = 200.0,
        hold_threshold_ms: float = 400.0,
        release_threshold_ms: float = 150.0,
        move_drag_threshold: float = 0.01,
    ) -> None:
        self.state = TouchState.IDLE
        self._touch_threshold = touch_threshold_ms
        self._hold_threshold = hold_threshold_ms
        self._release_threshold = release_threshold_ms
        self._move_drag_threshold = move_drag_threshold

        self._state_enter_time: float = 0.0
        self._touch_start: float = 0.0
        self._drag_start_pos: tuple[float, float] | None = None
        self._virtual_clock_ms: float = 0.0
        self._accumulated_ms: float = 0.0

        # Fingertip depth heuristic state
        self._touch_depth_threshold: float = 0.015
        self._is_touching: bool = False

        # Actions emitted per frame
        self.action: str | None = None   # "tap", "long_press", "drag_start", "drag_end", etc.
        self.drag_delta: tuple[float, float] | None = None

        # Tracking smoothed position
        self._filter = ExponentialSmoothingFilter(alpha=0.5)
        self.smoothed_position: tuple[float, float] | None = None

    def update(
        self,
        touching: bool,
        finger_on_screen: bool,
        elapsed_ms: float,
        position: tuple[float, float] | None = None,
    ) -> TouchState:
        """Advance the state machine. Returns the new state.

        ``elapsed_ms`` is the wall-clock time since the previous call.
        Internally the engine tracks a virtual clock for deterministic behaviour.
        """
        self.action = None
        self.drag_delta = None

        if position is not None:
            self.smoothed_position = self._filter.process(position)

        self._accumulated_ms += elapsed_ms
        now_ms = self._accumulated_ms
        time_in_state = now_ms - self._state_enter_time

        if self.state == TouchState.IDLE:
            if finger_on_screen:
                self._transition(TouchState.POINTING, now_ms)

        elif self.state == TouchState.POINTING:
            if not finger_on_screen:
                self._transition(TouchState.IDLE, now_ms)
            elif touching:
                self._touch_start = now_ms
                self._transition(TouchState.APPROACHING, now_ms)

        elif self.state == TouchState.APPROACHING:
            if not touching:
                self._transition(TouchState.POINTING, now_ms)
            elif time_in_state > self._touch_threshold:
                self.action = "tap"
                self._transition(TouchState.VIRTUAL_TOUCH, now_ms)

        elif self.state == TouchState.VIRTUAL_TOUCH:
            if not touching:
                self._transition(TouchState.RELEASING, now_ms)
            elif time_in_state > self._hold_threshold:
                self.action = "long_press"
                self._transition(TouchState.HOLDING, now_ms)

        elif self.state == TouchState.HOLDING:
            if not touching:
                self.action = "long_press_end"
                self._transition(TouchState.RELEASING, now_ms)
            elif self._check_drag_start(position):
                self._transition(TouchState.DRAGGING, now_ms)

        elif self.state == TouchState.DRAGGING:
            if not touching:
                self.action = "drag_end"
                self._transition(TouchState.RELEASING, now_ms)
            elif position and self._drag_start_pos:
                self.drag_delta = (
                    position[0] - self._drag_start_pos[0],
                    position[1] - self._drag_start_pos[1],
                )

        elif self.state == TouchState.RELEASING:
            if time_in_state > self._release_threshold:
                self._transition(TouchState.IDLE, now_ms)

        return self.state

    def _transition(self, new_state: TouchState, now_ms: float) -> None:
        if new_state == TouchState.DRAGGING:
            self.action = "drag_start"
        self.state = new_state
        self._state_enter_time = now_ms

    def _check_drag_start(self, position: tuple[float, float] | None) -> bool:
        if position is None or self.smoothed_position is None:
            return False
        dx = position[0] - self.smoothed_position[0]
        dy = position[1] - self.smoothed_position[1]
        if (dx * dx + dy * dy) ** 0.5 > self._move_drag_threshold:
            self._drag_start_pos = position
            return True
        return False

    def reset(self) -> None:
        self._transition(TouchState.IDLE, self._accumulated_ms)
        self._filter.reset()
        self.smoothed_position = None
        self._is_touching = False

    # -- depth-based virtual touch detection --

    def is_virtual_touch(self, hand: HandData) -> bool:
        """Estimate whether the index fingertip has reached the virtual touch
        plane.

        Uses MediaPipe pseudo-depth (z-coordinate): the fingertip is 'touching'
        when it is significantly closer to the camera than the index MCP joint
        with the finger extended. Robust to small hand movements because the
        threshold is relative.
        """
        if not hand.landmarks:
            return False
        from app.tracking.models import INDEX_TIP, INDEX_MCP

        def _get(idx: int):
            if idx >= len(hand.landmarks):
                return None
            lm = hand.landmarks[idx]
            if lm.visibility < 0.3:
                return None
            return lm

        mcp = _get(INDEX_MCP)
        tip = _get(INDEX_TIP)
        if mcp is None or tip is None:
            return False

        # Finger should be extended (tip further in y from wrist than MCP).
        # We use z: more negative = closer to camera in MediaPipe.
        delta_z = tip.z - mcp.z
        self._is_touching = delta_z < -self._touch_depth_threshold
        return self._is_touching

    @property
    def is_virtual_touch_active(self) -> bool:
        """True when the interaction is in an active touch/drag state."""
        return self.state in (TouchState.VIRTUAL_TOUCH, TouchState.HOLDING, TouchState.DRAGGING)

    def set_depth_threshold(self, value: float) -> None:
        self._touch_depth_threshold = value

    def apply_settings(self, *, touch_depth_cm: float = 3.0, sensitivity: float = 1.0) -> None:
        """Map the user-facing depth (cm) + sensitivity to MediaPipe pseudo-depth.

        MediaPipe's z is normalised by hand scale; a finger reaching ~3 cm
        further from the MCP than the plane base corresponds roughly to a
        delta of 0.015. Higher sensitivity lowers the threshold (easier touch).
        """
        base = max(0.001, float(touch_depth_cm) * 0.005)
        sens = max(0.1, float(sensitivity))
        self._touch_depth_threshold = base / sens