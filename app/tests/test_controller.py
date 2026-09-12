"""Tests for the pipeline controller (orchestration) and keyboard VK logic.

Uses mocks for camera / tracker / dispatcher / screen manager so no hardware
(and no Win32 input injection) is required.
"""
from __future__ import annotations

import time
import unittest
from unittest.mock import Mock

from app.tracking.models import HandData, Landmark2D, FingerState, INDEX_MCP, INDEX_TIP
from app.core.events import EventBus, EventType
from app.core.state import AppStatus, Mode
from app.config import Settings
from app.core.controller import PipelineController
from app.virtual_touch.engine import VirtualTouchEngine, TouchState


def _hand(index_tip=(0.5, 0.3), tip_z: float = -0.1, mcp_z: float = 0.0) -> HandData:
    landmarks = [Landmark2D(i, 0.5, 0.5, 0.0, 0.9) for i in range(21)]
    landmarks[INDEX_TIP] = Landmark2D(INDEX_TIP, index_tip[0], index_tip[1], tip_z, 0.9)
    landmarks[INDEX_MCP] = Landmark2D(INDEX_MCP, 0.5, 0.5, mcp_z, 0.9)
    return HandData(
        landmarks=landmarks,
        confidence=0.9,
        finger_states={"index": FingerState.EXTENDED},
    )


def _fresh_controller():
    Settings._instance = None
    bus = EventBus()
    settings = Settings()
    pc = PipelineController(bus, settings)
    return pc, bus


class TestPipelineLifecycle(unittest.TestCase):
    def setUp(self):
        self.pc, self.bus = _fresh_controller()

    def tearDown(self):
        Settings._instance = None
        self.pc.stop()

    def test_initial_state(self):
        self.assertEqual(self.pc.state.status, AppStatus.IDLE)
        self.assertIsNone(self.pc._camera)

    def test_start_and_stop(self):
        self.pc.start()
        self.assertEqual(self.pc.state.status, AppStatus.RUNNING)
        self.pc.stop()
        self.assertEqual(self.pc.state.status, AppStatus.IDLE)

    def test_pause_resume(self):
        self.pc.pause()
        self.assertEqual(self.pc.state.status, AppStatus.PAUSED)
        self.assertFalse(self.pc.state.tracking_active)
        self.pc.resume()
        self.assertEqual(self.pc.state.status, AppStatus.RUNNING)
        self.assertTrue(self.pc.state.tracking_active)

    def test_emergency_stop_pauses(self):
        self.pc.resume()
        self.bus.emit_simple(EventType.EMERGENCY_STOP)
        self.assertEqual(self.pc.state.status, AppStatus.PAUSED)

    def test_start_without_components_loop_returns(self):
        self.pc.start()
        deadline = time.time() + 2.0
        while self.pc._thread is not None and self.pc._thread.is_alive() and time.time() < deadline:
            time.sleep(0.02)
        self.assertFalse(self.pc._thread.is_alive())


class TestPipelineDispatch(unittest.TestCase):
    def setUp(self):
        self.pc, self.bus = _fresh_controller()

    def tearDown(self):
        Settings._instance = None
        self.pc.stop()

    def test_open_palm_pauses(self):
        self.pc.resume()
        dispatcher = Mock()
        self.pc.set_dispatcher(dispatcher)
        self.pc._dispatch_action("OPEN_PALM", None)
        self.assertEqual(self.pc.state.status, AppStatus.PAUSED)
        dispatcher.handle_gesture.assert_not_called()

    def test_pause_gesture_name_pauses(self):
        self.pc.resume()
        self.pc._dispatch_action("PAUSE", None)
        self.assertEqual(self.pc.state.status, AppStatus.PAUSED)

    def test_resume_gesture_resumes(self):
        self.pc.pause()
        self.pc._dispatch_action("RESUME", None)
        self.assertEqual(self.pc.state.status, AppStatus.RUNNING)

    def test_wave_toggles_pause_resume(self):
        self.pc.resume()
        self.pc._dispatch_action("WAVE", None)
        self.assertEqual(self.pc.state.status, AppStatus.PAUSED)
        self.pc._dispatch_action("WAVE", None)
        self.assertEqual(self.pc.state.status, AppStatus.RUNNING)

    def test_other_gesture_delegates_to_dispatcher(self):
        dispatcher = Mock()
        self.pc.set_dispatcher(dispatcher)
        self.pc._dispatch_action("PINCH", None)
        dispatcher.handle_gesture.assert_called_once_with("pinch")

    def test_no_dispatcher_is_safe(self):
        self.pc._dispatch_action("PINCH", None)  # no crash

    def test_double_pinch_delegates_lowercase(self):
        dispatcher = Mock()
        self.pc.set_dispatcher(dispatcher)
        self.pc._dispatch_action("DOUBLE_PINCH", None)
        dispatcher.handle_gesture.assert_called_once_with("double_pinch")


