"""Tests for services and support modules (profiles, assistant, quality,
virtual keyboard, voice mapping, app state, finger-state heuristics,
camera/screen managers, privacy guard).

All tests run without third-party packages (OpenCV / MediaPipe / Qt / vosk).
"""
from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock

from app.tracking.models import HandData, Landmark2D, FingerState
from app.tracking.models import INDEX_PIP, INDEX_TIP, THUMB_MCP, THUMB_TIP


def _full_hand(confidence: float = 0.9, visibility: float = 0.9) -> HandData:
    return HandData(
        landmarks=[Landmark2D(i, 0.5, 0.5, 0.0, visibility) for i in range(21)],
        confidence=confidence,
        finger_states={},
    )


# ---------------------------------------------------------------------------
# Profile manager
# ---------------------------------------------------------------------------

class TestProfileManager(unittest.TestCase):
    def setUp(self):
        from app.profiles.manager import ProfileManager
        self._tmp = tempfile.TemporaryDirectory()
        self.pm = ProfileManager(config_dir=Path(self._tmp.name))

    def tearDown(self):
        self._tmp.cleanup()

    def test_builtin_profiles_present(self):
        for name in ("general", "browser", "presentation", "media", "cad", "accessibility"):
            self.assertIn(name, self.pm.all_names)

    def test_default_active_is_general(self):
        self.assertEqual(self.pm.active_name, "general")
        self.assertEqual(self.pm.get_active().name, "general")

    def test_set_active_known(self):
        self.assertTrue(self.pm.set_active("browser"))
        self.assertEqual(self.pm.active_name, "browser")
        self.assertEqual(self.pm.get_active().name, "browser")

    def test_set_active_unknown(self):
        self.assertFalse(self.pm.set_active("nope"))
        self.assertEqual(self.pm.active_name, "general")

    def test_get_profile(self):
        p = self.pm.get_profile("cad")
        self.assertIsNotNone(p)
        self.assertAlmostEqual(p.cursor_speed, 0.7)
        self.assertIsNone(self.pm.get_profile("does_not_exist"))

    def test_profile_dict_round_trip(self):
        p = self.pm.get_profile("media")
        clone = type(p).from_dict(p.to_dict())
        self.assertEqual(clone.name, p.name)
        self.assertEqual(clone.gestures, p.gestures)
        self.assertEqual(clone.trigger_apps, p.trigger_apps)

    def test_custom_profile_loaded(self):
        from app.profiles.manager import ProfileManager
        custom = {"myapp": {"name": "myapp", "description": "custom", "cursor_speed": 0.3}}
        (Path(self._tmp.name) / "profiles.json").write_text(
            json.dumps(custom), encoding="utf-8"
        )
        pm2 = ProfileManager(config_dir=Path(self._tmp.name))
        self.assertIn("myapp", pm2.all_names)
        self.assertEqual(pm2.get_profile("myapp").cursor_speed, 0.3)

    def test_missing_config_dir_is_safe(self):
        from app.profiles.manager import ProfileManager
        pm = ProfileManager(config_dir=None)
        self.assertIn("general", pm.all_names)


# ---------------------------------------------------------------------------
# HADJ AI assistant
# ---------------------------------------------------------------------------

class TestHadjAI(unittest.TestCase):
    def setUp(self):
        from app.assistant.hadj_ai import HadjAI
        self.ai = HadjAI()

    def test_known_topic(self):
        text = self.ai.get_tip("calibration_start")
        self.assertIn("Calibration", text)

    def test_unknown_topic_fallback(self):
        text = self.ai.get_tip("not_a_topic")
        self.assertIn("don't have a tip", text)

    def test_format_kwargs(self):
        text = self.ai.get_tip("calibration_done", quality=0.9)
        self.assertIn("90%", text)

    def test_missing_format_kwarg_is_safe(self):
        # Should not raise even if format arg is missing.
        text = self.ai.get_tip("calibration_done")
        self.assertIsInstance(text, str)

    def test_diagnose_hand_not_visible(self):
        self.assertIn("tracking lost", self.ai.diagnose("POOR", 0.1, hand_visible=False).lower())

    def test_diagnose_low_confidence(self):
        msg = self.ai.diagnose("GOOD", 0.2, hand_visible=True)
        self.assertIn("confidence", msg.lower())

    def test_diagnose_poor(self):
        msg = self.ai.diagnose("POOR", 0.9, hand_visible=True)
        self.assertIn("confidence", msg.lower())

    def test_diagnose_warning(self):
        msg = self.ai.diagnose("WARNING", 0.9, hand_visible=True)
        self.assertIn("not optimal", msg.lower())

    def test_diagnose_excellent(self):
        msg = self.ai.diagnose("EXCELLENT", 0.95, hand_visible=True)
        self.assertIn("looks good", msg.lower())

    def test_list_topics(self):
        topics = self.ai.list_topics()
        self.assertIn("camera_position", topics)
        self.assertEqual(topics, sorted(topics))


