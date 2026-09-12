"""Tests for calibration persistence (serialize / restore + config)."""
from __future__ import annotations

import unittest

from app.calibration.calibrator import Calibrator, CalibrationResult
from app.config import AppConfig, Settings


def _calibrate(c: Calibrator) -> None:
    pts = [(0.2, 0.2), (0.8, 0.2), (0.8, 0.8), (0.2, 0.8)]
    c.start()
    for pt in pts:
        c.feed_point_auto(pt)


class TestCalibratorSerialize(unittest.TestCase):
    def test_serialize_none_without_homography(self):
        c = Calibrator(1920, 1080)
        self.assertIsNone(c.serialize_result())

    def test_roundtrip(self):
        c = Calibrator(1920, 1080)
        _calibrate(c)
        self.assertTrue(c.result.success)
        snap = c.serialize_result()
        self.assertIsNotNone(snap)
        self.assertEqual(snap["screen_w"], 1920)
        self.assertEqual(len(snap["homography"]), 3)

        restored = Calibrator(1920, 1080)
        self.assertTrue(restored.restore_result(snap))
        self.assertIsNotNone(restored.result.homography)
        for pt in [(0.08, 0.12), (0.92, 0.10), (0.90, 0.90), (0.10, 0.88)]:
            a = c.map_camera_to_screen(pt)
            b = restored.map_camera_to_screen(pt)
            self.assertIsNotNone(a)
            self.assertAlmostEqual(a[0], b[0], places=6)
            self.assertAlmostEqual(a[1], b[1], places=6)

    def test_restore_rejects_screen_size_mismatch(self):
        c = Calibrator(1920, 1080)
        _calibrate(c)
        snap = c.serialize_result()
        other = Calibrator(2560, 1440)
        self.assertFalse(other.restore_result(snap))
        self.assertIsNone(other.result.homography)

    def test_restore_rejects_garbage(self):
        c = Calibrator(1920, 1080)
        self.assertFalse(c.restore_result(None))
        self.assertFalse(c.restore_result({}))
        self.assertFalse(c.restore_result({"homography": "nope"}))
        self.assertFalse(c.restore_result({"homography": [[1, 0, 0], [0, 1, 0]]}))

    def test_restore_good_team_persists_plane(self):
        c = Calibrator(1920, 1080)
        _calibrate(c)
        snap = c.serialize_result()
        restored = Calibrator(1920, 1080)
        restored.restore_result(snap)
        self.assertEqual(restored.state.value, "done")
        self.assertEqual(restored.result.message, "Restored saved calibration")


class TestCalibrationConfig(unittest.TestCase):
    def test_default_save_on(self):
        cfg = AppConfig()
        self.assertTrue(cfg.calibration.save_homography)
        self.assertIsNone(cfg.calibration.homography_state)

    def test_calib_state_passthrough_unpacks(self):
        cfg = Settings()._dict_to_config({
            "calibration": {
                "save_homography": False,
                "homography_state": {"screen_w": 1920},
                "bogus_field": 1,
            }
        })
        self.assertFalse(cfg.calibration.save_homography)
        self.assertEqual(cfg.calibration.homography_state["screen_w"], 1920)
        self.assertFalse(hasattr(cfg.calibration, "bogus_field"))

    def test_quality_float(self):
        c = Calibrator(1920, 1080)
        _calibrate(c)
        self.assertIsInstance(c.result, CalibrationResult)
        self.assertGreater(c.result.quality, 0.5)


if __name__ == "__main__":
    unittest.main()