class TestMoveCursor(unittest.TestCase):
    def setUp(self):
        self.pc, self.bus = _fresh_controller()
        self.dispatcher = Mock()
        self.screen = Mock()
        self.screen.get_screen_size.return_value = (1920, 1080)
        self.pc.set_dispatcher(self.dispatcher)
        self.pc.set_screen_manager(self.screen)

    def tearDown(self):
        Settings._instance = None
        self.pc.stop()

    def test_no_tip_returns(self):
        hand = HandData(landmarks=[], finger_states={})
        self.pc._move_cursor(hand)
        self.dispatcher.mouse.move_smoothed.assert_not_called()

    def test_moves_cursor_to_mapped_point(self):
        self.dispatcher.map_fingertip_to_screen.return_value = (960.0, 540.0)
        self.dispatcher.apply_cursor_settings.return_value = (961.0, 541.0)
        self.pc._move_cursor(_hand(index_tip=(0.5, 0.3)))
        self.dispatcher.mouse.move_smoothed.assert_called_once_with((961.0, 541.0))
        self.assertEqual(self.pc._last_cursor_pos, (961.0, 541.0))

    def test_screen_manager_used(self):
        self.dispatcher.map_fingertip_to_screen.return_value = (1.0, 2.0)
        self.dispatcher.apply_cursor_settings.return_value = (1.0, 2.0)
        self.pc._move_cursor(_hand(index_tip=(0.5, 0.3)))
        self.screen.get_screen_size.assert_called()

    def test_screen_size_default_when_no_manager(self):
        pc2, _bus2 = _fresh_controller()
        disp = Mock()
        disp.map_fingertip_to_screen.return_value = (960.0, 540.0)
        disp.apply_cursor_settings.return_value = (960.0, 540.0)
        pc2.set_dispatcher(disp)
        try:
            pc2._move_cursor(_hand(index_tip=(0.5, 0.3)))
            disp.map_fingertip_to_screen.assert_called_once_with((0.5, 0.3), (1920, 1080))
        finally:
            Settings._instance = None
            pc2.stop()

    def test_dead_zone_and_screen_height_passed_through(self):
        self.dispatcher.map_fingertip_to_screen.return_value = (960.0, 540.0)
        self.dispatcher.apply_cursor_settings.return_value = (961.0, 541.0)
        self.pc._move_cursor(_hand(index_tip=(0.5, 0.3)))
        kwargs = self.dispatcher.apply_cursor_settings.call_args.kwargs
        self.assertEqual(kwargs["dead_zone"], 0.005)
        self.assertEqual(kwargs["screen_height"], 1080)

    def test_one_euro_filter_engaged_when_enabled(self):
        self.pc.settings.set("cursor.one_euro", True)
        self.assertIsNone(self.pc._one_euro)
        self.dispatcher.map_fingertip_to_screen.return_value = (500.0, 300.0)
        self.dispatcher.apply_cursor_settings.return_value = (500.0, 300.0)
        self.pc._move_cursor(_hand(index_tip=(0.3, 0.3)))
        self.assertIsNotNone(self.pc._one_euro)
        self.dispatcher.map_fingertip_to_screen.assert_called()

    def test_one_euro_reset_when_disabled(self):
        self.pc.settings.set("cursor.one_euro", True)
        self.dispatcher.map_fingertip_to_screen.return_value = (500.0, 300.0)
        self.dispatcher.apply_cursor_settings.return_value = (500.0, 300.0)
        self.pc._move_cursor(_hand(index_tip=(0.3, 0.3)))
        self.assertIsNotNone(self.pc._one_euro)
        self.pc.settings.set("cursor.one_euro", False)
        self.pc._move_cursor(_hand(index_tip=(0.3, 0.3)))
        self.assertIsNone(self.pc._one_euro)

    def test_position_sink_receives_moved_pos(self):
        sink = Mock()
        self.pc.set_position_sink(sink)
        self.dispatcher.map_fingertip_to_screen.return_value = (960.0, 540.0)
        self.dispatcher.apply_cursor_settings.return_value = (961.0, 541.0)
        self.pc._move_cursor(_hand(index_tip=(0.5, 0.3)))
        sink.assert_called_once_with((961.0, 541.0))