# ---------------------------------------------------------------------------
# Tracking quality monitor
# ---------------------------------------------------------------------------

class TestTrackingQuality(unittest.TestCase):
    def setUp(self):
        from app.tracking.quality import TrackingQualityMonitor
        self.mon = TrackingQualityMonitor(min_confidence=0.5)

    def test_no_hand(self):
        report = self.mon.evaluate(None)
        self.assertEqual(report.level.value, "poor")
        self.assertEqual(report.score, 0.0)
        self.assertFalse(report.hand_visible)
        self.assertTrue(report.recommendations)

    def test_excellent_hand(self):
        report = self.mon.evaluate(_full_hand(confidence=0.95, visibility=0.95))
        self.assertEqual(report.level.value, "excellent")
        self.assertGreaterEqual(report.score, 0.85)
        self.assertTrue(report.confidence_ok)

    def test_low_confidence_penalised(self):
        report = self.mon.evaluate(_full_hand(confidence=0.2, visibility=0.9))
        self.assertLess(report.score, 0.6)
        self.assertFalse(report.confidence_ok)
        self.assertTrue(any("confidence" in r.lower() for r in report.recommendations))

    def test_few_landmarks_penalised(self):
        hand = _full_hand(confidence=0.95, visibility=0.1)
        report = self.mon.evaluate(hand)
        self.assertLess(report.score, 0.85)
        self.assertTrue(any("landmarks" in r.lower() for r in report.recommendations))

    def test_tips_not_visible(self):
        hand = _full_hand(confidence=0.95, visibility=0.95)
        # Hide the five fingertip landmarks
        for i in (4, 8, 12, 16, 20):
            hand.landmarks[i].visibility = 0.0
        report = self.mon.evaluate(hand)
        self.assertTrue(any("fingertip" in r.lower() for r in report.recommendations))


# ---------------------------------------------------------------------------
# Virtual keyboard
# ---------------------------------------------------------------------------

class TestVirtualKeyboard(unittest.TestCase):
    def setUp(self):
        from app.keyboard.virtual_keyboard import VirtualKeyboard, KeyboardLayout
        self.vk = VirtualKeyboard()
        self.Layout = KeyboardLayout

    def test_default_layout_has_rows(self):
        self.assertEqual(self.vk.layout, self.Layout.QWERTY_EN)
        self.assertGreaterEqual(len(self.vk.keys), 5)

    def test_all_layouts_present(self):
        for layout in self.Layout:
            self.vk.set_layout(layout)
            self.assertTrue(self.vk.keys)

    def test_qwerty_contains_space_and_enter(self):
        codes = {k.code for row in self.vk.keys for k in row}
        self.assertIn("space", codes)
        self.assertIn("enter", codes)
        self.assertIn("backspace", codes)

    def test_set_layout_changes_keys(self):
        self.vk.set_layout(self.Layout.EMOJI)
        self.assertEqual(self.vk.layout, self.Layout.EMOJI)
        labels = {k.label for row in self.vk.keys for k in row}
        self.assertIn(u"\U0001f44d", labels)  # thumbs-up
        codes = {k.code for row in self.vk.keys for k in row}
        self.assertIn(u"\U0001f44d", codes)

    def test_numbers_symbols_layout(self):
        self.vk.set_layout(self.Layout.NUMBERS_SYMBOLS)
        codes = {k.code for row in self.vk.keys for k in row}
        for sym in ["1", "0", "!", "@", "#", "$", "%", "^", "&", "*", "(", ")", "_", "+",
                    "[", "]", "{", "}", ";", ":", "'", '"', ".", ",", "/", "-", "=", "\\"]:
            self.assertIn(sym, codes, f"missing {sym!r}")
        self.assertIn("space", codes)
        self.assertIn("backspace", codes)

    def test_emoji_codes_are_typeable_chars(self):
        self.vk.set_layout(self.Layout.EMOJI)
        for row in self.vk.keys:
            for key in row:
                self.assertEqual(key.label, key.code)
                self.assertGreater(len(key.code), 0)

    def test_available_layouts_lists_all(self):
        self.assertEqual(set(self.vk.available_layouts), set(self.Layout))

    def test_key_widths_positive(self):
        for row in self.vk.keys:
            for key in row:
                self.assertGreaterEqual(key.width, 1)


# ---------------------------------------------------------------------------
# Voice controller (no vosk -> command mapping still works)
# ---------------------------------------------------------------------------

