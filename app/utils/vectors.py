"""Pure-Python 2D/3D vector helpers.

Numpy is available when installed but this module provides a lightweight
fallback so that calibration math can run and be tested without numpy.
"""
from __future__ import annotations

import math
from typing import Sequence

Tup2 = tuple[float, float]
Tup3 = tuple[float, float, float]

# ---------------------------------------------------------------------------
# Numpy-accelerated path (optional)
# ---------------------------------------------------------------------------
try:
    import numpy as _np
    HAS_NUMPY = True
except ImportError:
    _np = None  # type: ignore[assignment]
    HAS_NUMPY = False


def vec2(x: float, y: float) -> Tup2:
    return (x, y)


def vec_add(a: Tup2, b: Tup2) -> Tup2:
    return (a[0] + b[0], a[1] + b[1])


def vec_sub(a: Tup2, b: Tup2) -> Tup2:
    return (a[0] - b[0], a[1] - b[1])


def vec_scale(a: Tup2, s: float) -> Tup2:
    return (a[0] * s, a[1] * s)


def vec_length(a: Tup2) -> float:
    return math.hypot(a[0], a[1])


def vec_norm(a: Tup2) -> Tup2:
    L = vec_length(a)
    if L < 1e-12:
        return (0.0, 0.0)
    return (a[0] / L, a[1] / L)


def vec_dot(a: Tup2, b: Tup2) -> float:
    return a[0] * b[0] + a[1] * b[1]


def vec_cross(a: Tup2, b: Tup2) -> float:
    return a[0] * b[1] - a[1] * b[0]


def vec_lerp(a: Tup2, b: Tup2, t: float) -> Tup2:
    return (a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t)


def vec_distance(a: Tup2, b: Tup2) -> float:
    return vec_length(vec_sub(a, b))


def vec_angle(a: Tup2, b: Tup2) -> float:
    """Unsigned angle in radians between two 2D vectors."""
    cross = vec_cross(a, b)
    dot = vec_dot(a, b)
    return abs(math.atan2(cross, dot))


def vec3(x: float, y: float, z: float) -> Tup3:
    return (x, y, z)


def vec3_distance(a: Tup3, b: Tup3) -> float:
    return math.sqrt((a[0]-b[0])**2 + (a[1]-b[1])**2 + (a[2]-b[2])**2)