"""Input dispatcher – bridges pipeline/gesture events to Windows input control.

This is the final stage of the interaction pipeline:
  Gesture/State signals -> InputDispatcher -> MouseController / KeyboardController
"""
from __future__ import annotations

import logging
import time
from typing import TYPE_CHECKING, Optional

from app.core.events import Event, EventBus, EventType
from app.core.state import Mode

if TYPE_CHECKING:
    from app.windows_input.mouse import MouseController
    from app.windows_input.keyboard import KeyboardController
    from app.calibration.calibrator import Calibrator
    from app.config import Settings

_LOG = logging.getLogger(__name__)


class InputDispatcher:
    """Subscribes to HADJ events and translates them into mouse/keyboard actions."""

    def __init__(
        self,
        bus: EventBus,
        mouse_ctrl: MouseController,
        kb_ctrl: KeyboardController,
        calibrator: Calibrator,
        settings: Settings,
    ) -> None:
        self.bus = bus
        self.mouse = mouse_ctrl
        self.keyboard = kb_ctrl
        self.calibrator = calibrator
        self.settings = settings
        self.mode: Mode = Mode.AIR_MOUSE

        # Debounce / cooldown state
        self._click_cooldown_until: float = 0.0
        self._last_drag_text_ts: float = 0.0
        self._click_guard_pos: tuple[float, float] | None = None

        # Cursor mapping state
        self._last_screen_point: tuple[float, float] | None = None

        self._wire_events()

    # -- cursor position mapping (pure logic, testable) --

    def map_fingertip_to_screen(
        self,
        fingertip: tuple[float, float],
        screen_size: tuple[int, int],
    ) -> tuple[float, float]:
        """Map a normalised camera-space fingertip to screen pixel coordinates.

        Uses the calibration homography when available; otherwise falls back to
        a linear (no-perspective) mapping. Returns (x, y) in screen pixels.
        """
        if self.calibrator.result.homography is not None:
            mapped = self.calibrator.map_camera_to_screen(fingertip)
            if mapped is not None:
                self._last_screen_point = mapped
                return mapped

        w, h = screen_size
        mapped = (fingertip[0] * w, fingertip[1] * h)
        self._last_screen_point = mapped
        return mapped

    def apply_cursor_settings(
        self,
        screen_point: tuple[float, float],
        mouse_pos: tuple[float, float],
        speed: float = 1.0,
        smoothing: float = 0.5,
        acceleration: float = 1.0,
        dead_zone: float = 0.0,
        screen_height: int = 1080,
        screen_size: tuple[int, int] | None = None,
    ) -> tuple[float, float]:
        """Apply sensitivity + exponential smoothing towards a target position.

        ``dead_zone`` is a fraction of the screen height: sub-threshold deltas
        are ignored entirely, so a still hand produces zero cursor drift.
        ``screen_size`` clamps the result to the visible desktop so a slightly
        out-of-bounds fingertip never pushes the cursor off-screen.
        """
        delta_x = screen_point[0] - mouse_pos[0]
        delta_y = screen_point[1] - mouse_pos[1]

        # Dead zone – absorb micro-jitter when the hand is (nearly) still
        if dead_zone > 0.0:
            dz_px = dead_zone * max(1.0, float(screen_height))
            if (delta_x ** 2 + delta_y ** 2) ** 0.5 <= dz_px:
                return mouse_pos

        # Acceleration – amplify larger movements
        dist = (delta_x ** 2 + delta_y ** 2) ** 0.5
        gain = speed * (1.0 + (acceleration - 1.0) * min(1.0, dist / 500.0))

        alpha = min(1.0, max(0.0, smoothing))
        dx = delta_x * gain * (1.0 - alpha) if alpha < 1.0 else delta_x * gain
        dy = delta_y * gain * (1.0 - alpha) if alpha < 1.0 else delta_y * gain
        result = (mouse_pos[0] + dx, mouse_pos[1] + dy)

        # Keep the cursor on the visible desktop
        if screen_size is not None:
            sw, sh = screen_size
            result = (
                max(0.0, min(float(sw), result[0])),
                max(0.0, min(float(sh), result[1])),
            )
        return result

    # -- event wiring --

    def _wire_events(self) -> None:
        self.bus.subscribe(EventType.MOUSE_CLICK, self._on_mouse_click)
        self.bus.subscribe(EventType.MOUSE_DOUBLE_CLICK, self._on_double_click)
        self.bus.subscribe(EventType.MOUSE_RIGHT_CLICK, self._on_right_click)
        self.bus.subscribe(EventType.MOUSE_SCROLL, self._on_scroll)
        self.bus.subscribe(EventType.KEYBOARD_SHORTCUT, self._on_keyboard_shortcut)
        self.bus.subscribe(EventType.TOUCH_DOWN, self._on_touch_down)
        self.bus.subscribe(EventType.TOUCH_UP, self._on_touch_up)
        self.bus.subscribe(EventType.DRAG_START, self._on_drag_start)
        self.bus.subscribe(EventType.DRAG_END, self._on_drag_end)

    def _on_mouse_click(self, event: Event) -> None:
        self.mouse.left_click()

    def _on_double_click(self, event: Event) -> None:
        self.mouse.double_click()

    def _on_right_click(self, event: Event) -> None:
        self.mouse.right_click()

    def _on_scroll(self, event: Event) -> None:
        delta = event.data.get("delta", 3)
        self.mouse.scroll(int(delta))

    def _on_keyboard_shortcut(self, event: Event) -> None:
        keys = event.data.get("keys", [])
        if not keys:
            return
        action = keys[0] if len(keys) == 1 else keys

        # Media / volume single keys
        single_key_actions = {
            "volume_up": lambda: self.keyboard.volume_up(),
            "volume_down": lambda: self.keyboard.volume_down(),
            "volume_mute": lambda: self.keyboard.volume_mute(),
            "media_play_pause": lambda: self.keyboard.media_play_pause(),
            "media_next": lambda: self.keyboard.media_next(),
            "media_prev": lambda: self.keyboard.media_prev(),
        }
        if isinstance(action, str) and action in single_key_actions:
            single_key_actions[action]()
            return

        if isinstance(keys, list) and len(keys) > 1:
            self.keyboard.hotkey(*keys)
        elif isinstance(action, str):
            self.keyboard.key_press(action)

    def _on_touch_down(self, event: Event) -> None:
        self.mouse.mouse_down("left")

    def _on_touch_up(self, event: Event) -> None:
        self.mouse.mouse_up("left")

    def _on_drag_start(self, event: Event) -> None:
        pos = event.data.get("position", self._last_screen_point)
        if pos is not None:
            self.mouse.drag_start(pos[0], pos[1])

    def _on_drag_end(self, event: Event) -> None:
        self.mouse.drag_end()

    # -- gesture-driven actions --

    def handle_gesture(self, gesture_name: str) -> None:
        """Translate a profile-mapped gesture name into a mouse/keyboard action."""
        from app.gestures.mapping import gesture_action_lookup  # noqa: PLC0415
        action = gesture_action_lookup(gesture_name, self.settings.config.active_profile)
        if action is None:
            return

        now = time.perf_counter()
        if now < self._click_cooldown_until:
            return

        handler = {
            "left_click": self.mouse.left_click,
            "double_click": self.mouse.double_click,
            "right_click": self.mouse.right_click,
            "scroll_up": lambda: self.mouse.scroll(3),
            "scroll_down": lambda: self.mouse.scroll(-3),
            "zoom_in": lambda: self.keyboard.key_press("ctrl"),
            "zoom_out": lambda: self.keyboard.key_press("ctrl"),
            "back": lambda: self.keyboard.hotkey("alt", "left"),
            "forward": lambda: self.keyboard.hotkey("alt", "right"),
            "previous_slide": lambda: self.keyboard.key_press("up"),
            "next_slide": lambda: self.keyboard.key_press("down"),
            "previous_track": lambda: self.keyboard.media_prev(),
            "next_track": lambda: self.keyboard.media_next(),
            "play_pause": lambda: self.keyboard.media_play_pause(),
            "volume_up": lambda: self.keyboard.volume_up(),
            "volume_down": lambda: self.keyboard.volume_down(),
            "pause": lambda: self._noop(),
            "resume": lambda: self._noop(),
            "laser_pointer": lambda: self._noop(),
            "close": lambda: self.keyboard.hotkey("alt", "f4"),
            "open_browser": lambda: self.keyboard.hotkey("win", "d"),
            "undo": lambda: self.keyboard.hotkey("ctrl", "z"),
            "redo": lambda: self.keyboard.hotkey("ctrl", "y"),
            "save": lambda: self.keyboard.hotkey("ctrl", "s"),
            "select_all": lambda: self.keyboard.hotkey("ctrl", "a"),
            "copy": lambda: self.keyboard.ctrl_c(),
            "cut": lambda: self.keyboard.hotkey("ctrl", "x"),
            "paste": lambda: self.keyboard.ctrl_v(),
            "new_tab": lambda: self.keyboard.hotkey("ctrl", "t"),
            "close_tab": lambda: self.keyboard.hotkey("ctrl", "w"),
            "reopen_tab": lambda: self.keyboard.hotkey("ctrl", "shift", "t"),
            "switch_tab_next": lambda: self.keyboard.hotkey("ctrl", "tab"),
            "switch_tab_prev": lambda: self.keyboard.hotkey("ctrl", "shift", "tab"),
            "minimize_window": lambda: self.keyboard.hotkey("win", "down"),
            "maximize_window": lambda: self.keyboard.hotkey("win", "up"),
            "show_desktop": lambda: self.keyboard.hotkey("win", "d"),
            "lock_screen": lambda: self.keyboard.hotkey("win", "l"),
            "screenshot": lambda: self.keyboard.hotkey("win", "shift", "s"),
            "volume_mute": lambda: self.keyboard.volume_mute(),
        }.get(action)

        if handler is None:
            return

        # Cooldown for repeated gestures
        if action in ("left_click", "right_click", "scroll_up", "scroll_down"):
            self._click_cooldown_until = now + self.settings.config.safety.click_cooldown_ms / 1000.0

        _LOG.debug("Dispatcher action: %s (from gesture %s)", action, gesture_name)
        handler()

    @staticmethod
    def _noop() -> None:
        pass