"""Keyboard & shortcut injection via Windows SendInput (ctypes)."""
from __future__ import annotations

import ctypes
import ctypes.wintypes
import logging
import sys
import time

_LOG = logging.getLogger(__name__)

_IS_WIN = sys.platform == "win32"

if _IS_WIN:
    user32 = ctypes.windll.user32  # type: ignore[attr-defined]

    INPUT_KEYBOARD = 1
    KEYEVENTF_KEYUP = 0x0002
    KEYEVENTF_EXTENDEDKEY = 0x0001
    KEYBDINPUT = 0

    # Virtual key codes (subset)
    VK_BACK = 0x08
    VK_RETURN = 0x0D
    VK_SHIFT = 0x10
    VK_CONTROL = 0x11
    VK_MENU = 0x12      # Alt
    VK_ESCAPE = 0x1B
    VK_SPACE = 0x20
    VK_TAB = 0x09
    VK_DELETE = 0x2E
    VK_LWIN = 0x5B
    VK_UP = 0x26
    VK_DOWN = 0x28
    VK_LEFT = 0x25
    VK_RIGHT = 0x27
    VK_F1 = 0x70
    VK_F5 = 0x74
    VK_F11 = 0x7A
    VK_MEDIA_NEXT_TRACK = 0xB0
    VK_MEDIA_PREV_TRACK = 0xB1
    VK_MEDIA_PLAY_PAUSE = 0xB3
    VK_VOLUME_UP = 0xAF
    VK_VOLUME_DOWN = 0xAE
    VK_VOLUME_MUTE = 0xAD

    class KEYBDINPUT(ctypes.Structure):
        _fields_ = [
            ("wVk", ctypes.wintypes.WORD),
            ("wScan", ctypes.wintypes.WORD),
            ("dwFlags", ctypes.wintypes.DWORD),
            ("time", ctypes.wintypes.DWORD),
            ("dwExtraInfo", ctypes.POINTER(ctypes.c_ulong)),
        ]

    class _KBD_UNION(ctypes.Union):
        _fields_ = [("ki", KEYBDINPUT)]

    class INPUT(ctypes.Structure):
        _fields_ = [
            ("type", ctypes.wintypes.DWORD),
            ("_u", _KBD_UNION),
        ]


    def _send_input(*inp: INPUT) -> int:
        n = len(inp)
        arr = (INPUT * n)(*inp)
        return user32.SendInput(n, ctypes.byref(arr), ctypes.sizeof(INPUT))


    def _kbd_input(vk: int, flags: int = 0) -> INPUT:
        inp = INPUT()
        inp.type = INPUT_KEYBOARD
        inp._u.ki = KEYBDINPUT()
        inp._u.ki.wVk = vk
        inp._u.ki.wScan = 0
        inp._u.ki.dwFlags = flags
        inp._u.ki.time = 0
        inp._u.ki.dwExtraInfo = None
        return inp

