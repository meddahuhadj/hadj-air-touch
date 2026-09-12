"""Tests for the gesture recognition engine."""
from __future__ import annotations

import unittest
import time

from app.tracking.models import HandData, Landmark2D, FingerState
from app.gestures.gestures import (
    GestureType,
    SwipeDetector,
    TwoFingerZoomDetector,
    WaveDetector,
    is_pointing,
    is_pinching,
    is_grabbing,
    is_open_palm,
    is_fist,
    is_peace_sign,
    is_two_finger_pinch,
    is_thumbs_up,
)
from app.gestures.engine import GestureEngine, GestureResult


def _make_hand(
    thumb_ext: bool = False,
    index_ext: bool = True,
    middle_ext: bool = False,
    ring_ext: bool = False,
    pinky_ext: bool = False,
    index_tip: tuple[float, float] = (0.5, 0.3),
    thumb_tip: tuple[float, float] = (0.45, 0.35),
    middle_tip: tuple[float, float] = (0.55, 0.4),
) -> HandData:
    """Create a HandData with controlled finger states."""
    def _fs(ext: bool) -> FingerState:
        return FingerState.EXTENDED if ext else FingerState.FOLDED

    finger_states = {
        "thumb": _fs(thumb_ext),
        "index": _fs(index_ext),
        "middle": _fs(middle_ext),
        "ring": _fs(ring_ext),
        "pinky": _fs(pinky_ext),
    }

    landmarks = []
    # Generate 21 basic landmarks
    for i in range(21):
        landmarks.append(Landmark2D(index=i, x=0.5, y=0.5, z=0.0, visibility=0.9))

    # Override specific tips
    from app.tracking.models import INDEX_TIP, THUMB_TIP, MIDDLE_TIP, INDEX_PIP, THUMB_MCP, INDEX_MCP
    landmarks[INDEX_TIP] = Landmark2D(INDEX_TIP, index_tip[0], index_tip[1], 0.0, 0.9)
    landmarks[THUMB_TIP] = Landmark2D(THUMB_TIP, thumb_tip[0], thumb_tip[1], 0.0, 0.9)
    landmarks[MIDDLE_TIP] = Landmark2D(MIDDLE_TIP, middle_tip[0], middle_tip[1], 0.0, 0.9)

    return HandData(
        landmarks=landmarks,
        handedness="Right",
        confidence=0.9,
        finger_states=finger_states,
    )


class TestPointingDetector(unittest.TestCase):
    def test_pointing(self):
        hand = _make_hand(index_ext=True, middle_ext=False, ring_ext=False, pinky_ext=False)
        self.assertTrue(is_pointing(hand))

    def test_not_pointing_all_extended(self):
        hand = _make_hand(index_ext=True, middle_ext=True, ring_ext=True, pinky_ext=True)
        self.assertFalse(is_pointing(hand))

    def test_not_pointing_index_folded(self):
        hand = _make_hand(index_ext=False)
        self.assertFalse(is_pointing(hand))

    def test_no_finger_states(self):
        hand = HandData(landmarks=[], finger_states={})
        self.assertFalse(is_pointing(hand))


class TestPinchingDetector(unittest.TestCase):
    def test_pinch_close(self):
        hand = _make_hand(index_tip=(0.5, 0.3), thumb_tip=(0.49, 0.31))
        self.assertTrue(is_pinching(hand, threshold=0.06))

    def test_pinch_far(self):
        hand = _make_hand(index_tip=(0.5, 0.3), thumb_tip=(0.3, 0.5))
        self.assertFalse(is_pinching(hand, threshold=0.06))

    def test_pinch_no_tip(self):
        hand = HandData(landmarks=[], finger_states={})
        self.assertFalse(is_pinching(hand))


class TestOpenPalmDetector(unittest.TestCase):
    def test_open_palm(self):
        hand = _make_hand(thumb_ext=True, index_ext=True, middle_ext=True, ring_ext=True, pinky_ext=True)
        self.assertTrue(is_open_palm(hand))

    def test_not_open_palm(self):
        hand = _make_hand(thumb_ext=True, index_ext=True, middle_ext=False)
        self.assertFalse(is_open_palm(hand))