class TestHandleTouchAction(unittest.TestCase):
    def setUp(self):
        self.pc, self.bus = _fresh_controller()
        self.dispatcher = Mock()
        self.pc.set_dispatcher(self.dispatcher)

    def tearDown(self):
        Settings._instance = None
        self.pc.stop()

    def _fake_vt(self, action=None, active=False, drag_delta=None):
        vt = Mock()
        vt.action = action
        vt.is_virtual_touch_active = active
        vt.drag_delta = drag_delta
        return vt

    def test_tap_sets_position_and_clicks(self):
        vt = self._fake_vt(action="tap", active=True)
        self.pc._handle_touch_action(vt, (500, 400))
        self.dispatcher.mouse.set_position.assert_called_once_with(500, 400)
        self.dispatcher.mouse.left_click.assert_called_once()

    def test_tap_without_position_still_clicks(self):
        vt = self._fake_vt(action="tap", active=True)
        self.pc._handle_touch_action(vt, None)
        self.dispatcher.mouse.set_position.assert_not_called()
        self.dispatcher.mouse.left_click.assert_called_once()

    def test_long_press_holds_left(self):
        vt = self._fake_vt(action="long_press")
        self.pc._handle_touch_action(vt, None)
        self.dispatcher.mouse.mouse_down.assert_called_once_with("left")

    def test_long_press_end_releases(self):
        vt = self._fake_vt(action="long_press_end")
        self.pc._handle_touch_action(vt, None)
        self.dispatcher.mouse.mouse_up.assert_called_once_with("left")

    def test_drag_start(self):
        vt = self._fake_vt(action="drag_start")
        self.pc._handle_touch_action(vt, (100, 100))
        self.dispatcher.mouse.drag_start.assert_called_once_with(100, 100)

    def test_drag_end(self):
        vt = self._fake_vt(action="drag_end")
        self.pc._handle_touch_action(vt, None)
        self.dispatcher.mouse.drag_end.assert_called_once()

    def test_drag_move_uses_delta(self):
        self.pc._last_cursor_pos = (100, 100)
        vt = self._fake_vt(action=None, drag_delta=(0.5, -0.25))
        self.pc._handle_touch_action(vt, None)
        pos = self.pc._last_cursor_pos
        self.assertAlmostEqual(pos[0], 100 + 0.5 * 100)
        self.assertAlmostEqual(pos[1], 100 + (-0.25) * 100)
        self.dispatcher.mouse.move_smoothed.assert_called()

    def test_no_dispatcher_returns(self):
        pc2, bus2 = _fresh_controller()  # no dispatcher set
        vt = self._fake_vt(action="tap", active=True)
        try:
            pc2._handle_touch_action(vt, (1, 2))  # no crash
            self.assertTrue(True)
        finally:
            Settings._instance = None


