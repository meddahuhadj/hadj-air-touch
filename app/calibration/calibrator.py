"""Calibration workflow and quality scoring."""
from __future__ import annotations

import enum
import logging
import time
from dataclasses import dataclass, field
from typing import Optional

from app.calibration.homography import Mat3, solve_homography, apply_homography
from app.virtual_touch.plane import ScreenPlane
from app.utils.vectors import Tup2

_LOG = logging.getLogger(__name__)


class CalibState(enum.Enum):
    IDLE = "idle"
    TOP_LEFT = "top_left"
    TOP_RIGHT = "top_right"
    BOTTOM_RIGHT = "bottom_right"
    BOTTOM_LEFT = "bottom_left"
    COMPUTING = "computing"
    DONE = "done"
    FAILED = "failed"


@dataclass
class CalibrationResult:
    success: bool = False
    quality: float = 0.0
    homography: Optional[Mat3] = None
    message: str = ""
    screen_points: list[Tup2] = field(default_factory=list)
    camera_points: list[Tup2] = field(default_factory=list)


# Corner labels
CORNERS = [
    ("top_left", (0, 0)),
    ("top_right", (1920, 0)),
    ("bottom_right", (1920, 1080)),
    ("bottom_left", (0, 1080)),
]


class Calibrator:
    """Guided 4-point calibration.

    For each corner the user points at it; we record the camera-space position.
    Then we compute a homography.
    """

    def __init__(self, screen_width: int = 1920, screen_height: int = 1080) -> None:
        self.screen_w = screen_width
        self.screen_h = screen_height
        self.state = CalibState.IDLE
        self._camera_points: list[Tup2] = []
        self._screen_points: list[Tup2] = [
            (0, 0), (screen_width, 0),
            (screen_width, screen_height), (0, screen_height),
        ]
        self._plane = ScreenPlane(width_px=screen_width, height_px=screen_height)
        self._hold_time_ms: float = 1000.0
        self._hold_start: float = 0.0
        self._result = CalibrationResult()
        self._step = 0

    @property
    def result(self) -> CalibrationResult:
        return self._result

    @property
    def plane(self) -> ScreenPlane:
        return self._plane

    @property
    def step(self) -> int:
        """Number of corner points recorded so far (0-4)."""
        return self._step

    @property
    def recorded_points(self) -> list[Tup2]:
        """Camera-space points recorded so far, in corner order."""
        return list(self._camera_points)

    def start(self) -> None:
        self._camera_points.clear()
        self._step = 0
        self.state = CalibState.TOP_LEFT
        self._hold_start = time.perf_counter()
        _LOG.info("Calibration started – point at TOP LEFT")

    def get_current_corner(self) -> tuple[str, Tup2]:
        """Return (corner_name, screen_position) for the current step."""
        name, pos = CORNERS[self._step % 4]
        return name, pos

    def feed_point(self, point: Tup2) -> bool:
        """Feed a stabilised camera-space point.  Returns True when the step is complete.

        The user must hold still for ~1 second.
        """
        if self.state in (CalibState.IDLE, CalibState.COMPUTING, CalibState.DONE, CalibState.FAILED):
            return False

        elapsed = time.perf_counter() - self._hold_start
        if elapsed < self._hold_time_ms / 1000.0:
            return False

        self._camera_points.append(point)
        _LOG.info("Corner %s recorded at camera (%.3f, %.3f)",
                   self.get_current_corner()[0], point[0], point[1])

        self._step += 1
        states = [CalibState.TOP_LEFT, CalibState.TOP_RIGHT, CalibState.BOTTOM_RIGHT, CalibState.BOTTOM_LEFT]
        if self._step < 4:
            self.state = states[self._step]
            self._hold_start = time.perf_counter()
        else:
            self.state = CalibState.COMPUTING
            self._compute()
        return True

    def feed_point_auto(self, point: Tup2) -> bool:
        """Auto mode: record immediately (no hold requirement)."""
        self._hold_time_ms = 0.0
        result = self.feed_point(point)
        self._hold_time_ms = 1000.0
        return result

    def skip_current(self) -> None:
        """Skip to next corner (records center as fallback)."""
        self._camera_points.append((0.5, 0.5))
        self._step += 1
        if self._step >= 4:
            self.state = CalibState.COMPUTING
            self._compute()
        else:
            states = [CalibState.TOP_LEFT, CalibState.TOP_RIGHT, CalibState.BOTTOM_RIGHT, CalibState.BOTTOM_LEFT]
            self.state = states[self._step]
            self._hold_start = time.perf_counter()

    def _compute(self) -> None:
        try:
            quality = self._plane.calibrate(self._camera_points, self._screen_points)
            self._result = CalibrationResult(
                success=quality > 0.5,
                quality=quality,
                homography=self._plane.homography,
                camera_points=list(self._camera_points),
                screen_points=list(self._screen_points),
                message="Calibration complete" if quality > 0.5 else "Low quality – try again",
            )
            self.state = CalibState.DONE if quality > 0.5 else CalibState.FAILED
        except Exception as exc:
            self._result = CalibrationResult(success=False, message=str(exc))
            self.state = CalibState.FAILED
            _LOG.exception("Calibration computation failed")

    def map_camera_to_screen(self, point: Tup2) -> Optional[Tup2]:
        return self._plane.camera_to_screen(point)

    # -- persistence --

    def serialize_result(self) -> Optional[dict]:
        """Return a JSON-friendly snapshot of a successful calibration, or None."""
        r = self._result
        if r.homography is None:
            return None
        return {
            "screen_w": self.screen_w,
            "screen_h": self.screen_h,
            "quality": r.quality,
            "success": r.success,
            "homography": [list(row) for row in r.homography],
            "camera_points": [list(p) for p in r.camera_points],
            "screen_points": [list(p) for p in r.screen_points],
        }

    def restore_result(self, data: Optional[dict]) -> bool:
        """Apply a saved calibration snapshot. Returns True on success."""
        if not data or data.get("homography") is None:
            return False
        try:
            homography = [
                [float(v) for v in row]
                for row in data["homography"]
            ]
            if len(homography) != 3 or any(len(row) != 3 for row in homography):
                return False
            # Only restore when the monitor size matches (same setup)
            if int(data.get("screen_w", -1)) != self.screen_w or int(data.get("screen_h", -1)) != self.screen_h:
                _LOG.info("Saved calibration ignored: screen size mismatch")
                return False

            self._camera_points = [
                (float(x), float(y)) for x, y in data.get("camera_points", [])
            ]
            self._screen_points = [
                (float(x), float(y)) for x, y in data.get("screen_points", [])
            ]
            self._plane.homography = homography
            try:
                from app.calibration.homography import inverse_homography  # noqa: PLC0415
                self._plane.inverse_homography = inverse_homography(homography)
            except Exception:
                self._plane.inverse_homography = None
            self._result = CalibrationResult(
                success=bool(data.get("success")),
                quality=float(data.get("quality", 0.0)),
                homography=homography,
                camera_points=list(self._camera_points),
                screen_points=list(self._screen_points),
                message="Restored saved calibration",
            )
            self.state = CalibState.DONE if self._result.success else CalibState.FAILED
            _LOG.info("Restored saved calibration (quality=%.2f)", self._result.quality)
            return True
        except (TypeError, ValueError) as exc:
            _LOG.warning("Could not restore saved calibration: %s", exc)
            return False

    def reset(self) -> None:
        self.state = CalibState.IDLE
        self._camera_points.clear()
        self._result = CalibrationResult()