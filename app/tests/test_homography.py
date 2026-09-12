"""Tests for homography (DLT) and perspective transform."""
from __future__ import annotations

import math
import unittest

from app.calibration.homography import (
    Mat3,
    apply_homography,
    inverse_homography,
    solve_homography,
    _mat3_apply,
    _mat3_identity,
    _mat3_mul,
)


class TestMat3Helpers(unittest.TestCase):
    def test_identity(self):
        I = _mat3_identity()
        pt = (3.0, 5.0)
        r = _mat3_apply(I, pt)
        self.assertAlmostEqual(r[0], 3.0, places=6)
        self.assertAlmostEqual(r[1], 5.0, places=6)

    def test_mul_identity(self):
        I = _mat3_identity()
        A = [[2, 0, 1], [0, 3, 4], [0, 0, 1]]
        R = _mat3_mul(A, I)
        self.assertEqual(R, A)

    def test_apply_translation(self):
        T = [[1, 0, 10], [0, 1, 20], [0, 0, 1]]
        r = _mat3_apply(T, (5.0, 5.0))
        self.assertAlmostEqual(r[0], 15.0)
        self.assertAlmostEqual(r[1], 25.0)

    def test_apply_scale(self):
        S = [[2, 0, 0], [0, 3, 0], [0, 0, 1]]
        r = _mat3_apply(S, (5.0, 5.0))
        self.assertAlmostEqual(r[0], 10.0)
        self.assertAlmostEqual(r[1], 15.0)


class TestHomography(unittest.TestCase):
    def test_identity_homography(self):
        pts = [(0, 0), (100, 0), (100, 100), (0, 100)]
        H = solve_homography(pts, pts)
        for pt in pts:
            mapped = apply_homography(H, pt)
            self.assertAlmostEqual(mapped[0], pt[0], delta=2.0)
            self.assertAlmostEqual(mapped[1], pt[1], delta=2.0)

    def test_scale_transform(self):
        src = [(0, 0), (100, 0), (100, 100), (0, 100)]
        dst = [(0, 0), (200, 0), (200, 200), (0, 200)]
        H = solve_homography(src, dst)
        # Center should map to center
        center = apply_homography(H, (50, 50))
        self.assertAlmostEqual(center[0], 100, delta=5)
        self.assertAlmostEqual(center[1], 100, delta=5)

    def test_translate_transform(self):
        src = [(0, 0), (100, 0), (100, 100), (0, 100)]
        dst = [(50, 50), (150, 50), (150, 150), (50, 150)]
        H = solve_homography(src, dst)
        mapped = apply_homography(H, (0, 0))
        self.assertAlmostEqual(mapped[0], 50, delta=5)
        self.assertAlmostEqual(mapped[1], 50, delta=5)

    def test_camera_to_screen_typical(self):
        """Simulate a camera seeing a monitor at perspective."""
        cam_pts = [(0.2, 0.2), (0.8, 0.2), (0.8, 0.8), (0.2, 0.8)]
        scr_pts = [(0, 0), (1920, 0), (1920, 1080), (0, 1080)]
        H = solve_homography(cam_pts, scr_pts)
        # Center
        c = apply_homography(H, (0.5, 0.5))
        self.assertAlmostEqual(c[0], 960, delta=20)
        self.assertAlmostEqual(c[1], 540, delta=20)
        # Top-left
        tl = apply_homography(H, (0.2, 0.2))
        self.assertAlmostEqual(tl[0], 0, delta=20)
        self.assertAlmostEqual(tl[1], 0, delta=20)

    def test_roundtrip_with_inverse(self):
        src = [(0.1, 0.1), (0.9, 0.1), (0.9, 0.9), (0.1, 0.9)]
        dst = [(0, 0), (1920, 0), (1920, 1080), (0, 1080)]
        H = solve_homography(src, dst)
        Hinv = inverse_homography(H)
        # Round-trip
        for pt in src:
            mid = apply_homography(H, pt)
            back = apply_homography(Hinv, mid)
            self.assertAlmostEqual(back[0], pt[0], delta=0.05)
            self.assertAlmostEqual(back[1], pt[1], delta=0.05)

    def test_too_few_points_raises(self):
        with self.assertRaises(ValueError):
            solve_homography([(0, 0), (1, 1)], [(0, 0), (1, 1)])

    def test_inverse_singular_raises(self):
        H_singular = [[1, 0, 0], [2, 0, 0], [3, 0, 0]]
        with self.assertRaises(ValueError):
            inverse_homography(H_singular)


if __name__ == "__main__":
    unittest.main()