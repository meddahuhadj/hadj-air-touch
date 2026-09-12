"""Profile manager – per-application gesture/sensitivity presets."""
from __future__ import annotations

import json
import logging
import sys
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Any, Optional

from app.gestures.mapping import get_profile_names, get_profile_map
from dataclasses import fields

_LOG = logging.getLogger(__name__)


@dataclass
class Profile:
    name: str
    description: str = ""
    gestures: dict[str, bool] = field(default_factory=dict)
    cursor_speed: float = 1.0
    touch_sensitivity: float = 1.0
    smoothing: float = 0.5
    auto_activate: bool = False
    trigger_apps: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> Profile:
        valid_fields = {f.name for f in fields(cls)}
        return cls(**{k: v for k, v in data.items() if k in valid_fields})


# Built-in profiles
_BUILTIN_PROFILES: dict[str, Profile] = {
    "general": Profile(
        name="general",
        description="Default profile for everyday Windows use.",
        gestures={"point": True, "pinch": True, "double_pinch": True, "right_click": True},
    ),
    "browser": Profile(
        name="browser",
        description="Optimised for web browsing (swipe = back/forward).",
        gestures={"point": True, "pinch": True, "swipe": True},
        trigger_apps=["chrome", "firefox", "edge", "brave", "opera"],
    ),
    "presentation": Profile(
        name="presentation",
        description="Presentation mode: swipe = next/prev slide, point = laser.",
        gestures={"point": True, "pinch": True, "swipe": True, "open_palm": True},
        trigger_apps=["powerpnt", "slideshow"],
    ),
    "media": Profile(
        name="media",
        description="Media playback control.",
        gestures={"point": True, "pinch": True, "swipe": True, "open_palm": True},
        trigger_apps=["vlc", "spotify", "wmplayer", "potplayer"],
    ),
    "cad": Profile(
        name="cad",
        description="CAD/3D modelling – reduced sensitivity.",
        gestures={"point": True, "pinch": True, "grab": True, "zoom": True},
        cursor_speed=0.7,
        smoothing=0.65,
        trigger_apps=["autocad", "solidworks", "blender", "fusion360"],
    ),
    "office": Profile(
        name="office",
        description="Office / productivity: swipe = undo/redo, thumbs-up = save.",
        gestures={"point": True, "pinch": True, "swipe": True,
                  "thumbs_up": True, "peace": True, "fist": True, "open_palm": True},
        trigger_apps=["winword", "excel", "powerpnt", "wordpad", "notepad"],
    ),
    "developer": Profile(
        name="developer",
        description="IDE / coding: swipe = switch tabs, thumbs-up = new tab.",
        gestures={"point": True, "pinch": True, "swipe": True,
                  "thumbs_up": True, "peace": True, "fist": True, "open_palm": True},
        trigger_apps=["code", "pycharm", "intellij", "studio", "terminal", "cmd"],
    ),
    "accessibility": Profile(
        name="accessibility",
        description="Accessibility mode – slower, larger target area.",
        gestures={"point": True, "pinch": True},
        cursor_speed=0.5,
        touch_sensitivity=0.8,
        smoothing=0.7,
    ),
}


class ProfileManager:
    def __init__(self, config_dir: Path | None = None) -> None:
        self._profiles: dict[str, Profile] = dict(_BUILTIN_PROFILES)
        self._active: str = "general"
        self._config_dir = config_dir
        self._load_custom()

    def _load_custom(self) -> None:
        if self._config_dir is None:
            return
        p = self._config_dir / "profiles.json"
        if not p.exists():
            return
        try:
            data = json.loads(p.read_text(encoding="utf-8"))
            for name, pdata in data.items():
                self._profiles[name] = Profile.from_dict(pdata)
        except Exception as exc:
            _LOG.warning("Failed to load custom profiles: %s", exc)

    def get_active(self) -> Profile:
        return self._profiles.get(self._active, _BUILTIN_PROFILES["general"])

    def set_active(self, name: str) -> bool:
        if name in self._profiles:
            self._active = name
            return True
        return False

    @property
    def active_name(self) -> str:
        return self._active

    @property
    def all_names(self) -> list[str]:
        return list(self._profiles.keys())

    def get_profile(self, name: str) -> Optional[Profile]:
        return self._profiles.get(name)

    def detect_profile_by_active_window(self) -> Optional[str]:
        """Attempt to match the foreground window to a profile's trigger apps."""
        if sys.platform != "win32":
            return None
        try:
            import ctypes
            hwnd = ctypes.windll.user32.GetForegroundWindow()
            _, pid = ctypes.windll.user32.GetWindowThreadProcessId(hwnd)
            import subprocess
            out = subprocess.check_output(
                f"tasklist /FI \"PID eq {pid}\" /FO CSV /NH",
                shell=True, text=True, timeout=3,
            ).strip().lower()
            for name, profile in self._profiles.items():
                for app in profile.trigger_apps:
                    if app.lower() in out:
                        return name
        except Exception:
            pass
        return None

    def auto_detect(self) -> Optional[str]:
        detected = self.detect_profile_by_active_window()
        if detected and detected != self._active:
            _LOG.info("Auto-detected profile: %s", detected)
            self._active = detected
            return detected
        return None