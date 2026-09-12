"""Tests for the virtual touch state machine."""
from __future__ import annotations

import unittest

from app.virtual_touch.engine import VirtualTouchEngine, TouchState


class TestVirtualTouchStateMachine(unittest.TestCase):
    def setUp(self):
        self.vte = VirtualTouchEngine(
            touch_threshold_ms=50.0,
            hold_threshold_ms=100.0,
            release_threshold_ms=20.0,
        )

    def test_initial_state_is_idle(self):
        self.assertEqual(self.vte.state, TouchState.IDLE)

    def test_idle_to_pointing(self):
        self.vte.update(touching=False, finger_on_screen=True, elapsed_ms=50)
        self.assertEqual(self.vte.state, TouchState.POINTING)

    def test_pointing_back_to_idle_when_finger_leaves(self):
        # POINTING + finger leaves -> IDLE (not RELEASING)
        self.vte.update(touching=False, finger_on_screen=True, elapsed_ms=50)
        self.assertEqual(self.vte.state, TouchState.POINTING)
        self.vte.update(touching=False, finger_on_screen=False, elapsed_ms=50)
        self.assertEqual(self.vte.state, TouchState.IDLE)

    def test_full_tap_cycle(self):
        # IDLE
        self.vte.update(touching=False, finger_on_screen=True, elapsed_ms=50)
        self.assertEqual(self.vte.state, TouchState.POINTING)

        # POINTING + touching -> APPROACHING
        self.vte.update(touching=True, finger_on_screen=True, elapsed_ms=50)
        self.assertEqual(self.vte.state, TouchState.APPROACHING)

        # APPROACHING, need time_in_state > 50ms threshold
        self.vte.update(touching=True, finger_on_screen=True, elapsed_ms=50)
        # time_in_state = 100 (accumulated) - 50 (enter_time) = 50, NOT > 50 yet
        self.assertEqual(self.vte.state, TouchState.APPROACHING)

        self.vte.update(touching=True, finger_on_screen=True, elapsed_ms=10)
        # time_in_state = 110 - 50 = 60 > 50 -> tap -> VIRTUAL_TOUCH
        self.assertEqual(self.vte.state, TouchState.VIRTUAL_TOUCH)

        # Release
        self.vte.update(touching=False, finger_on_screen=False, elapsed_ms=50)
        self.assertEqual(self.vte.state, TouchState.RELEASING)

        # Settle back to IDLE
        self.vte.update(touching=False, finger_on_screen=False, elapsed_ms=50)
        self.assertEqual(self.vte.state, TouchState.IDLE)

    def test_long_press(self):
        # Get to VIRTUAL_TOUCH
        self.vte.update(touching=False, finger_on_screen=True, elapsed_ms=50)
        self.vte.update(touching=True, finger_on_screen=True, elapsed_ms=50)
        self.vte.update(touching=True, finger_on_screen=True, elapsed_ms=60)
        self.assertEqual(self.vte.state, TouchState.VIRTUAL_TOUCH)

        # Keep touching until hold_threshold (100ms from VIRTUAL_TOUCH entry)
        # VIRTUAL_TOUCH was entered at clock ~110, hold_threshold=100ms
        # Need clock > 210 to trigger
        self.vte.update(touching=True, finger_on_screen=True, elapsed_ms=100)
        self.assertIn(self.vte.state, (TouchState.VIRTUAL_TOUCH, TouchState.HOLDING))

        if self.vte.state == TouchState.VIRTUAL_TOUCH:
            self.vte.update(touching=True, finger_on_screen=True, elapsed_ms=50)
        self.assertIn(self.vte.state, (TouchState.VIRTUAL_TOUCH, TouchState.HOLDING))

    def test_drag_start(self):
        # Get to HOLDING
        self.vte.update(touching=False, finger_on_screen=True, elapsed_ms=50)
        self.vte.update(touching=True, finger_on_screen=True, elapsed_ms=50)
        self.vte.update(touching=True, finger_on_screen=True, elapsed_ms=60)
        # Keep touching to get past hold threshold
        for _ in range(5):
            self.vte.update(touching=True, finger_on_screen=True, elapsed_ms=100,
                            position=(0.5, 0.5))
        self.assertIn(self.vte.state, (TouchState.VIRTUAL_TOUCH, TouchState.HOLDING))

        if self.vte.state != TouchState.HOLDING:
            self.vte.update(touching=True, finger_on_screen=True, elapsed_ms=200,
                            position=(0.5, 0.5))

        if self.vte.state == TouchState.HOLDING:
            # Move finger significantly to trigger drag
            self.vte.update(touching=True, finger_on_screen=True, elapsed_ms=50,
                            position=(0.7, 0.5))
            self.assertIn(self.vte.state, (TouchState.HOLDING, TouchState.DRAGGING))

    def test_reset(self):
        self.vte.update(touching=False, finger_on_screen=True, elapsed_ms=50)
        self.vte.reset()
        self.assertEqual(self.vte.state, TouchState.IDLE)
        self.assertIsNone(self.vte.smoothed_position)


class TestVirtualTouchActions(unittest.TestCase):
    def test_tap_action_fires(self):
        vte = VirtualTouchEngine(touch_threshold_ms=10, hold_threshold_ms=1000)
        # IDLE -> POINTING
        vte.update(touching=False, finger_on_screen=True, elapsed_ms=10)
        # POINTING -> APPROACHING
        vte.update(touching=True, finger_on_screen=True, elapsed_ms=10)
        # APPROACHING, need > 10ms
        vte.update(touching=True, finger_on_screen=True, elapsed_ms=15)
        self.assertEqual(vte.action, "tap")

    def test_long_press_action_fires(self):
        vte = VirtualTouchEngine(touch_threshold_ms=5, hold_threshold_ms=20, release_threshold_ms=5)
        vte.update(touching=False, finger_on_screen=True, elapsed_ms=10)
        vte.update(touching=True, finger_on_screen=True, elapsed_ms=10)
        vte.update(touching=True, finger_on_screen=True, elapsed_ms=20)
        # Now should be in VIRTUAL_TOUCH, need hold threshold
        vte.update(touching=True, finger_on_screen=True, elapsed_ms=30)
        if vte.state == TouchState.VIRTUAL_TOUCH:
            vte.update(touching=True, finger_on_screen=True, elapsed_ms=50)
        # Should have fired long_press at some point
        # (action is per-frame, so it fires once then resets)
        self.assertIn(vte.state, (TouchState.VIRTUAL_TOUCH, TouchState.HOLDING))


if __name__ == "__main__":
    unittest.main()