class TestPipelineLoop(unittest.TestCase):
    def setUp(self):
        self.pc, self.bus = _fresh_controller()

    def tearDown(self):
        Settings._instance = None
        self.pc.stop()

    @staticmethod
    def _frame_gen(hand, n: int = 3):
        """Return `hand` for the first `n` grabs, then None forever."""
        count = {"i": 0}

        def gen():
            count["i"] += 1
            return hand if count["i"] <= n else None

        return gen

    def _wire_components(self, hand=_hand()):
        cam = Mock()
        cam.grab.side_effect = self._frame_gen(hand)
        tracker = Mock()
        tracker.process_frame.return_value = hand
        dispatcher = Mock()
        dispatcher.map_fingertip_to_screen.return_value = (960.0, 540.0)
        dispatcher.apply_cursor_settings.return_value = (960.0, 540.0)
        screen = Mock()
        screen.get_screen_size.return_value = (1920, 1080)
        self.pc.set_camera(cam)
        self.pc.set_tracker(tracker)
        self.pc.set_dispatcher(dispatcher)
        self.pc.set_screen_manager(screen)
        return cam, tracker, dispatcher, screen

    def _wait_for(self, condition, timeout=2.0):
        deadline = time.time() + timeout
        while time.time() < deadline:
            if condition():
                return True
            time.sleep(0.02)
        return False

    def test_loop_emits_hand_detected_and_moves_cursor(self):
        cam, tracker, dispatcher, screen = self._wire_components()
        seen = []
        self.bus.subscribe(EventType.HAND_DETECTED,
                           lambda e: seen.append(e.data.get("hand")))
        self.pc.start()
        ok = self._wait_for(lambda: len(seen) > 0)
        self.assertTrue(ok, "HAND_DETECTED was never emitted")
        self.assertEqual(len(seen), 1)
        self.assertIsNotNone(dispatcher.mouse.move_smoothed.call_args)

    def test_loop_emits_hand_lost_when_tracker_returns_none(self):
        cam = Mock()
        cam.grab.side_effect = self._frame_gen(object(), n=5)
        tracker = Mock()
        tracker.process_frame.return_value = None
        self.pc.set_camera(cam)
        self.pc.set_tracker(tracker)
        lost = []
        self.bus.subscribe(EventType.HAND_LOST, lambda e: lost.append(1))
        self.pc.start()
        ok = self._wait_for(lambda: len(lost) > 0)
        self.assertTrue(ok, "HAND_LOST was never emitted")

    def test_virtual_touch_mode_engine_driven(self):
        hand = _hand(index_tip=(0.5, 0.3), tip_z=-0.1, mcp_z=0.0)
        self.pc.state.update(mode=Mode.VIRTUAL_TOUCH)
        cam, tracker, dispatcher, screen = self._wire_components(hand=hand)
        vte = VirtualTouchEngine(touch_threshold_ms=10, hold_threshold_ms=50)
        self.pc.set_virtual_touch_engine(vte)
        self.pc.start()
        # is_virtual_touch returns True (tip much closer than MCP), so the
        # engine should leave IDLE and start approaching.
        ok = self._wait_for(lambda: vte.state != TouchState.IDLE)
        self.assertTrue(ok, f"virtual touch engine never advanced (state={vte.state})")

    def test_no_air_mouse_move_in_virtual_touch_mode(self):
        hand = _hand(index_tip=(0.5, 0.3), tip_z=-0.1, mcp_z=0.0)
        self.pc.state.update(mode=Mode.VIRTUAL_TOUCH)
        cam, tracker, dispatcher, screen = self._wire_components(hand=hand)
        vte = VirtualTouchEngine(touch_threshold_ms=0.0, hold_threshold_ms=1000)
        self.pc.set_virtual_touch_engine(vte)
        self.pc.start()
        ok = self._wait_for(lambda: dispatcher.mouse.left_click.called)
        self.assertTrue(ok, "virtual touch tap never fired")
        # The air-mouse `_move_cursor` path must be skipped in VT mode.
        dispatcher.mouse.move_smoothed.assert_not_called()

    def test_virtual_touch_depth_detection(self):
        hand = _hand(index_tip=(0.5, 0.3), tip_z=-0.05, mcp_z=0.0)
        vte = VirtualTouchEngine()
        self.assertTrue(vte.is_virtual_touch(hand))

    def test_virtual_touch_depth_not_touching_when_far(self):
        hand = _hand(index_tip=(0.5, 0.3), tip_z=0.02, mcp_z=0.0)
        vte = VirtualTouchEngine()
        self.assertFalse(vte.is_virtual_touch(hand))