class TestVoiceController(unittest.TestCase):
    def setUp(self):
        from app.core.events import EventBus
        from app.voice.controller import VoiceController
        self.bus = EventBus()
        self.vc = VoiceController(self.bus, language="en")
        self.received = []
        self.bus.subscribe  # noqa: B018 – warm attribute
        from app.core.events import EventType
        for et in EventType:
            self.bus.subscribe(et, lambda e, r=self.received: r.append(e))

    def test_not_available_without_vosk(self):
        self.assertFalse(self.vc.available)
        self.assertFalse(self.vc.start())

    def test_click_emits_mouse_click(self):
        from app.core.events import EventType
        self.vc._handle_text("click")
        self.assertTrue(any(e.type == EventType.MOUSE_CLICK for e in self.received))

    def test_double_click(self):
        from app.core.events import EventType
        self.vc._handle_text("double click")
        self.assertTrue(any(e.type == EventType.MOUSE_DOUBLE_CLICK for e in self.received))

    def test_scroll_mapping(self):
        from app.core.events import EventType
        self.vc._handle_text("scroll up")
        scrolls = [e for e in self.received if e.type == EventType.MOUSE_SCROLL]
        self.assertEqual(scrolls[-1].data["delta"], 3)

    def test_pause_emits_emergency_stop(self):
        from app.core.events import EventType
        self.vc._handle_text("stop")
        self.assertTrue(any(e.type == EventType.EMERGENCY_STOP for e in self.received))

    def test_volume_command(self):
        from app.core.events import EventType
        self.vc._handle_text("volume up")
        shortcuts = [e for e in self.received if e.type == EventType.KEYBOARD_SHORTCUT]
        self.assertEqual(shortcuts[-1].data["keys"], ["volume_up"])

    def test_unknown_command_is_ignored(self):
        self.vc._handle_text("make me a sandwich")
        self.assertEqual(self.received, [])

    def test_command_callback_invoked(self):
        seen = []
        self.vc.set_command_callback(seen.append)
        self.vc._handle_text("right click")
        self.assertEqual(seen, ["right_click"])

    def test_calibrate_emits_calibration_started(self):
        from app.core.events import EventType
        self.vc._handle_text("calibrate")
        self.assertTrue(any(e.type == EventType.CALIBRATION_STARTED for e in self.received))

    def test_undo_command(self):
        from app.core.events import EventType
        self.vc._handle_text("undo")
        shortcuts = [e for e in self.received if e.type == EventType.KEYBOARD_SHORTCUT]
        self.assertEqual(shortcuts[-1].data["keys"], ["ctrl", "z"])

    def test_new_tab_command(self):
        from app.core.events import EventType
        self.vc._handle_text("new tab")
        shortcuts = [e for e in self.received if e.type == EventType.KEYBOARD_SHORTCUT]
        self.assertEqual(shortcuts[-1].data["keys"], ["ctrl", "t"])

    def test_screenshot_command(self):
        from app.core.events import EventType
        self.vc._handle_text("take screenshot")
        shortcuts = [e for e in self.received if e.type == EventType.KEYBOARD_SHORTCUT]
        self.assertEqual(shortcuts[-1].data["keys"], ["win", "shift", "s"])

    def test_save_command(self):
        from app.core.events import EventType
        self.vc._handle_text("save")
        shortcuts = [e for e in self.received if e.type == EventType.KEYBOARD_SHORTCUT]
        self.assertEqual(shortcuts[-1].data["keys"], ["ctrl", "s"])


class TestParseHotkey(unittest.TestCase):
    def test_standard_hotkey(self):
        from app.privacy.guard import parse_hotkey
        self.assertEqual(len(parse_hotkey("Ctrl+Alt+H")), 3)

    def test_single_key_hotkey(self):
        from app.privacy.guard import parse_hotkey
        self.assertEqual(len(parse_hotkey("F12")), 1)

    def test_unknown_keys_skipped(self):
        from app.privacy.guard import parse_hotkey
        self.assertEqual(len(parse_hotkey("Ctrl+NotARealKey+Q")), 2)

    def test_empty_returns_empty(self):
        from app.privacy.guard import parse_hotkey
        self.assertEqual(parse_hotkey(""), [])


# ---------------------------------------------------------------------------
# Application state
# ---------------------------------------------------------------------------

class TestAppState(unittest.TestCase):
    def test_defaults(self):
        from app.core.state import AppState, AppStatus, Mode
        s = AppState()
        self.assertEqual(s.status, AppStatus.IDLE)
        self.assertEqual(s.mode, Mode.AIR_MOUSE)
        self.assertEqual(s.stats.fps, 0.0)

    def test_update(self):
        from app.core.state import AppState, AppStatus
        s = AppState()
        s.update(status=AppStatus.RUNNING, cursor_x=100, cursor_y=200)
        self.assertEqual(s.status, AppStatus.RUNNING)
        self.assertEqual(s.cursor_x, 100)
        self.assertEqual(s.cursor_y, 200)

    def test_snapshot_is_copy(self):
        from app.core.state import AppState
        s = AppState()
        snap = s.snapshot()
        s.update(cursor_x=42)
        self.assertNotEqual(snap.cursor_x, 42)


