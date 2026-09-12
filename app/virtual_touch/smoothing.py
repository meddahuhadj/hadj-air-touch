"""Numpy-free smoothing filters."""
from __future__ import annotations

import math
from typing import Sequence

from app.utils.vectors import Tup2, vec_lerp


class ExponentialSmoothingFilter:
    """Exponential moving average on 2D points."""

    def __init__(self, alpha: float = 0.5) -> None:
        self._alpha = alpha
        self._prev: Tup2 | None = None

    def process(self, point: Tup2) -> Tup2:
        if self._prev is None:
            self._prev = point
            return point
        smoothed = vec_lerp(self._prev, point, self._alpha)
        self._prev = smoothed
        return smoothed

    def reset(self) -> None:
        self._prev = None


class OneEuroFilter:
    """One Euro filter for low-latency jitter reduction.

    Ref: https://hal.inria.fr/hal-00670496/document
    """

    def __init__(
        self,
        min_cutoff: float = 1.0,
        beta: float = 0.007,
        d_cutoff: float = 1.0,
    ) -> None:
        self.min_cutoff = min_cutoff
        self.beta = beta
        self.d_cutoff = d_cutoff
        self._x_prev: Tup2 | None = None
        self._dx_prev: Tup2 | None = None
        self._t_prev: float | None = None

    def _alpha(self, cutoff: float, dt: float) -> float:
        tau = 1.0 / (2 * math.pi * cutoff)
        return 1.0 / (1.0 + tau / dt) if dt > 0 else 1.0

    def process(self, point: Tup2, t: float | None = None) -> Tup2:
        if t is None:
            import time
            t = time.perf_counter()

        if self._t_prev is None:
            self._x_prev = point
            self._dx_prev = (0.0, 0.0)
            self._t_prev = t
            return point

        dt = t - self._t_prev
        if dt <= 0:
            return self._x_prev  # type: ignore[return-value]

        dx = ((point[0] - self._x_prev[0]) / dt, (point[1] - self._x_prev[1]) / dt)
        alpha_d = self._alpha(self.d_cutoff, dt)
        dx_hat = (
            alpha_d * dx[0] + (1 - alpha_d) * self._dx_prev[0],
            alpha_d * dx[1] + (1 - alpha_d) * self._dx_prev[1],
        )

        speed = math.hypot(dx_hat[0], dx_hat[1])
        cutoff = self.min_cutoff + self.beta * speed
        alpha = self._alpha(cutoff, dt)

        x_hat = (
            alpha * point[0] + (1 - alpha) * self._x_prev[0],
            alpha * point[1] + (1 - alpha) * self._x_prev[1],
        )

        self._x_prev = x_hat
        self._dx_prev = dx_hat
        self._t_prev = t
        return x_hat

    def reset(self) -> None:
        self._x_prev = self._dx_prev = self._t_prev = None