# VK name -> code mapping
_VK_MAP: dict[str, int] = {
    "backspace": VK_BACK if _IS_WIN else 0x08,
    "return": VK_RETURN if _IS_WIN else 0x0D,
    "enter": VK_RETURN if _IS_WIN else 0x0D,
    "escape": VK_ESCAPE if _IS_WIN else 0x1B,
    "esc": VK_ESCAPE if _IS_WIN else 0x1B,
    "space": VK_SPACE if _IS_WIN else 0x20,
    "tab": VK_TAB if _IS_WIN else 0x09,
    "delete": VK_DELETE if _IS_WIN else 0x2E,
    "up": VK_UP if _IS_WIN else 0x26,
    "down": VK_DOWN if _IS_WIN else 0x28,
    "left": VK_LEFT if _IS_WIN else 0x25,
    "right": VK_RIGHT if _IS_WIN else 0x27,
    "lwin": VK_LWIN if _IS_WIN else 0x5B,
    "win": VK_LWIN if _IS_WIN else 0x5B,
    "alt": VK_MENU if _IS_WIN else 0x12,
    "shift": VK_SHIFT if _IS_WIN else 0x10,
    "ctrl": VK_CONTROL if _IS_WIN else 0x11,
    "control": VK_CONTROL if _IS_WIN else 0x11,
    "f1": 0x70,
    "f2": 0x71,
    "f3": 0x72,
    "f4": 0x73,
    "f5": 0x74,
    "f6": 0x75,
    "f7": 0x76,
    "f8": 0x77,
    "f9": 0x78,
    "f10": 0x79,
    "f11": 0x7A,
    "f12": 0x7B,
    "media_next": VK_MEDIA_NEXT_TRACK if _IS_WIN else 0xB0,
    "media_prev": VK_MEDIA_PREV_TRACK if _IS_WIN else 0xB1,
    "media_play_pause": VK_MEDIA_PLAY_PAUSE if _IS_WIN else 0xB3,
    "volume_up": VK_VOLUME_UP if _IS_WIN else 0xAF,
    "volume_down": VK_VOLUME_DOWN if _IS_WIN else 0xAE,
    "volume_mute": VK_VOLUME_MUTE if _IS_WIN else 0xAD,
}

# Char -> VK code for printable ASCII
_CHAR_TO_VK: dict[str, int] = {}
if _IS_WIN:
    for c in range(ord('A'), ord('Z') + 1):
        _CHAR_TO_VK[chr(c).lower()] = c
        _CHAR_TO_VK[chr(c).upper()] = c
    for c in range(ord('0'), ord('9') + 1):
        _CHAR_TO_VK[chr(c)] = c


class KeyboardController:
    """Inject keyboard events and shortcuts."""

    def key_press(self, key: str) -> None:
        vk = _resolve_vk(key)
        if vk is None or not _IS_WIN:
            return
        _send_input(_kbd_input(vk), _kbd_input(vk, KEYEVENTF_KEYUP))

    def key_down(self, key: str) -> None:
        vk = _resolve_vk(key)
        if vk and _IS_WIN:
            _send_input(_kbd_input(vk))

    def key_up(self, key: str) -> None:
        vk = _resolve_vk(key)
        if vk and _IS_WIN:
            _send_input(_kbd_input(vk, KEYEVENTF_KEYUP))

    def hotkey(self, *keys: str) -> None:
        """Press a key combination, e.g. hotkey('ctrl', 'alt', 'h')."""
        vks = [_resolve_vk(k) for k in keys]
        vks = [v for v in vks if v is not None]
        if not vks or not _IS_WIN:
            return
        for vk in vks:
            _send_input(_kbd_input(vk))
        for vk in reversed(vks):
            _send_input(_kbd_input(vk, KEYEVENTF_KEYUP))

    def type_text(self, text: str, delay_ms: float = 0) -> None:
        """Type a string character by character using key events."""
        for ch in text:
            vk = _CHAR_TO_VK.get(ch.lower())
            if vk is not None:
                self.key_press(ch.upper() if ch.isupper() else ch.lower())
            else:
                # Fall back to Unicode input
                _type_unicode_char(ch)
            if delay_ms > 0:
                time.sleep(delay_ms / 1000.0)

    def press_enter(self) -> None:
        self.key_press("enter")

    def press_key(self, code: str) -> None:
        """Press a single key from the virtual keyboard.

        Resolves the key as a virtual-key code when possible (letters,
        digits, modifiers, function keys); otherwise types it as a Unicode
        character – which is how emoji and symbols are inserted reliably
        regardless of the active keyboard layout.
        """
        if not code:
            return
        if _resolve_vk(code) is not None:
            self.key_press(code)
        else:
            self.type_text(code)

    def press_escape(self) -> None:
        self.key_press("escape")

    def press_backspace(self) -> None:
        self.key_press("backspace")

    def press_tab(self) -> None:
        self.key_press("tab")

    def press_space(self) -> None:
        self.key_press("space")

    # Convenience
    def alt_tab(self) -> None:
        self.hotkey("alt", "tab")

    def ctrl_c(self) -> None:
        self.hotkey("ctrl", "c")

    def ctrl_v(self) -> None:
        self.hotkey("ctrl", "v")

    def ctrl_z(self) -> None:
        self.hotkey("ctrl", "z")

    def ctrl_a(self) -> None:
        self.hotkey("ctrl", "a")

    def media_play_pause(self) -> None:
        self.key_press("media_play_pause")

    def media_next(self) -> None:
        self.key_press("media_next")

    def media_prev(self) -> None:
        self.key_press("media_prev")

    def volume_up(self) -> None:
        self.key_press("volume_up")

    def volume_down(self) -> None:
        self.key_press("volume_down")

    def volume_mute(self) -> None:
        self.key_press("volume_mute")

    def win_key(self) -> None:
        self.key_press("win")


