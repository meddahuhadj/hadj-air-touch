"""Monitor enumeration and screen information via Windows APIs."""
from __future__ import annotations

import ctypes
import ctypes.wintypes
import logging
from dataclasses import dataclass
from typing import Optional

_LOG = logging.getLogger(__name__)

# Windows constants
MONITOR_DEFAULTTONEAREST = 2
ENUM_CURRENT_SETTINGS = -1
DM_PELSWIDTH = 0x00080000
DM_PELSHEIGHT = 0x00100000


@dataclass
class MonitorInfo:
    index: int
    name: str
    left: int
    top: int
    width: int
    height: int
    primary: bool = False
    dpi: float = 96.0

    @property
    def center(self) -> tuple[int, int]:
        return (self.left + self.width // 2, self.top + self.height // 2)

    @property
    def bounds(self) -> tuple[int, int, int, int]:
        return (self.left, self.top, self.left + self.width, self.top + self.height)


class ScreenManager:
    """Enumerate monitors and get screen metrics."""

    def __init__(self) -> None:
        self._monitors: list[MonitorInfo] = []
        self._refresh()

    def _refresh(self) -> None:
        self._monitors.clear()
        if not _is_windows():
            self._monitors = [MonitorInfo(
                index=0, name="Default", left=0, top=0,
                width=1920, height=1080, primary=True,
            )]
            return

        try:
            from app.windows_input._win32_enums import enum_display_monitors, get_monitor_info  # noqa: PLC0415
            monitors = enum_display_monitors()
            for i, hmon in enumerate(monitors):
                info = get_monitor_info(hmon)
                if info is None:
                    continue
                self._monitors.append(MonitorInfo(
                    index=i,
                    name=f"Monitor {i}",
                    left=info["left"],
                    top=info["top"],
                    width=info["width"],
                    height=info["height"],
                    primary=info.get("primary", False),
                ))
        except Exception as exc:
            _LOG.warning("Monitor enumeration failed: %s", exc)
            self._monitors = [MonitorInfo(
                index=0, name="Default", left=0, top=0,
                width=1920, height=1080, primary=True,
            )]

    @property
    def monitors(self) -> list[MonitorInfo]:
        return list(self._monitors)

    @property
    def primary(self) -> Optional[MonitorInfo]:
        for m in self._monitors:
            if m.primary:
                return m
        return self._monitors[0] if self._monitors else None

    def get_monitor(self, index: int) -> Optional[MonitorInfo]:
        for m in self._monitors:
            if m.index == index:
                return m
        return None

    def get_screen_size(self, index: int = 0) -> tuple[int, int]:
        m = self.get_monitor(index) or self.primary
        if m is None:
            return (1920, 1080)
        return (m.width, m.height)


def _is_windows() -> bool:
    import sys
    return sys.platform == "win32"


# Lazy import of the Win32 enumeration helpers
if _is_windows():
    try:
        from app.windows_input._win32_enums import init  # noqa: F401
    except ImportError:
        pass