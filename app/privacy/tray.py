"""System tray integration and Windows auto-start.

The tray allows the app to keep running in the background with quick access
to START / PAUSE / CALIBRATE / SETTINGS / EXIT.
"""
from __future__ import annotations

import logging
import sys
from typing import TYPE_CHECKING, Optional

_LOG = logging.getLogger(__name__)

_IS_WIN = sys.platform == "win32"


class TrayController:
    """Manage the system tray icon (uses QSystemTrayIcon in the GUI).

    Fallback: if no GUI/icon is available, tracks state only.
    """

    def __init__(self) -> None:
        self._tray_icon = None
        self._enabled = False

    def install(self, window: object) -> bool:
        """Create the tray icon attached to a QMainWindow."""
        try:
            from PySide6.QtCore import QObject  # noqa: PLC0415
            from PySide6.QtGui import QAction, QIcon  # noqa: PLC0415
            from PySide6.QtWidgets import QSystemTrayIcon, QMenu  # noqa: PLC0415
        except ImportError:
            _LOG.warning("PySide6 unavailable – tray control disabled")
            return False

        if not QSystemTrayIcon.isSystemTrayAvailable():
            _LOG.warning("System tray not available on this system")
            return False

        try:
            has_icon = isinstance(window, QObject)
        except Exception:
            has_icon = False

        if not has_icon:
            return False

        tray = QSystemTrayIcon(window)
        tray.setIcon(window.windowIcon())
        tray.setToolTip("HADJ AIR TOUCH")

        menu = QMenu()
        for label, handler in [
            ("Start", getattr(window, "_on_start", None)),
            ("Pause", getattr(window, "_on_pause", None)),
            ("Calibrate", getattr(window, "_on_calib_start", None)),
            ("Settings", getattr(window, "_open_settings_page", None)),
            ("Exit", getattr(window, "_on_exit", None)),
        ]:
            if handler is None:
                continue
            act = QAction(label, window)
            act.triggered.connect(handler)
            menu.addAction(act)

        tray.setContextMenu(menu)
        tray.activated.connect(self._on_activated)
        tray.show()
        self._tray_icon = tray
        self._enabled = True
        _LOG.info("Tray icon installed")
        return True

    @property
    def enabled(self) -> bool:
        return self._enabled

    def show_message(self, title: str, message: str) -> None:
        """Show a tray balloon notification (best-effort)."""
        if self._tray_icon is None:
            return
        try:
            from PySide6.QtWidgets import QSystemTrayIcon  # noqa: PLC0415
            self._tray_icon.showMessage(title, message, QSystemTrayIcon.MessageIcon.Information)
        except Exception as exc:
            _LOG.debug("Tray message failed: %s", exc)

    def _on_activated(self, reason) -> None:  # type: ignore[no-untyped-def]
        """Left click or double click on the tray shows the main window."""
        try:
            from PySide6.QtWidgets import QSystemTrayIcon  # noqa: PLC0415
            if reason in (QSystemTrayIcon.ActivationReason.Trigger,
                          QSystemTrayIcon.ActivationReason.DoubleClick):
                parent = self._tray_icon.parent()
                if parent is not None and hasattr(parent, "show"):
                    parent.show()
                    parent.raise_()
                    parent.activateWindow()
        except Exception as exc:
            _LOG.debug("Tray activation failed: %s", exc)


# ---------------------------------------------------------------------------
# Windows auto-start (registry Run key)
# ---------------------------------------------------------------------------

_APP_PATH = sys.executable if sys.executable and "python" not in sys.executable.lower() else None
_PROCESS_PATH: Optional[str] = None


def set_auto_start(enabled: bool, executable: str | None = None) -> bool:
    """Add/remove HADJ AIR TOUCH from the Windows startup registry key."""
    if not _IS_WIN:
        return False
    try:
        import winreg  # noqa: PLC0415
        exe = executable or _PROCESS_PATH or sys.executable
        key = winreg.OpenKey(
            winreg.HKEY_CURRENT_USER,
            r"Software\Microsoft\Windows\CurrentVersion\Run",
            0, winreg.KEY_SET_VALUE,
        )
        if enabled:
            winreg.SetValueEx(key, "HADJAirTouch", 0, winreg.REG_SZ, f'"{exe}"')
        else:
            try:
                winreg.DeleteValue(key, "HADJAirTouch")
            except FileNotFoundError:
                pass
        winreg.CloseKey(key)
        _LOG.info("Auto-start %s", "enabled" if enabled else "disabled")
        return True
    except Exception as exc:
        _LOG.warning("Auto-start update failed: %s", exc)
        return False


def is_auto_start_enabled() -> bool:
    if not _IS_WIN:
        return False
    try:
        import winreg  # noqa: PLC0415
        key = winreg.OpenKey(
            winreg.HKEY_CURRENT_USER,
            r"Software\Microsoft\Windows\CurrentVersion\Run",
            0, winreg.KEY_READ,
        )
        winreg.QueryValueEx(key, "HADJAirTouch")
        winreg.CloseKey(key)
        return True
    except FileNotFoundError:
        return False
    except Exception:
        return False