class TestFistDetector(unittest.TestCase):
    def test_fist(self):
        hand = _make_hand(thumb_ext=False, index_ext=False, middle_ext=False, ring_ext=False, pinky_ext=False)
        self.assertTrue(is_fist(hand))

    def test_not_fist(self):
        hand = _make_hand(thumb_ext=False, index_ext=True)
        self.assertFalse(is_fist(hand))


class TestGrabDetector(unittest.TestCase):
    def test_grab(self):
        hand = _make_hand(index_ext=False, middle_ext=False, ring_ext=False, pinky_ext=False)
        self.assertTrue(is_grabbing(hand))


class TestPeaceSign(unittest.TestCase):
    def test_peace(self):
        hand = _make_hand(index_ext=True, middle_ext=True, ring_ext=False, pinky_ext=False)
        self.assertTrue(is_peace_sign(hand))


class TestRightClickGesture(unittest.TestCase):
    def test_right_click(self):
        hand = _make_hand(thumb_tip=(0.5, 0.3), middle_tip=(0.51, 0.31))
        self.assertTrue(is_two_finger_pinch(hand, threshold=0.06))

    def test_not_right_click(self):
        hand = _make_hand(thumb_tip=(0.3, 0.3), middle_tip=(0.7, 0.7))
        self.assertFalse(is_two_finger_pinch(hand, threshold=0.06))


def _wave_hand(x: float) -> HandData:
    """Hand whose palm centre is at horizontal position x (no finger states)."""
    landmarks = [Landmark2D(i, x, 0.5, 0.0, 0.9) for i in range(21)]
    return HandData(landmarks=landmarks, confidence=0.9, finger_states={})


class TestThumbsUpDetector(unittest.TestCase):
    def test_thumbs_up(self):
        hand = _make_hand(thumb_ext=True, index_ext=False)
        self.assertTrue(is_thumbs_up(hand))

    def test_not_thumbs_up_fist(self):
        hand = _make_hand(thumb_ext=False)
        self.assertFalse(is_thumbs_up(hand))

    def test_not_thumbs_up_index_extended(self):
        hand = _make_hand(thumb_ext=True)
        self.assertFalse(is_thumbs_up(hand))

    def test_not_thumbs_up_all_extended(self):
        hand = _make_hand(thumb_ext=True, index_ext=True, middle_ext=True, ring_ext=True, pinky_ext=True)
        self.assertFalse(is_thumbs_up(hand))

    def test_thumbs_up_sticks_out_beyond_folded_fingers(self):
        # Thumb extended but tucked against the fingers = grab, not thumbs-up.
        hand = _make_hand(thumb_ext=True, index_ext=False,
                          thumb_tip=(0.52, 0.4), middle_tip=(0.5, 0.38))
        self.assertFalse(is_thumbs_up(hand))

    def test_no_finger_states(self):
        self.assertFalse(is_thumbs_up(_wave_hand(0.5)))


class TestWaveDetector(unittest.TestCase):
    def test_wave_detected(self):
        wd = WaveDetector()
        now = time.perf_counter()
        result = None
        for x in [0.3, 0.5, 0.3, 0.5, 0.3, 0.5, 0.3]:
            result = wd.update(_wave_hand(x), now)
            now += 0.1
            if result is not None:
                break
        self.assertEqual(result, GestureType.WAVE)

    def test_no_wave_without_oscillation(self):
        wd = WaveDetector()
        now = time.perf_counter()
        result = None
        for _ in range(10):
            result = wd.update(_wave_hand(0.5), now)
            now += 0.1
        self.assertIsNone(result)

    def test_no_wave_single_direction(self):
        wd = WaveDetector()
        now = time.perf_counter()
        result = None
        for x in [0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8]:
            result = wd.update(_wave_hand(x), now)
            now += 0.1
        self.assertIsNone(result)

    def test_cooldown_after_wave(self):
        wd = WaveDetector()
        now = time.perf_counter()
        result = None
        for x in [0.3, 0.5, 0.3, 0.5, 0.3, 0.5]:
            result = wd.update(_wave_hand(x), now)
            now += 0.1
        self.assertEqual(result, GestureType.WAVE)
        self.assertIsNone(wd.update(_wave_hand(0.5), now))

    def test_hand_lost_clears_history(self):
        wd = WaveDetector()
        now = time.perf_counter()
        for x in [0.3, 0.5, 0.3, 0.5]:
            wd.update(_wave_hand(x), now)
            now += 0.1
        wd.update(HandData(landmarks=[], finger_states={}), now)
        self.assertEqual(wd._state.positions, [])