class TestKeyboardResolution(unittest.TestCase):
    def test_common_keys_resolve(self):
        from app.windows_input.keyboard import _resolve_vk
        for key in ("ctrl", "alt", "shift", "win", "enter", "space", "tab",
                    "up", "down", "left", "right", "f11", "volume_up", "a", "1"):
            self.assertIsNotNone(_resolve_vk(key), key)

    def test_unknown_key_returns_none(self):
        from app.windows_input.keyboard import _resolve_vk
        self.assertIsNone(_resolve_vk("not-a-key"))

    def test_shortcut_table_sane(self):
        from app.windows_input.keyboard import WINDOWS_SHORTCUTS
        self.assertIn("alt_tab", WINDOWS_SHORTCUTS)
        self.assertEqual(WINDOWS_SHORTCUTS["ctrl_alt_del"], ["ctrl", "alt", "delete"])


class TestKeyboardPress(unittest.TestCase):
    def _kc(self):
        from unittest.mock import Mock
        from app.windows_input.keyboard import KeyboardController
        kc = KeyboardController()
        kc.key_press = Mock()
        kc.type_text = Mock()
        return kc

    def test_press_returns_false_for_empty(self):
        kc = self._kc()
        self.assertFalse(kc.press_key(""))
        kc.key_press.assert_not_called()
        kc.type_text.assert_not_called()

    def test_press_key_vk_path(self):
        kc = self._kc()
        kc.press_key("a")
        kc.key_press.assert_called_once()
        kc.type_text.assert_not_called()

    def test_press_key_unicode_fallback(self):
        kc = self._kc()
        emoji = u"\U0001f600"
        kc.press_key(emoji)
        kc.key_press.assert_not_called()
        kc.type_text.assert_called_once_with(emoji)

    def test_press_key_symbol_fallback(self):
        kc = self._kc()
        kc.press_key("@")
        kc.key_press.assert_not_called()
        kc.type_text.assert_called_once_with("@")


