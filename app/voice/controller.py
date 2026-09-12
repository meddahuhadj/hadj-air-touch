"""Optional local voice control – uses vosk if installed, else stub."""
from __future__ import annotations

import logging
import sys
import threading
from typing import Callable, Optional

from app.core.events import EventBus, EventType

_LOG = logging.getLogger(__name__)

_COMMAND_MAP: dict[str, str] = {
    "click": "left_click",
    "double click": "double_click",
    "doubleclick": "double_click",
    "right click": "right_click",
    "rightclick": "right_click",
    "scroll down": "scroll_down",
    "scroll up": "scroll_up",
    "pause": "pause",
    "resume": "resume",
    "stop": "pause",
    "start": "resume",
    "go back": "back",
    "go forward": "forward",
    "close window": "close",
    "open browser": "open_browser",
    "start calibration": "calibrate",
    "calibrate": "calibrate",
    "volume up": "volume_up",
    "volume down": "volume_down",
    "mute": "volume_mute",
    "play": "play_pause",
    "next": "next_track",
    "previous": "previous_track",
    "undo": "undo",
    "redo": "redo",
    "save": "save",
    "copy": "copy",
    "cut": "cut",
    "paste": "paste",
    "select all": "select_all",
    "new tab": "new_tab",
    "close tab": "close_tab",
    "reopen tab": "reopen_tab",
    "next tab": "switch_tab_next",
    "previous tab": "switch_tab_prev",
    "minimize": "minimize_window",
    "maximize": "maximize_window",
    "show desktop": "show_desktop",
    "lock screen": "lock_screen",
    "lock": "lock_screen",
    "screenshot": "screenshot",
    "take screenshot": "screenshot",
}

# Maps a recognised action to the keyboard shortcut it should trigger.
_ACTION_SHORTCUTS: dict[str, tuple[str, ...]] = {
    "volume_up": ("volume_up",),
    "volume_down": ("volume_down",),
    "volume_mute": ("volume_mute",),
    "play_pause": ("media_play_pause",),
    "next_track": ("media_next",),
    "previous_track": ("media_prev",),
    "back": ("alt", "left"),
    "forward": ("alt", "right"),
    "close": ("alt", "f4"),
    "open_browser": ("win", "d"),
    "show_desktop": ("win", "d"),
    "undo": ("ctrl", "z"),
    "redo": ("ctrl", "y"),
    "save": ("ctrl", "s"),
    "select_all": ("ctrl", "a"),
    "copy": ("ctrl", "c"),
    "cut": ("ctrl", "x"),
    "paste": ("ctrl", "v"),
    "new_tab": ("ctrl", "t"),
    "close_tab": ("ctrl", "w"),
    "reopen_tab": ("ctrl", "shift", "t"),
    "switch_tab_next": ("ctrl", "tab"),
    "switch_tab_prev": ("ctrl", "shift", "tab"),
    "minimize_window": ("win", "down"),
    "maximize_window": ("win", "up"),
    "lock_screen": ("win", "l"),
    "screenshot": ("win", "shift", "s"),
}


class VoiceController:
    """Listens for voice commands (when vosk is available) and emits events."""

    def __init__(self, bus: EventBus, language: str = "en") -> None:
        self.bus = bus
        self.language = language
        self._running = False
        self._thread: threading.Thread | None = None
        self._vosk_available = False
        self._recognizer: object | None = None
        self._on_command: Callable[[str], None] | None = None
        self._check_vosk()

    def _check_vosk(self) -> None:
        try:
            import vosk  # noqa: PLC0415
            self._vosk_available = True
        except ImportError:
            _LOG.info("vosk not installed – voice control unavailable")
            self._vosk_available = False

    @property
    def available(self) -> bool:
        return self._vosk_available

    @property
    def running(self) -> bool:
        return self._running

    def set_command_callback(self, cb: Callable[[str], None]) -> None:
        self._on_command = cb

    def start(self) -> bool:
        if self._running:
            return True
        if not self._vosk_available:
            _LOG.warning("Cannot start voice control: vosk not installed")
            return False
        self._running = True
        self._thread = threading.Thread(target=self._listen_loop, daemon=True, name="voice")
        self._thread.start()
        return True

    def stop(self) -> None:
        self._running = False
        if self._thread:
            self._thread.join(timeout=2.0)

    def _listen_loop(self) -> None:
        """Main voice recognition loop (requires vosk + pyaudio)."""
        try:
            import vosk  # noqa: PLC0415
            import json
            import pyaudio  # noqa: PLC0415

            model = vosk.Model(lang=self.language)
            rec = vosk.KaldiRecognizer(model, 16000)
            pa = pyaudio.PyAudio()
            stream = pa.open(
                format=pyaudio.paInt16,
                channels=1,
                rate=16000,
                input=True,
                frames_per_buffer=4000,
            )

            while self._running:
                data = stream.read(4000, exception_on_overflow=False)
                if rec.AcceptWaveform(data):
                    result = json.loads(rec.Result())
                    text = result.get("text", "").strip().lower()
                    if text:
                        self._handle_text(text)
                else:
                    partial = json.loads(rec.PartialResult())
                    text = partial.get("partial", "").strip().lower()
                    if text and text in _COMMAND_MAP:
                        self._handle_text(text)

            stream.stop_stream()
            stream.close()
            pa.terminate()
        except Exception as exc:
            _LOG.error("Voice loop error: %s", exc)
            self._running = False

    def _handle_text(self, text: str) -> None:
        action = _COMMAND_MAP.get(text)
        if action is None:
            return
        _LOG.info("Voice command: '%s' -> %s", text, action)
        if self._on_command:
            self._on_command(action)
        self._emit_action(action)

    def _emit_action(self, action: str) -> None:
        if action == "left_click":
            self.bus.emit_simple(EventType.MOUSE_CLICK, button="left")
        elif action == "double_click":
            self.bus.emit_simple(EventType.MOUSE_DOUBLE_CLICK)
        elif action == "right_click":
            self.bus.emit_simple(EventType.MOUSE_RIGHT_CLICK)
        elif action == "scroll_up":
            self.bus.emit_simple(EventType.MOUSE_SCROLL, delta=3)
        elif action == "scroll_down":
            self.bus.emit_simple(EventType.MOUSE_SCROLL, delta=-3)
        elif action == "pause":
            self.bus.emit_simple(EventType.EMERGENCY_STOP)
        elif action == "resume":
            pass  # handled via the app-level command callback
        elif action == "calibrate":
            self.bus.emit_simple(EventType.CALIBRATION_STARTED)
        else:
            shortcut = _ACTION_SHORTCUTS.get(action)
            if shortcut is not None:
                self.bus.emit_simple(EventType.KEYBOARD_SHORTCUT, keys=list(shortcut))