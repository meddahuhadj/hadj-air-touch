"""Hand tracking data models (pure data, no deps)."""
from __future__ import annotations

import enum
from dataclasses import dataclass, field
from typing import Optional

from app.utils.vectors import Tup2, Tup3


# MediaPipe hand landmark indices (21 points)
WRIST = 0
THUMB_CMC, THUMB_MCP, THUMB_IP, THUMB_TIP = 1, 2, 3, 4
INDEX_MCP, INDEX_PIP, INDEX_DIP, INDEX_TIP = 5, 6, 7, 8
MIDDLE_MCP, MIDDLE_PIP, MIDDLE_DIP, MIDDLE_TIP = 9, 10, 11, 12
RING_MCP, RING_PIP, RING_DIP, RING_TIP = 13, 14, 15, 16
PINKY_MCP, PINKY_PIP, PINKY_DIP, PINKY_TIP = 17, 18, 19, 20

NUM_LANDMARKS = 21

# Pairs for skeleton drawing
SKELETON_CONNECTIONS: list[tuple[int, int]] = [
    (WRIST, THUMB_MCP), (THUMB_MCP, THUMB_IP), (THUMB_IP, THUMB_TIP),
    (WRIST, INDEX_MCP), (INDEX_MCP, INDEX_PIP), (INDEX_PIP, INDEX_TIP),
    (WRIST, MIDDLE_MCP), (MIDDLE_MCP, MIDDLE_PIP), (MIDDLE_PIP, MIDDLE_TIP),
    (WRIST, RING_MCP), (RING_MCP, RING_PIP), (RING_PIP, RING_TIP),
    (WRIST, PINKY_MCP), (PINKY_MCP, PINKY_PIP), (PINKY_PIP, PINKY_TIP),
    (INDEX_MCP, MIDDLE_MCP), (MIDDLE_MCP, RING_MCP), (RING_MCP, PINKY_MCP),
    (THUMB_MCP, INDEX_MCP),
]


class FingerState(enum.Enum):
    EXTENDED = "extended"
    FOLDED = "folded"
    UNKNOWN = "unknown"


@dataclass
class Landmark2D:
    index: int
    x: float
    y: float
    z: float = 0.0
    visibility: float = 0.0

    @property
    def pos2d(self) -> Tup2:
        return (self.x, self.y)

    @property
    def pos3d(self) -> Tup3:
        return (self.x, self.y, self.z)


@dataclass
class HandData:
    """Complete tracking data for one hand (one frame)."""
    landmarks: list[Landmark2D] = field(default_factory=list)
    handedness: str = "Right"
    confidence: float = 0.0
    timestamp: float = 0.0
    frame_index: int = 0

    # Precomputed convenience attributes
    finger_states: dict[str, FingerState] = field(default_factory=dict)

    @property
    def wrist(self) -> Optional[Tup2]:
        return self._pos(WRIST)

    @property
    def index_finger_tip(self) -> Optional[Tup2]:
        return self._pos(INDEX_TIP)

    @property
    def thumb_tip(self) -> Optional[Tup2]:
        return self._pos(THUMB_TIP)

    @property
    def middle_finger_tip(self) -> Optional[Tup2]:
        return self._pos(MIDDLE_TIP)

    @property
    def palm_center(self) -> Optional[Tup2]:
        """Approximate palm centre as average of MCP joints + wrist."""
        indices = [WRIST, INDEX_MCP, MIDDLE_MCP, RING_MCP, PINKY_MCP]
        pts = [self._pos(i) for i in indices]
        pts = [p for p in pts if p is not None]
        if not pts:
            return None
        return (
            sum(p[0] for p in pts) / len(pts),
            sum(p[1] for p in pts) / len(pts),
        )

    @property
    def index_finger_direction(self) -> Optional[Tup2]:
        """Direction vector from INDEX_MCP to INDEX_TIP."""
        mcp = self._pos(INDEX_MCP)
        tip = self._pos(INDEX_TIP)
        if mcp is None or tip is None:
            return None
        from app.utils.vectors import vec_sub, vec_norm
        return vec_norm(vec_sub(tip, mcp))

    @property
    def pinch_distance(self) -> Optional[float]:
        """Distance between thumb tip and index finger tip (normalised coords)."""
        from app.utils.vectors import vec_distance
        t = self.thumb_tip
        i = self.index_finger_tip
        if t is None or i is None:
            return None
        return vec_distance(t, i)

    def _pos(self, idx: int) -> Optional[Tup2]:
        # NOTE: `visibility` is not populated by MediaPipe's Hands solution
        # (unlike Pose) - it is always 0.0. Any landmark present in the list
        # was already returned by a confident MediaPipe detection, so it is
        # valid; gating on visibility here made every fingertip position
        # (and therefore cursor movement, pinch, etc.) permanently None.
        if idx < len(self.landmarks):
            return self.landmarks[idx].pos2d
        return None