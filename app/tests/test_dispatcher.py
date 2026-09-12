"""Tests for the InputDispatcher cursor mapping (pure logic, no Win32/Qt)."""
from __future__ import annotations

import unittest
from unittest.mock import Mock

from app.windows_input.dispatcher import InputDispatcher
from app.calibration.calibrator import Calibrator
from app.config import Settings
from app.core.events import EventBus


def _make_dispatcher():
    bus = EventBus()
    mouse = Mock()
    kb = Mock()
    calibrator = Calibrator(screen_width=1920, screen_height=1080)
    settings = Settings()
    return InputDispatcher(bus, mouse, kb, calibrator, settings), (bus, mouse, kb, calibrator, settings)


class TestFingertipMapping(unittest.TestCase):
    def setUp(self):
        self.disp, (self.bus, self.mouse, self.kb, self.cal, self.settings) = _make_dispatcher()
        self.screen = (1920, 1080)

    def test_linear_mapping_without_calibration(self):
        pt = self.disp.map_fingertip_to_screen((0.5, 0.5), self.screen)
        self.assertEqual(pt, (960.0, 540.0))

    def test_linear_mapping_top_left(self):
        pt = self.disp.map_fingertip_to_screen((0.0, 0.0), self.screen)
        self.assertEqual(pt, (0.0, 0.0))

    def test_linear_mapping_bottom_right(self):
        pt = self.disp.map_fingertip_to_screen((1.0, 1.0), self.screen)
        self.assertEqual(pt, (1920.0, 1080.0))

    def test_homography_mapping_after_calibration(self):
        cam = [(0.2, 0.2), (0.8, 0.2), (0.8, 0.8), (0.2, 0.8)]
        scr = [(0, 0), (1920, 0), (1920, 1080), (0, 1080)]
        self.cal.plane.calibrate(cam, scr)
        pt = self.disp.map_fingertip_to_screen((0.5, 0.5), self.screen)
        self.assertGreater(pt[0], 500)
        self.assertLess(pt[1], 800)


class TestCursorSettings(unittest.TestCase):
    def setUp(self):
        self.disp, _ = _make_dispatcher()

    def test_no_movement_when_target_equals_pos(self):
        r = self.disp.apply_cursor_settings((100, 100), (100, 100), speed=1.0, smoothing=0.5)
        self.assertAlmostEqual(r[0], 100.0)
        self.assertAlmostEqual(r[1], 100.0)

    def test_moves_toward_target(self):
        r = self.disp.apply_cursor_settings((200, 200), (100, 100),
                                            speed=1.0, smoothing=0.5)
        self.assertGreater(r[0], 100.0)
        self.assertLess(r[0], 200.0)

    def test_higher_speed_moves_further(self):
        r1 = self.disp.apply_cursor_settings((200, 200), (100, 100),
                                             speed=0.1, smoothing=0.0)
        r2 = self.disp.apply_cursor_settings((200, 200), (100, 100),
                                             speed=2.0, smoothing=0.0)
        self.assertGreater(r2[0], r1[0])

    def test_smoothing_reduces_step(self):
        r_raw = self.disp.apply_cursor_settings((200, 200), (100, 100),
                                                speed=1.0, smoothing=0.0)
        r_smooth = self.disp.apply_cursor_settings((200, 200), (100, 100),
                                                   speed=1.0, smoothing=0.9)
        self.assertLess(r_smooth[0], r_raw[0])

    def test_dead_zone_holds_cursor_still(self):
        # dead_zone 0.02 of 1080 => ~21.6px; a 10px jitter must be ignored
        r = self.disp.apply_cursor_settings((110, 100), (100, 100),
                                            speed=1.0, smoothing=0.0,
                                            dead_zone=0.02, screen_height=1080)
        self.assertEqual(r, (100.0, 100.0))

    def test_dead_zone_allows_large_moves(self):
        r = self.disp.apply_cursor_settings((160, 100), (100, 100),
                                            speed=1.0, smoothing=0.0,
                                            dead_zone=0.02, screen_height=1080)
        self.assertGreater(r[0], 150.0)

    def test_dead_zone_zero_has_no_effect(self):
        r1 = self.disp.apply_cursor_settings((110, 100), (100, 100),
                                             speed=1.0, smoothing=0.0,
                                             dead_zone=0.0)
        r2 = self.disp.apply_cursor_settings((110, 100), (100, 100),
                                             speed=1.0, smoothing=0.0)
        self.assertEqual(r1, r2)


class TestShortcutActions(unittest.TestCase):
    def setUp(self):
        from app.config import Settings
        Settings._instance = None
        self.disp, (self.bus, self.mouse, self.kb, self.cal, self.settings) = _make_dispatcher()

    def tearDown(self):
        from app.config import Settings
        Settings._instance = None

    def test_office_swipe_left_undo(self):
        self.settings.set("active_profile", "office")
        self.disp.handle_gesture("swipe_left")
        self.kb.hotkey.assert_called_with("ctrl", "z")

    def test_office_thumbs_up_save(self):
        self.settings.set("active_profile", "office")
        self.disp.handle_gesture("thumbs_up")
        self.kb.hotkey.assert_called_with("ctrl", "s")

    def test_developer_swipe_right_switches_tab(self):
        self.settings.set("active_profile", "developer")
        self.disp.handle_gesture("swipe_right")
        self.kb.hotkey.assert_called_with("ctrl", "tab")

    def test_developer_swipe_right_switch_tab_is_double_tab(self):
        self.settings.set("active_profile", "developer")
        self.disp.handle_gesture("swipe_right")
        self.assertEqual(self.kb.hotkey.call_count, 1)

    def test_developer_thumbs_up_new_tab(self):
        self.settings.set("active_profile", "developer")
        self.disp.handle_gesture("thumbs_up")
        self.kb.hotkey.assert_called_with("ctrl", "t")

    def test_cad_swipe_left_undo(self):
        self.settings.set("active_profile", "cad")
        self.disp.handle_gesture("swipe_left")
        self.kb.hotkey.assert_called_with("ctrl", "z")

    def test_cad_fist_save(self):
        self.settings.set("active_profile", "cad")
        self.disp.handle_gesture("fist")
        self.kb.hotkey.assert_called_with("ctrl", "s")

    def test_general_thumbs_up_still_volume(self):
        self.settings.set("active_profile", "general")
        self.disp.handle_gesture("thumbs_up")
        self.kb.volume_up.assert_called()


if __name__ == "__main__":
    unittest.main()