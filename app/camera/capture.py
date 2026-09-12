"""Thread-safe camera capture with simulation fallback."""
from __future__ import annotations

import logging
import math
import threading
import time
from typing import Any, Optional

_LOG = logging.getLogger(__name__)


class CameraCapture:
    """Runs a capture loop in a background thread.

    If OpenCV is not available, generates synthetic frames for testing.
    """

    def __init__(
        self,
        camera_index: int = 0,
        width: int = 1280,
        height: int = 720,
        fps: int = 30,
        mirror: bool = True,
    ) -> None:
        self._index = camera_index
        self._width = width
        self._height = height
        self._fps = fps
        self._mirror = mirror
        self._running = False
        self._thread: threading.Thread | None = None
        self._frame: Any = None
        self._frame_time: float = 0.0
        self._lock = threading.Lock()
        self._cap: Any = None
        self._simulation = False

    def open(self) -> bool:
        if self._cap is not None or self._running:
            # Already opened/running - avoid grabbing a second handle on the
            # same physical camera, which corrupts frames on most Windows
            # backends (MSMF/DSHOW) and crashes the capture thread.
            return True
        try:
            import cv2
            self._cap = cv2.VideoCapture(self._index)
            if not self._cap.isOpened():
                raise RuntimeError("Camera not opened")
            self._cap.set(cv2.CAP_PROP_FRAME_WIDTH, self._width)
            self._cap.set(cv2.CAP_PROP_FRAME_HEIGHT, self._height)
            self._cap.set(cv2.CAP_PROP_FPS, self._fps)
            _LOG.info("Camera %d opened (%dx%d @ %d fps)",
                       self._index, self._width, self._height, self._fps)
            return True
        except Exception as exc:
            _LOG.warning("OpenCV camera failed (%s) – using simulation", exc)
            self._simulation = True
            return True

    def start(self) -> None:
        if self._running:
            return
        self._running = True
        self._thread = threading.Thread(target=self._loop, daemon=True, name="camera")
        self._thread.start()

    def stop(self) -> None:
        self._running = False
        if self._thread:
            self._thread.join(timeout=2.0)
        if self._cap:
            self._cap.release()
            self._cap = None

    def grab(self) -> Any:
        """Return the latest frame or None."""
        with self._lock:
            return self._frame

    def set_mirror(self, mirror: bool) -> None:
        """Toggle horizontal mirroring at runtime (thread-safe)."""
        with self._lock:
            self._mirror = bool(mirror)

    @property
    def frame_time(self) -> float:
        return self._frame_time

    @property
    def is_running(self) -> bool:
        return self._running

    @property
    def is_simulation(self) -> bool:
        return self._simulation

    def _loop(self) -> None:
        if self._simulation:
            self._simulation_loop()
        else:
            self._opencv_loop()

    def _opencv_loop(self) -> None:
        import cv2
        interval = 1.0 / max(self._fps, 1)
        while self._running:
            try:
                ret, frame = self._cap.read()
            except cv2.error as exc:
                # Transient driver hiccup (e.g. another process briefly
                # contending for the same camera index) - keep the thread
                # alive instead of dying silently and freezing the preview.
                _LOG.warning("Camera read error (%s); retrying", exc)
                time.sleep(0.1)
                continue
            if not ret:
                time.sleep(0.01)
                continue
            if self._mirror:
                frame = cv2.flip(frame, 1)
            with self._lock:
                self._frame = frame
                self._frame_time = time.perf_counter()
            time.sleep(interval * 0.5)

    def _simulation_loop(self) -> None:
        """Generate a synthetic 640x480 black frame with a moving dot."""
        import numpy as np
        interval = 1.0 / max(self._fps, 1)
        t = 0.0
        while self._running:
            h, w = 480, 640
            frame = np.zeros((h, w, 3), dtype=np.uint8)
            cx = int(w * (0.5 + 0.4 * math.sin(t * 1.5)))
            cy = int(h * (0.5 + 0.3 * math.sin(t * 2.1)))
            y, x = np.ogrid[:h, :w]
            mask = (x - cx) ** 2 + (y - cy) ** 2 < 900
            frame[mask] = [100, 200, 255]

            with self._lock:
                self._frame = frame
                self._frame_time = time.perf_counter()
            t += interval
            time.sleep(interval)