class TestCalibrationFeed(unittest.TestCase):
    def setUp(self):
        self.pc, self.bus = _fresh_controller()
        from app.calibration.calibrator import Calibrator, CalibState
        self.cal = Calibrator(screen_width=1920, screen_height=1080)
        # Bypass the ~1s hold requirement for deterministic tests.
        self.cal._hold_time_ms = 0.0
        self.pc.set_calibrator(self.cal)

    def tearDown(self):
        Settings._instance = None
        self.pc.stop()

    def _wire(self, hand=_hand(index_tip=(0.5, 0.3))):
        cam = Mock()
        cam.grab.side_effect = self._frame_gen(hand)
        tracker = Mock()
        tracker.process_frame.return_value = hand
        self.pc.set_camera(cam)
        self.pc.set_tracker(tracker)

    @staticmethod
    def _frame_seq(tips):
        """Yield a hand with the given fingertip positions, then None forever."""
        state = {"i": 0}

        def gen(_frame=None):
            idx = state["i"]
            state["i"] += 1
            if idx < len(tips):
                return _hand(index_tip=tips[idx],
                             tip_z=-0.1 + idx * 0.001, mcp_z=0.0)
            return None

        return gen

    @staticmethod
    def _frame_gen(hand):
        while True:
            yield hand

    def _wait_for(self, condition, timeout=2.0):
        deadline = time.time() + timeout
        while time.time() < deadline:
            if condition():
                return True
            time.sleep(0.02)
        return False

    def test_feed_produces_calibration_complete(self):
        from app.core.state import AppStatus
        from app.calibration.calibrator import CalibState
        self.cal.start()
        self.pc.state.update(status=AppStatus.CALIBRATING)
        steps = []
        complete = []
        self.bus.subscribe(EventType.CALIBRATION_STEP,
                           lambda e: steps.append(e.data.get("corner")))
        self.bus.subscribe(EventType.CALIBRATION_COMPLETE,
                           lambda e: complete.append(e.data.get("result")))
        tips = [(0.2, 0.2), (0.8, 0.2), (0.8, 0.8), (0.2, 0.8)]
        cam = Mock()
        cam.grab.side_effect = self._frame_seq(tips)
        tracker = Mock()
        tracker.process_frame.side_effect = self._frame_seq(tips)
        self.pc.set_camera(cam)
        self.pc.set_tracker(tracker)
        self.pc.start()
        ok = self._wait_for(lambda: len(complete) > 0)
        self.assertTrue(ok, "CALIBRATION_COMPLETE never emitted")
        self.assertEqual(len(steps), 4)
        self.assertEqual(self.cal.state, CalibState.DONE)
        self.assertIsNotNone(complete[0].homography)

    def test_no_calibration_when_not_calibrating(self):
        from app.core.state import AppStatus
        self.cal.start()
        self.pc.state.update(status=AppStatus.RUNNING)
        steps = []
        self.bus.subscribe(EventType.CALIBRATION_STEP,
                           lambda e: steps.append(1))
        self._wire()
        self.pc.start()
        time.sleep(0.3)
        self.assertEqual(len(steps), 0)

    def test_feed_ignores_missing_fingertip(self):
        from app.calibration.calibrator import CalibState
        self.cal.start()
        self.pc.state.update(status=AppStatus.CALIBRATING)
        self.pc._feed_calibration(HandData(landmarks=[], finger_states={}))
        self.assertEqual(self.cal.step, 0)
        self.assertEqual(self.cal.state, CalibState.TOP_LEFT)


class TestQualityMonitor(unittest.TestCase):
    def setUp(self):
        self.pc, self.bus = _fresh_controller()

    def tearDown(self):
        Settings._instance = None
        self.pc.stop()

    def test_quality_updated_in_running_loop(self):
        from app.core.state import AppStatus, Mode
        from app.tracking.quality import TrackingQualityMonitor
        mon = TrackingQualityMonitor(min_confidence=0.0)
        self.pc.set_quality_monitor(mon)
        hand = _hand()
        # All landmarks have visibility 0.9 and confidence 0.9 -> GOOD/EXCELLENT
        cam = Mock()
        cam.grab.side_effect = (hand for _ in iter(int, 1))
        tracker = Mock()
        tracker.process_frame.return_value = hand
        self.pc.set_camera(cam)
        self.pc.set_tracker(tracker)
        self.pc.state.update(status=AppStatus.RUNNING)
        self.pc.start()
        deadline = time.time() + 2.0
        while time.time() < deadline and not self.pc.state.stats.tracking_quality:
            time.sleep(0.02)
        self.assertIn(self.pc.state.stats.tracking_quality,
                      ("good", "excellent", "warning"))

    def test_no_quality_eval_while_calibrating(self):
        from app.core.state import AppStatus
        mon = Mock()
        mon.evaluate.return_value = Mock(level=Mock(value="good"))
        self.pc.set_quality_monitor(mon)
        hand = _hand()
        cam = Mock()
        cam.grab.side_effect = (hand for _ in iter(int, 1))
        tracker = Mock()
        tracker.process_frame.return_value = hand
        self.pc.set_camera(cam)
        self.pc.set_tracker(tracker)
        self.pc.state.update(status=AppStatus.CALIBRATING)
        self.pc.start()
        time.sleep(0.25)
        self.pc.stop()
        mon.evaluate.assert_not_called()


if __name__ == "__main__":
    unittest.main()