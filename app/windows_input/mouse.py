"""Mouse control via Windows SendInput (ctypes).

No dependency on pyautogui or similar; works with standard Python on Windows.
"""
from __future__ import annotations

import ctypes
import ctypes.wintypes
import logging
import math
import sys
import time
from typing import Optional

from app.utils.vectors import Tup2

_LOG = logging.getLogger(__name__)

# Only build the Win32 structures if we're on Windows
_IS_WIN = sys.platform == "win32"

if _IS_WIN:
    user32 = ctypes.windll.user32  # type: ignore[attr-defined]
    kernel32 = ctypes.windll.kernel32  # type: ignore[attr-defined]

    INPUT_MOUSE = 0

    MOUSEEVENTF_MOVE = 0x0001
    MOUSEEVENTF_LEFTDOWN = 0x0002
    MOUSEEVENTF_LEFTUP = 0x0004
    MOUSEEVENTF_RIGHTDOWN = 0x0008
    MOUSEEVENTF_RIGHTUP = 0x0010
    MOUSEEVENTF_MIDDLEDOWN = 0x0020
    MOUSEEVENTF_MIDDLEUP = 0x0040
    MOUSEEVENTF_WHEEL = 0x0800
    MOUSEEVENTF_ABSOLUTE = 0x8000
    MOUSEEVENTF_VIRTUALDESK = 0x4000
    WHEEL_DELTA = 120

    class MOUSEINPUT(ctypes.Structure):
        _fields_ = [
            ("dx", ctypes.wintypes.LONG),
            ("dy", ctypes.wintypes.LONG),
            ("mouseData", ctypes.wintypes.DWORD),
            ("dwFlags", ctypes.wintypes.DWORD),
            ("time", ctypes.wintypes.DWORD),
            ("dwExtraInfo", ctypes.POINTER(ctypes.c_ulong)),
        ]

    class INPUT(ctypes.Structure):
        class _U(ctypes.Union):
            _fields_ = [("mi", MOUSEINPUT)]
        _fields_ = [
            ("type", ctypes.wintypes.DWORD),
            ("_u", _U),
        ]


def _send_input(*inputs: object) -> int:
    if not _IS_WIN:
        return 0
    n = len(inputs)
    arr = (INPUT * n)(*inputs)
    return user32.SendInput(n, ctypes.byref(arr), ctypes.sizeof(INPUT))


def _mouse_input(flags: int, dx: int = 0, dy: int = 0, data: int = 0) -> INPUT:
    inp = INPUT()
    inp.type = INPUT_MOUSE
    inp._u.mi = MOUSEINPUT()
    inp._u.mi.dx = dx
    inp._u.mi.dy = dy
    inp._u.mi.mouseData = data
    inp._u.mi.dwFlags = flags
    inp._u.mi.time = 0
    inp._u.mi.dwExtraInfo = None
    return inp


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

class MouseController:
    """Control the mouse cursor via Windows APIs."""

    def __init__(self) -> None:
        self._smoothing_alpha = 0.45
        self._prev_pos: Optional[Tup2] = None
        self._speed = 1.0
        self._dragging = False

    @property
    def screen_size(self) -> tuple[int, int]:
        if not _IS_WIN:
            return (1920, 1080)
        return (user32.GetSystemMetrics(0), user32.GetSystemMetrics(1))

    def get_position(self) -> Tup2:
        if not _IS_WIN:
            return (0.0, 0.0)
        pt = ctypes.wintypes.POINT()
        user32.GetCursorPos(ctypes.byref(pt))
        return (float(pt.x), float(pt.y))

    def set_position(self, x: float, y: float) -> None:
        """Move cursor to absolute screen coordinates."""
        if not _IS_WIN:
            return
        sx, sy = self.screen_size
        # Convert to 0-65535 range for absolute mode
        nx = int(x / sx * 65535)
        ny = int(y / sy * 65535)
        _send_input(_mouse_input(MOUSEEVENTF_ABSOLUTE | MOUSEEVENTF_MOVE, nx, ny))

    def move_relative(self, dx: int, dy: int) -> None:
        if not _IS_WIN:
            return
        _send_input(_mouse_input(MOUSEEVENTF_MOVE, dx, dy))

    def move_smoothed(self, target: Tup2, alpha: float | None = None) -> Tup2:
        """Move cursor with exponential smoothing.  Returns the actual position moved to."""
        a = alpha or self._smoothing_alpha
        if self._prev_pos is None:
            self._prev_pos = target
            self.set_position(target[0], target[1])
            return target
        sx = self._prev_pos[0] + (target[0] - self._prev_pos[0]) * a
        sy = self._prev_pos[1] + (target[1] - self._prev_pos[1]) * a
        self._prev_pos = (sx, sy)
        self.set_position(sx, sy)
        return (sx, sy)

    def left_click(self) -> None:
        if not _IS_WIN:
            return
        _send_input(_mouse_input(MOUSEEVENTF_LEFTDOWN), _mouse_input(MOUSEEVENTF_LEFTUP))

    def double_click(self) -> None:
        self.left_click()
        time.sleep(0.03)
        self.left_click()

    def right_click(self) -> None:
        if not _IS_WIN:
            return
        _send_input(_mouse_input(MOUSEEVENTF_RIGHTDOWN), _mouse_input(MOUSEEVENTF_RIGHTUP))

    def middle_click(self) -> None:
        if not _IS_WIN:
            return
        _send_input(_mouse_input(MOUSEEVENTF_MIDDLEDOWN), _mouse_input(MOUSEEVENTF_MIDDLEUP))

    def mouse_down(self, button: str = "left") -> None:
        if not _IS_WIN:
            return
        flag = {"left": MOUSEEVENTF_LEFTDOWN, "right": MOUSEEVENTF_RIGHTDOWN,
                "middle": MOUSEEVENTF_MIDDLEDOWN}.get(button, MOUSEEVENTF_LEFTDOWN)
        _send_input(_mouse_input(flag))

    def mouse_up(self, button: str = "left") -> None:
        if not _IS_WIN:
            return
        flag = {"left": MOUSEEVENTF_LEFTUP, "right": MOUSEEVENTF_RIGHTUP,
                "middle": MOUSEEVENTF_MIDDLEUP}.get(button, MOUSEEVENTF_LEFTUP)
        _send_input(_mouse_input(flag))

    def scroll(self, delta: int) -> None:
        """Scroll by *delta* clicks (positive = up)."""
        if not _IS_WIN:
            return
        _send_input(_mouse_input(MOUSEEVENTF_WHEEL, data=delta * WHEEL_DELTA))

    def drag_start(self, x: float, y: float) -> None:
        self.set_position(x, y)
        self.mouse_down("left")
        self._dragging = True

    def drag_move(self, x: float, y: float) -> None:
        self.set_position(x, y)

    def drag_end(self) -> None:
        self.mouse_up("left")
        self._dragging = False

    def reset_smoothing(self) -> None:
        self._prev_pos = None

    # -- screen-aware coordinate mapping (used by calibrator + virtual touch) --

    def screen_to_cursor(self, normalized_x: float, normalized_y: float,
                         monitor_index: int = 0) -> Tup2:
        """Map normalised [0..1] coords to screen pixels."""
        from app.windows_input.screen import ScreenManager  # noqa: PLC0415
        sm = ScreenManager()
        w, h = sm.get_screen_size(monitor_index)
        return (normalized_x * w, normalized_y * h)