def _resolve_vk(key: str) -> int | None:
    if key.lower() in _VK_MAP:
        return _VK_MAP[key.lower()]
    if len(key) == 1 and key in _CHAR_TO_VK:
        return _CHAR_TO_VK[key]
    # Single alphabetic char -> its natural VK (A..Z). Symbols and non-ASCII
    # characters (emoji, accented letters) must NOT map to a VK: they are
    # inserted via the Unicode fallback instead.
    if len(key) == 1 and key.upper().isalpha():
        return ord(key.upper())
    _LOG.warning("Unknown key: %s", key)
    return None


def _type_unicode_char(ch: str) -> None:
    """Type a single Unicode character using KEYEVENTF_UNICODE."""
    if not _IS_WIN:
        return

    class _U_KBD(ctypes.Structure):
        _fields_ = [
            ("wVk", ctypes.wintypes.WORD),
            ("wScan", ctypes.wintypes.WORD),
            ("dwFlags", ctypes.wintypes.DWORD),
            ("time", ctypes.wintypes.DWORD),
            ("dwExtraInfo", ctypes.POINTER(ctypes.c_ulong)),
        ]

    class _U_UNION(ctypes.Union):
        _fields_ = [("ki", _U_KBD)]

    class _INPUT(ctypes.Structure):
        _fields_ = [("type", ctypes.wintypes.DWORD), ("_u", _U_UNION)]

    inp_down = _INPUT()
    inp_down.type = 1  # INPUT_KEYBOARD
    inp_down._u.ki.wVk = 0
    inp_down._u.ki.wScan = ord(ch)
    inp_down._u.ki.dwFlags = 0x0004  # KEYEVENTF_UNICODE
    inp_down._u.ki.time = 0
    inp_down._u.ki.dwExtraInfo = None

    inp_up = _INPUT()
    inp_up.type = 1
    inp_up._u.ki.wVk = 0
    inp_up._u.ki.wScan = ord(ch)
    inp_up._u.ki.dwFlags = 0x0004 | 0x0002  # KEYEVENTF_UNICODE | KEYEVENTF_KEYUP
    inp_up._u.ki.time = 0
    inp_up._u.ki.dwExtraInfo = None

    arr = (_INPUT * 2)(inp_down, inp_up)
    user32.SendInput(2, ctypes.byref(arr), ctypes.sizeof(_INPUT))


# Keyboard shortcut table for common Windows actions
WINDOWS_SHORTCUTS: dict[str, list[str]] = {
    "alt_tab": ["alt", "tab"],
    "alt_f4": ["alt", "f4"],
    "ctrl_alt_del": ["ctrl", "alt", "delete"],
    "win_d": ["win", "d"],
    "win_e": ["win", "e"],
    "win_l": ["win", "l"],
    "alt_esc": ["alt", "escape"],
    "ctrl_w": ["ctrl", "w"],
    "ctrl_t": ["ctrl", "t"],
    "ctrl_shift_t": ["ctrl", "shift", "t"],
    "ctrl_n": ["ctrl", "n"],
    "f11": ["f11"],
    "f5": ["f5"],
}