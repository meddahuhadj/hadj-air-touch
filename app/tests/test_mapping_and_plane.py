"""Tests for gesture mapping and screen plane."""
from __future__ import annotations

import unittest

from app.gestures.mapping import gesture_action_lookup, get_profile_names, get_profile_map
from app.virtual_touch.plane import ScreenPlane


class TestGestureMapping(unittest.TestCase):
    def test_default_pinch_is_left_click(self):
        self.assertEqual(gesture_action_lookup("pinch"), "left_click")

    def test_default_double_pinch(self):
        self.assertEqual(gesture_action_lookup("double_pinch"), "double_click")

    def test_default_right_click(self):
        self.assertEqual(gesture_action_lookup("right_click"), "right_click")

    def test_point_has_no_action(self):
        """Pointing moves cursor – dispatched in pipeline, not by mapping."""
        self.assertIsNone(gesture_action_lookup("point"))

    def test_presentation_swipe_left(self):
        self.assertEqual(
            gesture_action_lookup("swipe_left", "presentation"),
            "previous_slide",
        )

    def test_browser_swipe(self):
        self.assertEqual(gesture_action_lookup("swipe_left", "browser"), "back")
        self.assertEqual(gesture_action_lookup("swipe_right", "browser"), "forward")

    def test_unknown_gesture(self):
        self.assertIsNone(gesture_action_lookup("does_not_exist"))

    def test_profile_names(self):
        names = get_profile_names()
        self.assertIn("general", names)
        self.assertIn("browser", names)
        self.assertIn("presentation", names)

    def test_profile_names_include_new(self):
        names = get_profile_names()
        for n in ("cad", "office", "developer"):
            self.assertIn(n, names)

    def test_cad_profile_maps(self):
        self.assertEqual(gesture_action_lookup("swipe_left", "cad"), "undo")
        self.assertEqual(gesture_action_lookup("swipe_right", "cad"), "redo")
        self.assertEqual(gesture_action_lookup("fist", "cad"), "save")

    def test_office_profile_maps(self):
        self.assertEqual(gesture_action_lookup("thumbs_up", "office"), "save")
        self.assertEqual(gesture_action_lookup("peace", "office"), "undo")
        self.assertEqual(gesture_action_lookup("open_palm", "office"), "select_all")

    def test_developer_profile_maps(self):
        self.assertEqual(gesture_action_lookup("swipe_right", "developer"), "switch_tab_next")
        self.assertEqual(gesture_action_lookup("swipe_left", "developer"), "switch_tab_prev")
        self.assertEqual(gesture_action_lookup("thumbs_up", "developer"), "new_tab")

    def test_wave_unmapped_by_default(self):
        self.assertIsNone(gesture_action_lookup("wave"))

    def test_get_profile_map(self):
        m = get_profile_map("general")
        self.assertIn("pinch", m)


class TestScreenPlane(unittest.TestCase):
    def test_calibrate_and_map(self):
        sp = ScreenPlane(1920, 1080)
        cam = [(0.2, 0.2), (0.8, 0.2), (0.8, 0.8), (0.2, 0.8)]
        scr = [(0, 0), (1920, 0), (1920, 1080), (0, 1080)]
        quality = sp.calibrate(cam, scr)
        self.assertGreater(quality, 0.5)
        mapped = sp.camera_to_screen((0.5, 0.5))
        self.assertIsNotNone(mapped)
        self.assertAlmostEqual(mapped[0], 960, delta=30)
        self.assertAlmostEqual(mapped[1], 540, delta=30)

    def test_map_without_calibration(self):
        sp = ScreenPlane()
        self.assertIsNone(sp.camera_to_screen((0.5, 0.5)))

    def test_inverse_mapping(self):
        sp = ScreenPlane(1920, 1080)
        cam = [(0.2, 0.2), (0.8, 0.2), (0.8, 0.8), (0.2, 0.8)]
        scr = [(0, 0), (1920, 0), (1920, 1080), (0, 1080)]
        sp.calibrate(cam, scr)
        back = sp.screen_to_camera((960, 540))
        self.assertIsNotNone(back)
        self.assertAlmostEqual(back[0], 0.5, delta=0.05)
        self.assertAlmostEqual(back[1], 0.5, delta=0.05)


class TestEventBus(unittest.TestCase):
    def test_subscribe_and_emit(self):
        from app.core.events import EventBus, Event, EventType
        bus = EventBus()
        received = []
        bus.subscribe(EventType.STATE_CHANGED, lambda e: received.append(e))
        bus.emit_simple(EventType.STATE_CHANGED, status="running")
        self.assertEqual(len(received), 1)
        self.assertEqual(received[0].data["status"], "running")

    def test_unsubscribe(self):
        from app.core.events import EventBus, EventType
        bus = EventBus()
        received = []
        unsub = bus.subscribe(EventType.MOUSE_CLICK, lambda e: received.append(1))
        bus.emit_simple(EventType.MOUSE_CLICK)
        self.assertEqual(len(received), 1)
        unsub()
        bus.emit_simple(EventType.MOUSE_CLICK)
        self.assertEqual(len(received), 1)


class TestTelemetry(unittest.TestCase):
    def test_fps_calculation(self):
        from app.services.telemetry import Telemetry
        t = Telemetry(window_size=10)
        t.update_frame(0.0)
        t.update_frame(1.0)
        # 1 frame over 1 second = 1 FPS
        self.assertAlmostEqual(t.fps, 1.0, delta=0.1)
        self.assertAlmostEqual(t.latency_ms, 1000.0, delta=1.0)

    def test_single_frame(self):
        from app.services.telemetry import Telemetry
        t = Telemetry()
        t.update_frame(0.5)
        self.assertEqual(t.latency_ms, 0.0)


if __name__ == "__main__":
    unittest.main()