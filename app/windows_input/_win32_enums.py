"""Low-level Win32 monitor enumeration (ctypes only – no pywin32 dependency)."""
from __future__ import annotations

import ctypes
import ctypes.wintypes
from typing import Optional


class _RECT(ctypes.Structure):
    _fields_ = [
        ("left", ctypes.c_long),
        ("top", ctypes.c_long),
        ("right", ctypes.c_long),
        ("bottom", ctypes.c_long),
    ]


class _MONITORINFOEX(ctypes.Structure):
    _fields_ = [
        ("cbSize", ctypes.wintypes.DWORD),
        ("rcMonitor", _RECT),
        ("rcWork", _RECT),
        ("dwFlags", ctypes.wintypes.DWORD),
        ("szDevice", ctypes.c_wchar * 32),
    ]


_Callback = ctypes.WINFUNCTYPE(
    ctypes.wintypes.BOOL,
    ctypes.wintypes.HMONITOR,
    ctypes.wintypes.HDC,
    ctypes.POINTER(_RECT),
    ctypes.wintypes.LPARAM,
)


def init() -> None:
    """Preload user32 if needed."""
    ctypes.windll.user32  # noqa: B018


def enum_display_monitors() -> list[int]:
    """Return list of HMONITOR handles."""
    monitors: list[int] = []

    def _cb(hmon, _hdc, _rect, _lparam):
        monitors.append(hmon)
        return 1

    cb = _Callback(_cb)
    ctypes.windll.user32.EnumDisplayMonitors(0, 0, cb, 0)
    return monitors


def get_monitor_info(hmon: int) -> Optional[dict]:
    info = _MONITORINFOEX()
    info.cbSize = ctypes.sizeof(_MONITORINFOEX)
    if not ctypes.windll.user32.GetMonitorInfoW(hmon, ctypes.byref(info)):
        return None
    r = info.rcMonitor
    return {
        "left": r.left,
        "top": r.top,
        "width": r.right - r.left,
        "height": r.bottom - r.top,
        "primary": bool(info.dwFlags & 1),  # MONITORINFOF_PRIMARY
        "name": info.szDevice,
    }