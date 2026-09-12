"""Virtual screen plane definition."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from app.calibration.homography import Mat3, solve_homography, apply_homography
from app.utils.vectors import Tup2


@dataclass
class ScreenPlane:
    """Defines the mapping between normalised camera coords and screen pixel coords."""
    width_px: int = 1920
    height_px: int = 1080
    homography: Optional[Mat3] = None
    inverse_homography: Optional[Mat3] = None

    def calibrate(self, camera_points: list[Tup2], screen_points: list[Tup2]) -> float:
        """Compute homography. Returns a quality score [0..1]."""
        if len(camera_points) < 4:
            return 0.0
        self.homography = solve_homography(camera_points, screen_points)
        from app.calibration.homography import inverse_homography
        try:
            self.inverse_homography = inverse_homography(self.homography)
        except Exception:
            self.inverse_homography = None
        return self._score(camera_points, screen_points)

    def camera_to_screen(self, point: Tup2) -> Optional[Tup2]:
        if self.homography is None:
            return None
        return apply_homography(self.homography, point)

    def screen_to_camera(self, point: Tup2) -> Optional[Tup2]:
        if self.inverse_homography is None:
            return None
        return apply_homography(self.inverse_homography, point)

    def _score(self, cam_pts: list[Tup2], scr_pts: list[Tup2]) -> float:
        """Reprojection error as a quality score [0..1] where 1 is perfect."""
        total_err = 0.0
        for cp, sp in zip(cam_pts, scr_pts):
            projected = self.camera_to_screen(cp)
            if projected is None:
                return 0.0
            dx = projected[0] - sp[0]
            dy = projected[1] - sp[1]
            total_err += (dx * dx + dy * dy) ** 0.5
        avg_err = total_err / len(cam_pts)
        # 10 px average error = 0 score, 0 px = 1
        return max(0.0, 1.0 - avg_err / 10.0)