class TestSwipeDetector(unittest.TestCase):
    def test_swipe_right(self):
        sd = SwipeDetector(min_distance=0.05)
        now = time.perf_counter()
        hand1 = _make_hand(index_tip=(0.3, 0.5))
        sd.update(hand1, now)
        hand2 = _make_hand(index_tip=(0.4, 0.5))
        sd.update(hand2, now + 0.1)
        hand3 = _make_hand(index_tip=(0.6, 0.5))
        result = sd.update(hand3, now + 0.2)
        self.assertEqual(result, GestureType.SWIPE_RIGHT)

    def test_no_swipe_small_movement(self):
        sd = SwipeDetector(min_distance=0.5)
        now = time.perf_counter()
        hand = _make_hand(index_tip=(0.5, 0.5))
        sd.update(hand, now)
        hand2 = _make_hand(index_tip=(0.51, 0.5))
        result = sd.update(hand2, now + 0.1)
        self.assertIsNone(result)

    def test_swipe_left(self):
        sd = SwipeDetector(min_distance=0.05)
        now = time.perf_counter()
        sd.update(_make_hand(index_tip=(0.6, 0.5)), now)
        sd.update(_make_hand(index_tip=(0.4, 0.5)), now + 0.1)
        result = sd.update(_make_hand(index_tip=(0.2, 0.5)), now + 0.2)
        self.assertEqual(result, GestureType.SWIPE_LEFT)

    def test_swipe_down(self):
        sd = SwipeDetector(min_distance=0.05)
        now = time.perf_counter()
        sd.update(_make_hand(index_tip=(0.5, 0.3)), now)
        sd.update(_make_hand(index_tip=(0.5, 0.5)), now + 0.1)
        result = sd.update(_make_hand(index_tip=(0.5, 0.7)), now + 0.2)
        self.assertEqual(result, GestureType.SWIPE_DOWN)

    def test_swipe_up(self):
        sd = SwipeDetector(min_distance=0.05)
        now = time.perf_counter()
        sd.update(_make_hand(index_tip=(0.5, 0.7)), now)
        sd.update(_make_hand(index_tip=(0.5, 0.5)), now + 0.1)
        result = sd.update(_make_hand(index_tip=(0.5, 0.3)), now + 0.2)
        self.assertEqual(result, GestureType.SWIPE_UP)


class TestTwoFingerZoom(unittest.TestCase):
    def test_zoom_out(self):
        zd = TwoFingerZoomDetector()
        now = time.perf_counter()
        h1 = _make_hand(thumb_tip=(0.4, 0.4), index_tip=(0.45, 0.4))
        zd.update(h1, now)
        h2 = _make_hand(thumb_tip=(0.3, 0.3), index_tip=(0.6, 0.6))
        result = zd.update(h2, now + 0.1)
        self.assertEqual(result, GestureType.TWO_FINGER_PINCH_OUT)

    def test_zoom_in(self):
        zd = TwoFingerZoomDetector()
        now = time.perf_counter()
        h1 = _make_hand(thumb_tip=(0.3, 0.3), index_tip=(0.6, 0.6))
        zd.update(h1, now)
        h2 = _make_hand(thumb_tip=(0.4, 0.4), index_tip=(0.45, 0.4))
        result = zd.update(h2, now + 0.1)
        self.assertEqual(result, GestureType.TWO_FINGER_PINCH_IN)

    def test_zoom_ignores_small_change(self):
        zd = TwoFingerZoomDetector()
        now = time.perf_counter()
        h1 = _make_hand(thumb_tip=(0.4, 0.4), index_tip=(0.5, 0.4))
        zd.update(h1, now)
        h2 = _make_hand(thumb_tip=(0.41, 0.4), index_tip=(0.5, 0.4))
        result = zd.update(h2, now + 0.1)
        self.assertIsNone(result)


