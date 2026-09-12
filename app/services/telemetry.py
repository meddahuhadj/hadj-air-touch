"""FPS counter, latency estimator, quality metrics."""
from __future__ import annotations

import collections
import time


class Telemetry:
    def __init__(self, window_size: int = 60) -> None:
        self._timestamps: collections.deque[float] = collections.deque(maxlen=window_size)
        self._latencies: collections.deque[float] = collections.deque(maxlen=window_size)
        self.fps: float = 0.0
        self.latency_ms: float = 0.0

    def update_frame(self, timestamp: float) -> None:
        self._timestamps.append(timestamp)
        if len(self._timestamps) >= 2:
            dt = self._timestamps[-1] - self._timestamps[-2]
            self.latency_ms = dt * 1000
            self._latencies.append(self.latency_ms)
            window = self._timestamps[-1] - self._timestamps[0]
            if window > 0:
                self.fps = (len(self._timestamps) - 1) / window

    @property
    def avg_latency_ms(self) -> float:
        return sum(self._latencies) / len(self._latencies) if self._latencies else 0.0