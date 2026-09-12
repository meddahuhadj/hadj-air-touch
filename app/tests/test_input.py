"""Tests for vector math and screen input math (pure logic, no Win32)."""
from __future__ import annotations

import math
import unittest

from app.utils.vectors import (
    Tup2,
    vec2,
    vec_add,
    vec_sub,
    vec_scale,
    vec_length,
    vec_norm,
    vec_dot,
    vec_cross,
    vec_lerp,
    vec_distance,
    vec_angle,
    vec3,
    vec3_distance,
)


class TestVec2(unittest.TestCase):
    def test_add(self):
        self.assertEqual(vec_add((1, 2), (3, 4)), (4, 6))

    def test_sub(self):
        self.assertEqual(vec_sub((5, 3), (2, 1)), (3, 2))

    def test_scale(self):
        self.assertEqual(vec_scale((2, 3), 3), (6, 9))

    def test_length(self):
        self.assertAlmostEqual(vec_length((3, 4)), 5.0)

    def test_norm(self):
        n = vec_norm((3, 4))
        self.assertAlmostEqual(vec_length(n), 1.0)
        self.assertAlmostEqual(n[0], 0.6)
        self.assertAlmostEqual(n[1], 0.8)

    def test_norm_zero(self):
        n = vec_norm((0, 0))
        self.assertEqual(n, (0, 0))

    def test_dot(self):
        self.assertAlmostEqual(vec_dot((1, 0), (0, 1)), 0.0)
        self.assertAlmostEqual(vec_dot((2, 3), (4, 5)), 23.0)

    def test_cross(self):
        self.assertAlmostEqual(vec_cross((1, 0), (0, 1)), 1.0)
        self.assertAlmostEqual(vec_cross((0, 1), (1, 0)), -1.0)

    def test_lerp(self):
        r = vec_lerp((0, 0), (10, 10), 0.5)
        self.assertAlmostEqual(r[0], 5.0)
        self.assertAlmostEqual(r[1], 5.0)

    def test_lerp_endpoints(self):
        self.assertEqual(vec_lerp((0, 0), (10, 10), 0.0), (0, 0))
        r = vec_lerp((0, 0), (10, 10), 1.0)
        self.assertAlmostEqual(r[0], 10.0)
        self.assertAlmostEqual(r[1], 10.0)

    def test_distance(self):
        self.assertAlmostEqual(vec_distance((0, 0), (3, 4)), 5.0)

    def test_angle_parallel(self):
        a = vec_angle((1, 0), (1, 0))
        self.assertAlmostEqual(a, 0.0, places=6)

    def test_angle_perpendicular(self):
        a = vec_angle((1, 0), (0, 1))
        self.assertAlmostEqual(a, math.pi / 2, places=4)


class TestVec3(unittest.TestCase):
    def test_distance(self):
        d = vec3_distance((0, 0, 0), (1, 0, 0))
        self.assertAlmostEqual(d, 1.0)
        d2 = vec3_distance((0, 0, 0), (1, 1, 1))
        self.assertAlmostEqual(d2, math.sqrt(3))


if __name__ == "__main__":
    unittest.main()