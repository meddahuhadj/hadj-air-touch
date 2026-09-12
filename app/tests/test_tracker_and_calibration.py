"""Tests for the calibration workflow and the hand tracker wrapper.

The hand tracker is tested with a fake mediapipe module injected into
``sys.modules`` so both the capable and degraded paths run in-process.
"""
from __future__ import annotations

import sys
import types
import unittest
from unittest.mock import Mock

from app.calibration.calibrator import Calibrator, CalibState
from app.tracking.hand_tracker import HandTracker


class TestCalibratorFlow(unittest.TestCase):
    def setUp(self):
        self.cal = Calibrator(screen_width=1920, screen_height=1080)

    def test_initial_state_is_idle(self):
        self.assertEqual(self.cal.state, CalibState.IDLE)
        self.assertEqual(self.cal.result, self.cal.result)
        self.assertFalse(self.cal.result.success)

    def test_start_sets_top_left(self):
        self.cal.start()
        self.assertEqual(self.cal.state, CalibState.TOP_LEFT)
        name, pos = self.cal.get_current_corner()
        self.assertEqual(name, "top_left")
        self.assertEqual(pos, (0, 0))

    def test_corner_sequence(self):
        self.cal.start()
        expected = [
            ("top_left", (0, 0)),
            ("top_right", (1920, 0)),
            ("bottom_right", (1920, 1080)),
            ("bottom_left", (0, 1080)),
        ]
        for i, (name, pos) in enumerate(expected):
            self.assertEqual(self.cal.get_current_corner(), (name, pos))
            if i < 3:
                self.assertTrue(self.cal.feed_point_auto((0.2, 0.2)))

    def test_feed_point_ignored_when_idle(self):
        self.assertFalse(self.cal.feed_point((0.5, 0.5)))

    def test_feed_point_requires_hold(self):
        self.cal.start()
        self.assertFalse(self.cal.feed_point((0.5, 0.5)))  # no hold time yet

    def test_full_calibration_succeeds(self):
        self.cal.start()
        camera_pts = [(0.2, 0.2), (0.8, 0.2), (0.8, 0.8), (0.2, 0.8)]
        for pt in camera_pts:
            self.assertTrue(self.cal.feed_point_auto(pt))
        self.assertEqual(self.cal.state, CalibState.DONE)
        res = self.cal.result
        self.assertTrue(res.success)
        self.assertGreater(res.quality, 0.5)
        self.assertIsNotNone(res.homography)
        self.assertEqual(res.camera_points, camera_pts)
        self.assertEqual(res.screen_points,
                         [(0, 0), (1920, 0), (1920, 1080), (0, 1080)])
        self.assertIn("complete", res.message)

    def test_mapping_after_calibration(self):
        self.cal.start()
        for pt in [(0.2, 0.2), (0.8, 0.2), (0.8, 0.8), (0.2, 0.8)]:
            self.cal.feed_point_auto(pt)
        scr = self.cal.map_camera_to_screen((0.2, 0.2))
        self.assertIsNotNone(scr)
        self.assertLess(abs(scr[0]), 300)
        self.assertLess(abs(scr[1]), 300)

    def test_reset_clears_state(self):
        self.cal.start()
        for pt in [(0.2, 0.2), (0.8, 0.2), (0.8, 0.8), (0.2, 0.8)]:
            self.cal.feed_point_auto(pt)
        self.assertEqual(self.cal.state, CalibState.DONE)
        self.cal.reset()
        self.assertEqual(self.cal.state, CalibState.IDLE)
        self.assertFalse(self.cal.result.success)

    def test_skip_all_points_fails(self):
        self.cal.start()
        for _ in range(4):
            self.cal.skip_current()
        self.assertFalse(self.cal.result.success)
        self.assertIn(self.cal.state, (CalibState.DONE, CalibState.FAILED))

    def test_skips_interleave_corners(self):
        self.cal.start()
        self.cal.skip_current()
        self.assertEqual(self.cal.state, CalibState.TOP_RIGHT)
        self.cal.skip_current()
        self.assertEqual(self.cal.state, CalibState.BOTTOM_RIGHT)
        self.cal.skip_current()
        self.assertEqual(self.cal.state, CalibState.BOTTOM_LEFT)


class TestHandTrackerWithoutMediaPipe(unittest.TestCase):
    def test_degrades_gracefully(self):
        import unittest.mock as mock
        with mock.patch.dict(sys.modules, {"mediapipe": None}):
            tracker = HandTracker()
            self.assertFalse(tracker.available)
            self.assertIsNone(tracker.process_frame(None))
            self.assertEqual(tracker.close(), None)


class TestHandTrackerWithMediaPipe(unittest.TestCase):
    def test_process_frame_converts_landmarks(self):
        fakes = _mediapipe_fakes(return_hand=True)
        with _patch_mediapipe(fakes["module"]):
            tracker = HandTracker(max_hands=1)
            self.assertTrue(tracker.available)
            hand = tracker.process_frame(None)
            self.assertIsNotNone(hand)
            self.assertEqual(len(hand.landmarks), 21)
            self.assertEqual(hand.landmarks[8].x, 0.4)
            self.assertEqual(hand.handedness, "Left")
            self.assertGreater(hand.confidence, 0.8)
            self.assertIn("index", hand.finger_states)
            # Hands was built with our config
            fakes["hands_cls"].assert_called_once_with(
                static_image_mode=False, max_num_hands=1,
                min_detection_confidence=0.7, min_tracking_confidence=0.6)
            tracker.close()
            fakes["hands_instance"].close.assert_called_once()

    def test_process_frame_no_hand_returns_none(self):
        fakes = _mediapipe_fakes(return_hand=False)
        with _patch_mediapipe(fakes["module"]):
            tracker = HandTracker()
            self.assertIsNone(tracker.process_frame(None))


def _mediapipe_fakes(return_hand: bool = True):
    """Build a fake mediapipe package plus a fake Hands instance."""
    mp = types.ModuleType("mediapipe")
    solutions = types.ModuleType("mediapipe.solutions")
    sol_hands = types.ModuleType("mediapipe.solutions.hands")
    mp.solutions = solutions
    solutions.hands = sol_hands

    hands_instance = Mock()
    if return_hand:
        fake_landmarks = [
            types.SimpleNamespace(x=i / 20.0, y=0.3, z=-0.01, visibility=0.9)
            for i in range(21)
        ]
        fake_hand = types.SimpleNamespace(landmark=fake_landmarks)
        results = types.SimpleNamespace(
            multi_hand_landmarks=[fake_hand],
            multi_handedness=[types.SimpleNamespace(
                classification=[types.SimpleNamespace(label="Left")])],
        )
        hands_instance.process.return_value = results
    else:
        hands_instance.process.return_value = types.SimpleNamespace(
            multi_hand_landmarks=[])

    hands_cls = Mock(return_value=hands_instance)
    sol_hands.Hands = hands_cls
    return {"module": mp, "hands_cls": hands_cls, "hands_instance": hands_instance}


def _patch_mediapipe(fake_module):
    import unittest.mock as mock
    installed = {}
    for name in ("mediapipe", "mediapipe.solutions",
                 "mediapipe.solutions.hands"):
        installed[name] = sys.modules.get(name)
    return mock.patch.dict(sys.modules, {
        "mediapipe": fake_module,
        "mediapipe.solutions": fake_module.solutions,
        "mediapipe.solutions.hands": fake_module.solutions.hands,
    })


if __name__ == "__main__":
    unittest.main()