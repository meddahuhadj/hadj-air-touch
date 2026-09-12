"""Tests for the configuration system."""
from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from app.config import (
    AppConfig,
    CameraConfig,
    Settings,
)


class TestAppConfigDefaults(unittest.TestCase):
    def test_defaults(self):
        cfg = AppConfig()
        self.assertEqual(cfg.camera.index, 0)
        self.assertEqual(cfg.camera.width, 1280)
        self.assertEqual(cfg.camera.height, 720)
        self.assertEqual(cfg.camera.fps, 30)
        self.assertTrue(cfg.camera.mirror)
        self.assertEqual(cfg.virtual_touch.touch_depth_cm, 3.0)
        self.assertFalse(cfg.accessibility.enabled)

    def test_mode(self):
        cfg = AppConfig()
        self.assertEqual(cfg.mode, "air_mouse")


class TestSettings(unittest.TestCase):
    def setUp(self):
        # Reset singleton
        Settings._instance = None
        self._tmpdir = tempfile.mkdtemp()
        self._config_path = Path(self._tmpdir) / "test_settings.json"

    def tearDown(self):
        Settings._instance = None

    def test_load_creates_defaults(self):
        s = Settings(self._config_path)
        self.assertEqual(s.config.camera.index, 0)

    def test_save_and_reload(self):
        s = Settings(self._config_path)
        s.set("camera.index", 5)
        s2 = Settings(self._config_path)
        self.assertEqual(s2.get("camera.index"), 5)

    def test_get_dotted_key(self):
        s = Settings(self._config_path)
        self.assertEqual(s.get("camera.width"), 1280)
        self.assertEqual(s.get("virtual_touch.smoothing"), 0.55)
        self.assertIsNone(s.get("nonexistent.key", None))
        self.assertEqual(s.get("nonexistent.key", 42), 42)

    def test_set_and_get(self):
        s = Settings(self._config_path)
        s.set("cursor.speed", 2.5)
        self.assertEqual(s.get("cursor.speed"), 2.5)

    def test_update_section(self):
        s = Settings(self._config_path)
        s.update_section("camera", {"width": 640, "height": 480})
        self.assertEqual(s.get("camera.width"), 640)
        self.assertEqual(s.get("camera.height"), 480)

    def test_reset(self):
        s = Settings(self._config_path)
        s.set("camera.index", 5)
        s.reset()
        self.assertEqual(s.get("camera.index"), 0)

    def test_as_dict(self):
        s = Settings(self._config_path)
        d = s.as_dict()
        self.assertIn("camera", d)
        self.assertIn("virtual_touch", d)
        self.assertIn("safety", d)

    def test_mode_roundtrip(self):
        s = Settings(self._config_path)
        s.set("mode", "virtual_touch")
        s2 = Settings(self._config_path)
        self.assertEqual(s2.get("mode"), "virtual_touch")

    def test_persistence_file_exists(self):
        s = Settings(self._config_path)
        s.set("test_key", "test_value")
        self.assertTrue(self._config_path.exists())
        raw = json.loads(self._config_path.read_text())
        self.assertEqual(raw["camera"]["index"], 0)

    def test_gestures_default_and_roundtrip(self):
        s = Settings(self._config_path)
        self.assertTrue(s.config.gestures["pinch"])
        self.assertFalse(s.config.gestures["fist"])
        gestures = dict(s.config.gestures)
        gestures["fist"] = True
        s.set("gestures", gestures)
        s2 = Settings(self._config_path)
        self.assertTrue(s2.config.gestures["fist"])
        self.assertTrue(s2.config.gestures["pinch"])

    def test_legacy_settingsfile_without_gestures(self):
        # A settings file saved before the `gestures` field existed must load,
        # falling back to the built-in defaults.
        self._config_path.write_text(
            json.dumps({"camera": {"index": 2}}), encoding="utf-8")
        s = Settings(self._config_path)
        self.assertEqual(s.config.camera.index, 2)
        self.assertTrue(s.config.gestures["point"])

    def test_cursor_new_fields_defaults(self):
        s = Settings(self._config_path)
        cfg = s.config.cursor
        self.assertEqual(cfg.dead_zone, 0.005)
        self.assertFalse(cfg.one_euro)
        self.assertEqual(cfg.one_euro_min_cutoff, 1.0)
        self.assertEqual(cfg.one_euro_beta, 0.007)

    def test_cursor_new_fields_roundtrip(self):
        s = Settings(self._config_path)
        s.set("cursor.dead_zone", 0.02)
        s.set("cursor.one_euro", True)
        s2 = Settings(self._config_path)
        self.assertAlmostEqual(s2.config.cursor.dead_zone, 0.02)
        self.assertTrue(s2.config.cursor.one_euro)

    def test_legacy_settingsfile_without_cursor_fields(self):
        # Files saved before dead_zone / one_euro existed must load with defaults.
        self._config_path.write_text(
            json.dumps({"cursor": {"speed": 1.5}}), encoding="utf-8")
        s = Settings(self._config_path)
        self.assertEqual(s.config.cursor.speed, 1.5)
        self.assertEqual(s.config.cursor.dead_zone, 0.005)
        self.assertFalse(s.config.cursor.one_euro)


if __name__ == "__main__":
    unittest.main()