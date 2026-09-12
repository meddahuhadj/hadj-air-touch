"""Integration test: gesture engine -> dispatcher -> (mock) Windows input.

Validates the full interaction chain without requiring OpenCV/MediaPipe/Qt.
"""
from __future__ import annotations

import unittest
from unittest.mock import Mock
import time

from app.tracking.models import HandData, Landmark2D, FingerState
from app.gestures.engine import GestureEngine
from app.gestures.gestures import GestureType
from app.windows_input.dispatcher import InputDispatcher
from app.calibration.calibrator import Calibrator
from app.config import Settings
from app.core.events import EventBus


def _hand(index_ext=True, middle_ext=False, ring_ext=False, pinky_ext=False,
          thumb_tip=(0.49, 0.31), index_tip=(0.5, 0.3), middle_tip=(0.5, 0.5)) -> HandData:
    def _fs(ext):
        return FingerState.EXTENDED if ext else FingerState.FOLDED
    states = {
        "thumb": _fs(False), "index": _fs(index_ext),
        "middle": _fs(middle_ext), "ring": _fs(ring_ext), "pinky": _fs(pinky_ext),
    }
    landmarks = [Landmark2D(i, 0.5, 0.5, 0.0, 0.9) for i in range(21)]
    from app.tracking.models import INDEX_TIP, THUMB_TIP, MIDDLE_TIP
    landmarks[INDEX_TIP] = Landmark2D(INDEX_TIP, index_tip[0], index_tip[1], 0.0, 0.9)
    landmarks[THUMB_TIP] = Landmark2D(THUMB_TIP, thumb_tip[0], thumb_tip[1], 0.0, 0.9)
    landmarks[MIDDLE_TIP] = Landmark2D(MIDDLE_TIP, middle_tip[0], middle_tip[1], 0.0, 0.9)
    return HandData(landmarks=landmarks, confidence=0.9, finger_states=states)


class TestEndToEnd(unittest.TestCase):
    def setUp(self):
        self.bus = EventBus()
        self.mouse = Mock()
        self.kb = Mock()
        self.cal = Calibrator(1920, 1080)
        Settings._instance = None
        self.settings = Settings()
        self.disp = InputDispatcher(self.bus, self.mouse, self.kb, self.cal, self.settings)
        self.engine = GestureEngine()

    def tearDown(self):
        Settings._instance = None

    def test_pinch_results_in_left_click(self):
        hand = _hand(thumb_tip=(0.49, 0.31), index_tip=(0.5, 0.3))
        result = self.engine.update(hand, time.perf_counter())
        self.assertEqual(result.name, GestureType.PINCH)
        self.disp.handle_gesture(result.name.name.lower())
        self.mouse.left_click.assert_called()

    def test_double_pinch_results_in_double_click(self):
        self.engine.configure("zoom", False)
        self.engine.configure("swipe", False)
        pinch = _hand(thumb_tip=(0.49, 0.31), index_tip=(0.5, 0.3))
        release = _hand(thumb_tip=(0.3, 0.5), index_tip=(0.5, 0.5))
        self.engine.update(pinch, 1.0)        # press
        self.engine.update(release, 1.05)     # release
        r2 = self.engine.update(pinch, 1.1)   # press again
        self.assertEqual(r2.name, GestureType.DOUBLE_PINCH)
        self.disp.handle_gesture(r2.name.name.lower())
        self.mouse.double_click.assert_called()

    def test_double_pinch_beyond_window_is_single_pinch(self):
        self.engine.configure("zoom", False)
        self.engine.configure("swipe", False)
        pinch = _hand(thumb_tip=(0.49, 0.31), index_tip=(0.5, 0.3))
        release = _hand(thumb_tip=(0.3, 0.5), index_tip=(0.5, 0.5))
        self.engine.update(pinch, 1.0)
        self.engine.update(release, 1.05)
        r2 = self.engine.update(pinch, 1.6)   # > 0.4s window
        self.assertEqual(r2.name, GestureType.PINCH)
        self.disp.handle_gesture(r2.name.name.lower())
        self.mouse.left_click.assert_called()

    def test_right_click_gesture(self):
        from app.gestures.gestures import is_two_finger_pinch
        # Thumb + middle close together (right click)
        hand = _hand(thumb_tip=(0.5, 0.3), middle_ext=True, middle_tip=(0.52, 0.32))
        self.assertTrue(is_two_finger_pinch(hand, threshold=0.09))
        self.disp.handle_gesture("right_click")
        self.mouse.right_click.assert_called()

    def test_open_palm_triggers_pause_mapping(self):
        # open_palm -> "pause" action -> no mouse call
        self.disp.handle_gesture("open_palm")
        self.mouse.left_click.assert_not_called()

    def test_swipe_gesture_maps_in_browser_profile(self):
        self.settings.set("active_profile", "browser")
        self.disp.handle_gesture("swipe_left")
        self.kb.hotkey.assert_called_with("alt", "left")

    def test_scroll_gesture(self):
        self.disp.handle_gesture("swipe_up")
        # swipe_up -> scroll_up -> scroll(3)
        self.mouse.scroll.assert_called_with(3)

    def test_volume_up_gesture(self):
        self.disp.handle_gesture("thumbs_up")
        self.kb.volume_up.assert_called()

    def test_media_play_pause(self):
        self.disp.handle_gesture("open_palm")  # media profile maps to play_pause
        # default profile maps to pause – no crash
        self.mouse.left_click.assert_not_called()

    def test_fingertip_mapping_uses_calibration_homography(self):
        self.cal.start()
        self.assertTrue(self.cal.feed_point_auto((0.0, 0.0)))
        self.assertTrue(self.cal.feed_point_auto((1.0, 0.0)))
        self.assertTrue(self.cal.feed_point_auto((1.0, 1.0)))
        self.assertTrue(self.cal.feed_point_auto((0.0, 1.0)))
        self.assertEqual(self.cal.state.name, "DONE")
        self.assertIsNotNone(self.cal.result.homography)
        pt = self.disp.map_fingertip_to_screen((0.5, 0.5), (1920, 1080))
        self.assertIsNotNone(pt)
        self.assertAlmostEqual(pt[0], 960, delta=2)
        self.assertAlmostEqual(pt[1], 540, delta=2)


class TestEventBridge(unittest.TestCase):
    def setUp(self):
        self.bus = EventBus()
        self.mouse = Mock()
        self.kb = Mock()
        self.cal = Calibrator(1920, 1080)
        Settings._instance = None
        self.settings = Settings()
        self.disp = InputDispatcher(self.bus, self.mouse, self.kb, self.cal, self.settings)

    def tearDown(self):
        Settings._instance = None

    def test_bus_click_event_reaches_mouse(self):
        from app.core.events import EventType
        self.bus.emit_simple(EventType.MOUSE_CLICK, button="left")
        self.mouse.left_click.assert_called()

    def test_bus_scroll_event(self):
        from app.core.events import EventType
        self.bus.emit_simple(EventType.MOUSE_SCROLL, delta=-2)
        self.mouse.scroll.assert_called_with(-2)

    def test_bus_keyboard_shortcut(self):
        from app.core.events import EventType
        self.bus.emit_simple(EventType.KEYBOARD_SHORTCUT, keys=["ctrl", "t"])
        self.kb.hotkey.assert_called_with("ctrl", "t")


if __name__ == "__main__":
    unittest.main()