class TestGestureEngine(unittest.TestCase):
    def test_pointing_triggers(self):
        engine = GestureEngine()
        hand = _make_hand(index_ext=True, middle_ext=False, ring_ext=False, pinky_ext=False)
        result = engine.update(hand, 1.0)
        self.assertIsNotNone(result)
        self.assertEqual(result.name, GestureType.POINT)

    def test_pinch_triggers(self):
        engine = GestureEngine()
        hand = _make_hand(index_tip=(0.5, 0.3), thumb_tip=(0.49, 0.31))
        result = engine.update(hand, 1.0)
        self.assertIsNotNone(result)
        self.assertEqual(result.name, GestureType.PINCH)

    def test_cooldown_prevents_rapid_fire(self):
        engine = GestureEngine()
        hand = _make_hand(index_ext=True, middle_ext=False, ring_ext=False, pinky_ext=False)
        r1 = engine.update(hand, 1.0)
        self.assertIsNotNone(r1)
        r2 = engine.update(hand, 1.05)
        self.assertIsNone(r2)  # cooldown blocks

    def test_pinch_hold_does_not_refire(self):
        engine = GestureEngine()
        hand = _make_hand(index_tip=(0.5, 0.3), thumb_tip=(0.49, 0.31))
        r1 = engine.update(hand, 1.0)
        self.assertEqual(r1.name, GestureType.PINCH)
        r2 = engine.update(hand, 1.05)  # still pinching
        self.assertIsNone(r2)  # should NOT refire while held

    def test_double_pinch(self):
        engine = GestureEngine()
        engine.configure("zoom", False)
        engine.configure("swipe", False)
        pinch = _make_hand(index_tip=(0.5, 0.3), thumb_tip=(0.49, 0.31))
        release = _make_hand(index_tip=(0.5, 0.5), thumb_tip=(0.3, 0.5), index_ext=True)
        r1 = engine.update(pinch, 1.0)
        self.assertEqual(r1.name, GestureType.PINCH)
        r2 = engine.update(release, 1.05)  # release
        self.assertIsNone(r2)
        r3 = engine.update(pinch, 1.1)  # press again within window
        self.assertEqual(r3.name, GestureType.DOUBLE_PINCH)

    def test_double_pinch_window_expired(self):
        engine = GestureEngine()
        engine.configure("zoom", False)
        engine.configure("swipe", False)
        pinch = _make_hand(index_tip=(0.5, 0.3), thumb_tip=(0.49, 0.31))
        release = _make_hand(index_tip=(0.5, 0.5), thumb_tip=(0.3, 0.5), index_ext=True)
        engine.update(pinch, 1.0)
        engine.update(release, 1.05)
        r3 = engine.update(pinch, 1.6)  # 0.5s > 0.4s window
        self.assertEqual(r3.name, GestureType.PINCH)

    def test_disabled_gesture_not_triggered(self):
        engine = GestureEngine()
        engine.configure("point", False)
        engine.configure("pinch", False)
        hand = _make_hand(index_ext=True, middle_ext=False)
        result = engine.update(hand, 1.0)
        self.assertIsNone(result)

    def test_thumbs_up_triggers_when_enabled(self):
        engine = GestureEngine()
        engine.configure("thumbs_up", True)
        engine.configure("pinch", False)
        engine.configure("swipe", False)
        hand = _make_hand(thumb_ext=True, index_ext=False)
        result = engine.update(hand, 1.0)
        self.assertEqual(result.name, GestureType.THUMBS_UP)

    def test_thumbs_up_off_by_default(self):
        engine = GestureEngine()
        engine.configure("pinch", False)
        engine.configure("open_palm", False)
        hand = _make_hand(thumb_ext=True)
        # grab would fire (default on) – make sure thumbs_up is NOT fired.
        result = engine.update(hand, 1.0)
        self.assertNotEqual(result.name, GestureType.THUMBS_UP)

    def test_wave_triggers_when_enabled(self):
        engine = GestureEngine()
        engine.configure("wave", True)
        engine.configure("swipe", False)
        engine.configure("pinch", False)
        engine.configure("right_click", False)
        now = 1.0
        result = None
        for x in [0.3, 0.5, 0.3, 0.5, 0.3, 0.5, 0.3]:
            result = engine.update(_wave_hand(x), now)
            now += 0.1
            if result is not None:
                break
        self.assertEqual(result.name, GestureType.WAVE)

    def test_wave_off_by_default(self):
        engine = GestureEngine()
        engine.configure("swipe", False)
        engine.configure("pinch", False)
        engine.configure("right_click", False)
        now = 1.0
        for x in [0.3, 0.5, 0.3, 0.5, 0.3, 0.5, 0.3]:
            result = engine.update(_wave_hand(x), now)
            now += 0.1
        self.assertIsNone(result)


if __name__ == "__main__":
    unittest.main()