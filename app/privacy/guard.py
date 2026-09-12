"""Privacy guard – camera indicator, emergency stop, pause on focus loss."""
from __future__ import annotations

import ctypes
import logging
import sys
import threading
import time
from typing import Callable, Optional

from app.core.events import Event, EventBus, EventType

_LOG = logging.getLogger(__name__)


def parse_hotkey(hotkey: str) -> list[int]:
    """Parse a hotkey such as 'Ctrl+Alt+H' into virtual-key codes.

    Uses the shared keyboard VK resolution, so any key name recognised by the
    keyboard module (modifiers, letters, digits, function keys, volume keys...)
    can be part of a hotkey.
    """
    from app.windows_input.keyboard import _resolve_vk  # noqa: PLC0415
    codes: list[int] = []
    for part in hotkey.split("+"):
        vk = _resolve_vk(part.strip())
        if vk is not None:
            codes.append(vk)
    return codes


class PrivacyGuard:
    """Manages privacy-related features: indicator, emergency stop, auto-pause."""

    def __init__(self, bus: EventBus) -> None:
        self.bus = bus
        self._camera_active = False
        self._pause_requested = False
        self._hotkey_thread: threading.Thread | None = None
        self._stop_event = threading.Event()

    def start_hotkey_listener(self, hotkey: str = "Ctrl+Alt+H") -> None:
        """Listen for the emergency stop hotkey in a background thread."""
        self._stop_event.clear()
        self._hotkey_thread = threading.Thread(
            target=self._listen_hotkey,
            args=(hotkey,),
            daemon=True,
            name="privacy-hotkey",
        )
        self._hotkey_thread.start()

    def stop_hotkey_listener(self) -> None:
        self._stop_event.set()
        if self._hotkey_thread:
            self._hotkey_thread.join(timeout=1.0)

    def _listen_hotkey(self, hotkey: str) -> None:
        if sys.platform != "win32":
            return

        vks = parse_hotkey(hotkey)
        if not vks:
            _LOG.error("Could not parse hotkey %r – emergency stop disabled", hotkey)
            return

        user32 = ctypes.windll.user32  # type: ignore[attr-defined]
        while not self._stop_event.is_set():
            all_pressed = all(user32.GetAsyncKeyState(vk) & 0x8000 for vk in vks)
            if all_pressed:
                _LOG.warning("Emergency stop hotkey pressed: %s", hotkey)
                self.bus.emit_simple(EventType.EMERGENCY_STOP)
                # Wait until keys released
                while any(user32.GetAsyncKeyState(vk) & 0x8000 for vk in vks):
                    time.sleep(0.02)
            time.sleep(0.05)

    def notify_camera_active(self) -> None:
        self._camera_active = True
        _LOG.info("Camera active indicator: ON")

    def notify_camera_inactive(self) -> None:
        self._camera_active = False

    @property
    def is_camera_active(self) -> bool:
        return self._camera_active

    def privacy_statement(self) -> str:
        return (
            "HADJ AIR TOUCH Privacy Statement\n"
            "==================================\n"
            "• Camera data is processed LOCALLY on this computer.\n"
            "• No images or tracking data are sent to any server.\n"
            "• No cloud upload occurs by default.\n"
            "• You can pause or stop the camera at any time.\n"
            "• All configuration is stored locally.\n"
        )