"""Gesture-to-action mapping (profile-aware)."""
from __future__ import annotations

from typing import Optional

# Default mapping shared by most profiles
_DEFAULT_MAP: dict[str, Optional[str]] = {
    "point": None,           # cursor move (handled by pipeline, not action dispatch)
    "pinch": "left_click",
    "double_pinch": "double_click",
    "right_click": "right_click",
    "grab": None,            # drag mode toggle
    "open_palm": "pause",
    "fist": None,
    "swipe_left": None,
    "swipe_right": None,
    "swipe_up": "scroll_up",
    "swipe_down": "scroll_down",
    "two_finger_pinch_in": "zoom_out",
    "two_finger_pinch_out": "zoom_in",
    "peace": None,
    "thumbs_up": "volume_up",
    "wave": None,
}

_PROFILES: dict[str, dict[str, Optional[str]]] = {
    "general": _DEFAULT_MAP.copy(),
    "browser": {
        **_DEFAULT_MAP,
        "swipe_left": "back",
        "swipe_right": "forward",
    },
    "presentation": {
        **_DEFAULT_MAP,
        "pinch": "next_slide",
        "right_click": "previous_slide",
        "open_palm": "laser_pointer",
        "swipe_left": "previous_slide",
        "swipe_right": "next_slide",
    },
    "media": {
        **_DEFAULT_MAP,
        "open_palm": "play_pause",
        "swipe_right": "next_track",
        "swipe_left": "previous_track",
        "thumbs_up": "volume_up",
        "peace": "volume_down",
    },
    "cad": {
        **_DEFAULT_MAP,
        "swipe_left": "undo",
        "swipe_right": "redo",
        "fist": "save",
    },
    "office": {
        **_DEFAULT_MAP,
        "swipe_left": "undo",
        "swipe_right": "redo",
        "thumbs_up": "save",
        "peace": "undo",
        "fist": "redo",
        "open_palm": "select_all",
    },
    "developer": {
        **_DEFAULT_MAP,
        "swipe_left": "switch_tab_prev",
        "swipe_right": "switch_tab_next",
        "swipe_up": None,
        "swipe_down": None,
        "thumbs_up": "new_tab",
        "peace": "close_tab",
        "fist": "undo",
        "open_palm": "show_desktop",
    },
}


def gesture_action_lookup(gesture_name: str, profile: str = "general") -> Optional[str]:
    """Return the action name for a gesture in the given profile, or None."""
    profile_map = _PROFILES.get(profile, _DEFAULT_MAP)
    return profile_map.get(gesture_name)


def get_profile_names() -> list[str]:
    return list(_PROFILES.keys())


def get_profile_map(profile: str) -> dict[str, Optional[str]]:
    return _PROFILES.get(profile, _DEFAULT_MAP).copy()