# ---------------------------------------------------------------------------
# Finger-state heuristic
# ---------------------------------------------------------------------------

class TestFingerStates(unittest.TestCase):
    def _hand_landmarks(self, index_tip_y: float, index_pip_y: float) -> list[Landmark2D]:
        lms = [Landmark2D(i, 0.5, 0.5) for i in range(21)]
        lms[INDEX_PIP] = Landmark2D(INDEX_PIP, 0.5, index_pip_y)
        lms[INDEX_TIP] = Landmark2D(INDEX_TIP, 0.5, index_tip_y)
        return lms

    def test_extended_when_tip_above_pip(self):
        from app.tracking.hand_tracker import _compute_finger_states
        states = _compute_finger_states(self._hand_landmarks(0.2, 0.4))
        self.assertEqual(states["index"], FingerState.EXTENDED)

    def test_folded_when_tip_below_pip(self):
        from app.tracking.hand_tracker import _compute_finger_states
        states = _compute_finger_states(self._hand_landmarks(0.6, 0.4))
        self.assertEqual(states["index"], FingerState.FOLDED)

    def test_empty_landmarks(self):
        from app.tracking.hand_tracker import _compute_finger_states
        self.assertEqual(_compute_finger_states([]), {})

    def test_all_five_fingers_reported(self):
        from app.tracking.hand_tracker import _compute_finger_states
        states = _compute_finger_states(self._hand_landmarks(0.2, 0.4))
        self.assertEqual(set(states), {"thumb", "index", "middle", "ring", "pinky"})


# ---------------------------------------------------------------------------
# Camera manager (no cv2 -> simulation fallback)
# ---------------------------------------------------------------------------

class TestCameraManager(unittest.TestCase):
    def setUp(self):
        from app.camera.manager import CameraManager
        self.cm = CameraManager()

    def test_at_least_one_camera(self):
        self.assertGreaterEqual(len(self.cm.cameras), 1)

    def test_get_camera_by_index(self):
        cam = self.cm.get_camera(0)
        self.assertIsNotNone(cam)
        self.assertEqual(cam.index, 0)

    def test_get_unknown_index_returns_first(self):
        cam = self.cm.get_camera(99)
        self.assertIsNotNone(cam)

    def test_refresh(self):
        self.cm.refresh()
        self.assertGreaterEqual(len(self.cm.cameras), 1)


# ---------------------------------------------------------------------------
# Screen / monitor info
# ---------------------------------------------------------------------------

class TestMonitorInfo(unittest.TestCase):
    def test_center_and_bounds(self):
        from app.windows_input.screen import MonitorInfo
        m = MonitorInfo(index=0, name="M", left=0, top=0, width=1920, height=1080, primary=True)
        self.assertEqual(m.center, (960, 540))
        self.assertEqual(m.bounds, (0, 0, 1920, 1080))

    def test_offset_center(self):
        from app.windows_input.screen import MonitorInfo
        m = MonitorInfo(index=1, name="M2", left=1920, top=0, width=1280, height=720)
        self.assertEqual(m.center, (2560, 360))


class TestScreenManager(unittest.TestCase):
    def test_monitors_and_primary(self):
        from app.windows_input.screen import ScreenManager
        sm = ScreenManager()
        self.assertGreaterEqual(len(sm.monitors), 1)
        self.assertIsNotNone(sm.primary)

    def test_screen_size_tuple(self):
        from app.windows_input.screen import ScreenManager
        sm = ScreenManager()
        w, h = sm.get_screen_size(0)
        self.assertGreater(w, 0)
        self.assertGreater(h, 0)


# ---------------------------------------------------------------------------
# Privacy guard
# ---------------------------------------------------------------------------

class TestPrivacyGuard(unittest.TestCase):
    def setUp(self):
        from app.core.events import EventBus
        from app.privacy.guard import PrivacyGuard
        self.guard = PrivacyGuard(EventBus())

    def test_camera_indicator_toggle(self):
        self.assertFalse(self.guard.is_camera_active)
        self.guard.notify_camera_active()
        self.assertTrue(self.guard.is_camera_active)
        self.guard.notify_camera_inactive()
        self.assertFalse(self.guard.is_camera_active)

    def test_privacy_statement_local_only(self):
        text = self.guard.privacy_statement()
        self.assertIn("LOCALLY", text)
        self.assertIn("No images", text)


if __name__ == "__main__":
    unittest.main()
