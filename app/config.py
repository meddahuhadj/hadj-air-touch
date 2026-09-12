"""Centralized application configuration (JSON + in-memory).

Thread-safe accessors; persisted to a JSON file that lives next to the
executable or in the user's AppData folder.
"""
from __future__ import annotations

import json
import logging
import os
import threading
import copy
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Any

_LOG = logging.getLogger(__name__)

_DEFAULT_CONFIG_DIR = Path(os.environ.get(
    "APPDATA",
    Path.home(),
)) / "HADJAirTouch"

_DEFAULT_CONFIG_FILE = _DEFAULT_CONFIG_DIR / "settings.json"

# ---------------------------------------------------------------------------
# Dataclass defaults
# ---------------------------------------------------------------------------

@dataclass
class CameraConfig:
    index: int = 0
    width: int = 1280
    height: int = 720
    fps: int = 30
    mirror: bool = True

@dataclass
class CalibrationConfig:
    auto: bool = True
    depth_threshold: float = 0.04
    smoothing: float = 0.6
    confidence_min: float = 0.7
    save_homography: bool = True
    homography_state: dict | None = None

@dataclass
class VirtualTouchConfig:
    monitor_width_cm: float = 53.0
    monitor_height_cm: float = 30.0
    interaction_distance_cm: float = 55.0
    touch_depth_cm: float = 3.0
    click_threshold: float = 0.04
    sensitivity: float = 1.0
    smoothing: float = 0.55
    gesture_threshold: float = 0.04

@dataclass
class CursorConfig:
    speed: float = 1.0
    acceleration: float = 1.2
    smoothing: float = 0.5
    dead_zone: float = 0.005
    one_euro: bool = False
    one_euro_min_cutoff: float = 1.0
    one_euro_beta: float = 0.007

@dataclass
class SafetyConfig:
    emergency_hotkey: str = "Ctrl+Alt+H"
    auto_timeout_sec: int = 3600
    click_cooldown_ms: int = 200
    false_click_guard: bool = True

@dataclass
class AccessibilityConfig:
    enabled: bool = False
    large_cursor: bool = False
    high_contrast: bool = False
    cursor_speed: float = 0.6
    interaction_delay_ms: int = 0

@dataclass
class VoiceConfig:
    enabled: bool = False
    language: str = "en"
    commands: dict[str, str] = field(default_factory=lambda: {
        "click": "left_click",
        "double click": "double_click",
        "right click": "right_click",
        "scroll down": "scroll_down",
        "scroll up": "scroll_up",
        "pause": "pause",
        "resume": "resume",
    })

@dataclass
class PrivacyConfig:
    camera_indicator: bool = True
    show_preview: bool = True
    pause_on_foucs_loss: bool = False

@dataclass
class OverlayConfig:
    enabled: bool = False
    show_halo: bool = True
    size: int = 64
    opacity: float = 0.85

@dataclass
class AppConfig:
    camera: CameraConfig = field(default_factory=CameraConfig)
    calibration: CalibrationConfig = field(default_factory=CalibrationConfig)
    virtual_touch: VirtualTouchConfig = field(default_factory=VirtualTouchConfig)
    cursor: CursorConfig = field(default_factory=CursorConfig)
    safety: SafetyConfig = field(default_factory=SafetyConfig)
    accessibility: AccessibilityConfig = field(default_factory=AccessibilityConfig)
    voice: VoiceConfig = field(default_factory=VoiceConfig)
    privacy: PrivacyConfig = field(default_factory=PrivacyConfig)
    overlay: OverlayConfig = field(default_factory=OverlayConfig)
    monitor: int = 0
    mode: str = "air_mouse"
    active_profile: str = "general"
    language: str = "en"
    theme: str = "dark"
    auto_start: bool = False
    gestures: dict[str, bool] = field(default_factory=lambda: {
        "point": True,
        "pinch": True,
        "double_pinch": True,
        "right_click": True,
        "grab": True,
        "open_palm": True,
        "fist": False,
        "swipe": True,
        "zoom": True,
        "peace": False,
        "thumbs_up": False,
        "wave": False,
    })


# ---------------------------------------------------------------------------
# Settings store
# ---------------------------------------------------------------------------

class Settings:
    """Thread-safe singleton-ish config store."""

    _instance: Settings | None = None
    _lock_cls = threading.Lock()

    def __new__(cls, path: Path | str | None = None):
        with cls._lock_cls:
            if cls._instance is not None:
                return cls._instance
            inst = super().__new__(cls)
            inst._lock = threading.Lock()
            inst._path = Path(path) if path else _DEFAULT_CONFIG_FILE
            inst._config = AppConfig()
            inst._load()
            cls._instance = inst
            return inst

    # -- public API --

    @property
    def config(self) -> AppConfig:
        return self._config

    def get(self, dotted_key: str, default: Any = None) -> Any:
        """Retrieve a value by dotted path, e.g. 'camera.width'."""
        parts = dotted_key.split(".")
        obj: Any = self._config
        for p in parts:
            if isinstance(obj, dict):
                obj = obj.get(p)
            else:
                obj = getattr(obj, p, None)
            if obj is None:
                return default
            if p == parts[-1]:
                return obj
        return default

    def set(self, dotted_key: str, value: Any) -> None:
        """Set a value by dotted path and persist."""
        parts = dotted_key.split(".")
        with self._lock:
            obj = self._config
            for p in parts[:-1]:
                obj = getattr(obj, p)
            setattr(obj, parts[-1], value)
            self._save()

    def update_section(self, section_name: str, data: dict[str, Any]) -> None:
        with self._lock:
            section = getattr(self._config, section_name)
            for k, v in data.items():
                setattr(section, k, v)
            self._save()

    def reset(self) -> None:
        with self._lock:
            self._config = AppConfig()
            self._save()

    def as_dict(self) -> dict:
        return asdict(self._config)

    def reload(self) -> None:
        with self._lock:
            self._load()

    # -- persistence --

    def _load(self) -> None:
        if not self._path.exists():
            _LOG.info("No settings file found – using defaults: %s", self._path)
            return
        try:
            raw = json.loads(self._path.read_text(encoding="utf-8"))
            self._config = self._dict_to_config(raw)
            _LOG.info("Settings loaded from %s", self._path)
        except Exception as exc:
            _LOG.warning("Could not load settings: %s", exc)

    def _save(self) -> None:
        try:
            self._path.parent.mkdir(parents=True, exist_ok=True)
            self._path.write_text(
                json.dumps(asdict(self._config), indent=2, ensure_ascii=False),
                encoding="utf-8",
            )
        except Exception as exc:
            _LOG.warning("Could not save settings: %s", exc)

    @staticmethod
    def _dict_to_config(raw: dict) -> AppConfig:
        mapping: dict[str, type] = {
            "camera": CameraConfig,
            "calibration": CalibrationConfig,
            "virtual_touch": VirtualTouchConfig,
            "cursor": CursorConfig,
            "safety": SafetyConfig,
            "accessibility": AccessibilityConfig,
            "voice": VoiceConfig,
            "privacy": PrivacyConfig,
            "overlay": OverlayConfig,
        }
        kwargs: dict[str, Any] = {}
        for key, cls_ in mapping.items():
            if key in raw:
                kwargs[key] = cls_(**{k: v for k, v in raw[key].items()
                                      if hasattr(cls_, k)})
            else:
                kwargs[key] = cls_()
        top_keys = set(raw) - set(mapping)
        for k in top_keys:
            kwargs[k] = raw[k]
        return AppConfig(**kwargs)


# Convenience singleton accessor
def settings() -> Settings:
    return Settings()