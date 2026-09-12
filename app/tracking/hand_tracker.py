"""MediaPipe-based hand tracker.

This module imports mediapipe lazily so the application can still load
(with reduced functionality) if mediapipe is not installed.
"""
from __future__ import annotations

import logging
import time
from typing import Any, Optional

from app.tracking.models import (
    HandData,
    Landmark2D,
    NUM_LANDMARKS,
    INDEX_TIP,
    THUMB_TIP,
    INDEX_PIP,
    THUMB_IP,
    INDEX_MCP,
    THUMB_MCP,
    MIDDLE_TIP,
    RING_TIP,
    PINKY_TIP,
    FingerState,
)

_LOG = logging.getLogger(__name__)


def _compute_finger_states(landmarks: list[Landmark2D]) -> dict[str, FingerState]:
    """Determine whether each finger is extended or folded.

    Heuristic: a finger is extended if its TIP is farther from the wrist
    than its PIP joint (in Y only for simplicity with normalised coords).
    """
    wrist = landmarks[0] if landmarks else None
    if wrist is None:
        return {}

    def _state(pip_idx: int, tip_idx: int) -> FingerState:
        if pip_idx >= len(landmarks) or tip_idx >= len(landmarks):
            return FingerState.UNKNOWN
        pip = landmarks[pip_idx]
        tip = landmarks[tip_idx]
        return FingerState.EXTENDED if tip.y < pip.y else FingerState.FOLDED

    return {
        "thumb": _state(THUMB_MCP, THUMB_TIP),
        "index": _state(INDEX_PIP, INDEX_TIP),
        "middle": _state(9, MIDDLE_TIP),   # MIDDLE_PIP = 10, but MCP is close enough
        "ring": _state(13, RING_TIP),      # RING_PIP = 14
        "pinky": _state(17, PINKY_TIP),    # PINKY_PIP = 18
    }


class HandTracker:
    """Wrapper around MediaPipe Hands.

    If mediapipe is not installed, ``process_frame`` returns ``None`` and
    logs an error once.
    """

    def __init__(
        self,
        max_hands: int = 1,
        min_detection_confidence: float = 0.7,
        min_tracking_confidence: float = 0.6,
        static_mode: bool = False,
    ) -> None:
        self._mp_hands: Any = None
        self._hands: Any = None
        self._capable = False
        self._logged = False
        self._static_mode = static_mode
        self._max_hands = max_hands
        self._min_det = min_detection_confidence
        self._min_track = min_tracking_confidence
        self._init_mediapipe()

    def _init_mediapipe(self) -> None:
        try:
            import mediapipe as mp  # noqa: PLC0415
            self._mp_hands = mp.solutions.hands
            self._hands = self._mp_hands.Hands(
                static_image_mode=self._static_mode,
                max_num_hands=self._max_hands,
                min_detection_confidence=self._min_det,
                min_tracking_confidence=self._min_track,
            )
            self._capable = True
            _LOG.info("MediaPipe Hands initialised")
        except ImportError:
            if not self._logged:
                _LOG.warning("mediapipe not installed – tracking disabled")
                self._logged = True

    @property
    def available(self) -> bool:
        return self._capable

    def process_frame(self, frame: Any) -> Optional[HandData]:
        """Process a single BGR frame (numpy ndarray from OpenCV) and return
        the best hand or None.
        """
        if not self._capable or self._hands is None:
            return None

        try:
            import cv2
            rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        except Exception:
            rgb = frame  # assume already RGB

        results = self._hands.process(rgb)
        if not results.multi_hand_landmarks:
            return None

        best_hand = results.multi_hand_landmarks[0]
        handedness = "Right"
        hand_confidence = 0.9
        if results.multi_handedness and results.multi_handedness[0]:
            classification = results.multi_handedness[0].classification[0]
            handedness = classification.label
            hand_confidence = getattr(classification, "score", hand_confidence)

        landmarks: list[Landmark2D] = []
        for i, lm in enumerate(best_hand.landmark):
            vis = getattr(lm, "visibility", 0.5)
            landmarks.append(Landmark2D(
                index=i,
                x=lm.x,
                y=lm.y,
                z=lm.z,
                visibility=vis,
            ))

        finger_states = _compute_finger_states(landmarks)

        return HandData(
            landmarks=landmarks,
            handedness=handedness,
            confidence=hand_confidence,
            timestamp=time.perf_counter(),
            finger_states=finger_states,
        )

    def close(self) -> None:
        if self._hands:
            self._hands.close()
            self._hands = None