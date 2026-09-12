"""Tests for smoothing filters."""
from __future__ import annotations

import unittest

from app.virtual_touch.smoothing import ExponentialSmoothingFilter, OneEuroFilter


class TestExponentialSmoothing(unittest.TestCase):
    def test_first_sample_passes_through(self):
        f = ExponentialSmoothingFilter(alpha=0.5)
        r = f.process((10.0, 20.0))
        self.assertEqual(r, (10.0, 20.0))

    def test_smoothing(self):
        f = ExponentialSmoothingFilter(alpha=0.5)
        f.process((0.0, 0.0))
        r = f.process((10.0, 10.0))
        self.assertAlmostEqual(r[0], 5.0)
        self.assertAlmostEqual(r[1], 5.0)

    def test_convergence(self):
        f = ExponentialSmoothingFilter(alpha=0.9)
        pt = (100.0, 100.0)
        for _ in range(50):
            r = f.process(pt)
        self.assertAlmostEqual(r[0], 100.0, places=1)
        self.assertAlmostEqual(r[1], 100.0, places=1)

    def test_alpha_one_is_passthrough(self):
        f = ExponentialSmoothingFilter(alpha=1.0)
        f.process((0.0, 0.0))
        r = f.process((42.0, 99.0))
        self.assertAlmostEqual(r[0], 42.0)
        self.assertAlmostEqual(r[1], 99.0)

    def test_reset(self):
        f = ExponentialSmoothingFilter()
        f.process((10.0, 10.0))
        f.reset()
        r = f.process((50.0, 50.0))
        self.assertEqual(r, (50.0, 50.0))


class TestOneEuroFilter(unittest.TestCase):
    def test_first_sample(self):
        f = OneEuroFilter()
        r = f.process((100.0, 200.0), t=0.0)
        self.assertEqual(r, (100.0, 200.0))

    def test_smoothing_effect(self):
        f = OneEuroFilter(min_cutoff=1.0, beta=0.0)
        f.process((0.0, 0.0), t=0.0)
        r1 = f.process((100.0, 100.0), t=0.1)
        r2 = f.process((100.0, 100.0), t=0.2)
        # Should converge toward 100 but not jump immediately
        self.assertLess(r1[0], 100.0)
        self.assertGreater(r2[0], r1[0])

    def test_reset(self):
        f = OneEuroFilter()
        f.process((10.0, 10.0), t=0.0)
        f.reset()
        r = f.process((50.0, 50.0), t=1.0)
        self.assertEqual(r, (50.0, 50.0))


if __name__ == "__main__":
    unittest.main()