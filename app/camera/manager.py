"""Camera enumeration, selection, and configuration."""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Optional

_LOG = logging.getLogger(__name__)


@dataclass
class CameraDevice:
    index: int
    name: str
    width: int = 1280
    height: int = 720
    fps: int = 30
    available: bool = True


class CameraManager:
    """Detect and manage available webcams.

    Uses OpenCV's cv2.VideoCapture when available; falls back to a
    stub list if OpenCV is missing (headless/self-test mode).
    """

    def __init__(self) -> None:
        self._cameras: list[CameraDevice] = []
        self._scan()

    def _scan(self) -> None:
        self._cameras.clear()
        try:
            import cv2
        except ImportError:
            _LOG.warning("OpenCV not installed – camera enumeration unavailable")
            self._cameras = [CameraDevice(index=0, name="Simulation")]
            return

        # Try up to 10 indices
        for i in range(10):
            cap = cv2.VideoCapture(i)
            if cap.isOpened():
                w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
                h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
                fps = int(cap.get(cv2.CAP_PROP_FPS))
                self._cameras.append(CameraDevice(
                    index=i,
                    name=f"Camera {i}",
                    width=w or 640,
                    height=h or 480,
                    fps=fps or 30,
                ))
                cap.release()
            else:
                break

        if not self._cameras:
            self._cameras = [CameraDevice(index=0, name="Simulation")]

        _LOG.info("Found %d camera(s)", len(self._cameras))

    @property
    def cameras(self) -> list[CameraDevice]:
        return list(self._cameras)

    def get_camera(self, index: int) -> Optional[CameraDevice]:
        for c in self._cameras:
            if c.index == index:
                return c
        return self._cameras[0] if self._cameras else None

    def refresh(self) -> None:
        self._scan()