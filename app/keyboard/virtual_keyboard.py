"""Optional on-screen virtual keyboard optimised for air-touch interaction."""
from __future__ import annotations

import enum
import logging
from dataclasses import dataclass
from typing import Optional

_LOG = logging.getLogger(__name__)


class KeyboardLayout(enum.Enum):
    QWERTY_EN = "qwerty_en"
    AZERTY_FR = "azerty_fr"
    ARABIC = "arabic"
    NUMBERS_SYMBOLS = "numbers_symbols"
    EMOJI = "emoji"


@dataclass
class KeyDef:
    label: str
    code: str
    width: int = 1
    shortcut: list[str] | None = None


_LAYOUTS: dict[KeyboardLayout, list[list[KeyDef]]] = {
    KeyboardLayout.QWERTY_EN: [
        [KeyDef("Esc", "escape"), KeyDef("F1", "f1"), KeyDef("F2", "f2"), KeyDef("F3", "f3"), KeyDef("F4", "f4"),
         KeyDef("F5", "f5"), KeyDef("F6", "f6"), KeyDef("F7", "f7"), KeyDef("F8", "f8"),
         KeyDef("F9", "f9"), KeyDef("F10", "f10"), KeyDef("F11", "f11")],
        [KeyDef("`", "`"), KeyDef("1", "1"), KeyDef("2", "2"), KeyDef("3", "3"), KeyDef("4", "4"),
         KeyDef("5", "5"), KeyDef("6", "6"), KeyDef("7", "7"), KeyDef("8", "8"),
         KeyDef("9", "9"), KeyDef("0", "0"), KeyDef("-", "-"), KeyDef("=", "="),
         KeyDef("Bksp", "backspace", 2)],
        [KeyDef("Tab", "tab", 1), KeyDef("Q", "q"), KeyDef("W", "w"), KeyDef("E", "e"),
         KeyDef("R", "r"), KeyDef("T", "t"), KeyDef("Y", "y"), KeyDef("U", "u"),
         KeyDef("I", "i"), KeyDef("O", "o"), KeyDef("P", "p"), KeyDef("[", "["),
         KeyDef("]", "]"), KeyDef("\\", "\\", 1)],
        [KeyDef("Caps", "tab", 1), KeyDef("A", "a"), KeyDef("S", "s"), KeyDef("D", "d"),
         KeyDef("F", "f"), KeyDef("G", "g"), KeyDef("H", "h"), KeyDef("J", "j"),
         KeyDef("K", "k"), KeyDef("L", "l"), KeyDef(";", ";"), KeyDef("'", "'"),
         KeyDef("Enter", "enter", 2)],
        [KeyDef("Shift", "shift", 2), KeyDef("Z", "z"), KeyDef("X", "x"), KeyDef("C", "c"),
         KeyDef("V", "v"), KeyDef("B", "b"), KeyDef("N", "n"), KeyDef("M", "m"),
         KeyDef(",", ","), KeyDef(".", "."), KeyDef("/", "/"), KeyDef("Shift", "shift", 2)],
        [KeyDef("Ctrl", "ctrl", 1), KeyDef("Win", "win"), KeyDef("Alt", "alt", 1),
         KeyDef("Space", "space", 5), KeyDef("Alt", "alt", 1), KeyDef("Win", "win"),
         KeyDef("Menu", "menu"), KeyDef("Ctrl", "ctrl", 1)],
    ],
    KeyboardLayout.AZERTY_FR: [
        [KeyDef("Esc", "escape"), KeyDef("1", "1"), KeyDef("2", "2"), KeyDef("3", "3"),
         KeyDef("4", "4"), KeyDef("5", "5"), KeyDef("6", "6"), KeyDef("7", "7"),
         KeyDef("8", "8"), KeyDef("9", "9"), KeyDef("0", "0"), KeyDef("-", "-"),
         KeyDef("=", "="), KeyDef("Bksp", "backspace", 2)],
        [KeyDef("Tab", "tab", 1), KeyDef("A", "a"), KeyDef("Z", "z"), KeyDef("E", "e"),
         KeyDef("R", "r"), KeyDef("T", "t"), KeyDef("Y", "y"), KeyDef("U", "u"),
         KeyDef("I", "i"), KeyDef("O", "o"), KeyDef("P", "p"), KeyDef("^", "^"),
         KeyDef("$", "$")],
        [KeyDef("Caps", "tab", 1), KeyDef("Q", "q"), KeyDef("S", "s"), KeyDef("D", "d"),
         KeyDef("F", "f"), KeyDef("G", "g"), KeyDef("H", "h"), KeyDef("J", "j"),
         KeyDef("K", "k"), KeyDef("L", "l"), KeyDef("M", "m"), KeyDef(u"\u00f9", u"\u00f9"),
         KeyDef("*", "*"), KeyDef("Enter", "enter", 1)],
        [KeyDef("Shift", "shift", 1), KeyDef("<", "<"), KeyDef("W", "w"), KeyDef("X", "x"),
         KeyDef("C", "c"), KeyDef("V", "v"), KeyDef("B", "b"), KeyDef("N", "n"),
         KeyDef(",", ","), KeyDef(";", ";"), KeyDef(":", ":"), KeyDef("!", "!"),
         KeyDef("Shift", "shift", 1)],
        [KeyDef("Ctrl", "ctrl", 1), KeyDef("Alt", "alt", 1),
         KeyDef("Space", "space", 6), KeyDef("Alt", "alt", 1), KeyDef("Ctrl", "ctrl", 1)],
    ],
    KeyboardLayout.ARABIC: [
        [KeyDef(u"\u0060", "`"), KeyDef(u"\u0661", "1"), KeyDef(u"\u0662", "2"),
         KeyDef(u"\u0663", "3"), KeyDef(u"\u0664", "4"), KeyDef(u"\u0665", "5"),
         KeyDef(u"\u0666", "6"), KeyDef(u"\u0667", "7"), KeyDef(u"\u0668", "8"),
         KeyDef(u"\u0669", "9"), KeyDef(u"\u0660", "0"), KeyDef("-", "-"),
         KeyDef("Bksp", "backspace", 2)],
        [KeyDef(u"\u064e", "q"), KeyDef(u"\u0648", "w"), KeyDef(u"\u0639", "e"),
         KeyDef(u"\u0631", "r"), KeyDef(u"\u064a", "t"), KeyDef(u"\u0629", "y"),
         KeyDef(u"\u0647", "u"), KeyDef(u"\u0641", "i"), KeyDef(u"\u0635", "o"),
         KeyDef(u"\u062f", "p"), KeyDef(u"\u062e", "["), KeyDef(u"\u062c", "]"),
         KeyDef("\\", "\\", 1)],
        [KeyDef("Enter", "enter", 1), KeyDef(u"\u0634", "a"), KeyDef(u"\u0627", "s"),
         KeyDef(u"\u064a", "d"), KeyDef(u"\u0628", "f"), KeyDef(u"\u0644", "g"),
         KeyDef(u"\u0625", "h"), KeyDef(u"\u064a", "j"), KeyDef(u"\u062a", "k"),
         KeyDef(u"\u0646", "l"), KeyDef(u"\u0645", ";"), KeyDef(u"\u0643", "'"),
         KeyDef(u"\u0637", "\\", 1)],
    ],
    KeyboardLayout.NUMBERS_SYMBOLS: [
        [KeyDef("Esc", "escape"), KeyDef("1", "1"), KeyDef("2", "2"), KeyDef("3", "3"),
         KeyDef("4", "4"), KeyDef("5", "5"), KeyDef("6", "6"), KeyDef("7", "7"),
         KeyDef("8", "8"), KeyDef("9", "9"), KeyDef("0", "0"), KeyDef("-", "-"),
         KeyDef("=", "="), KeyDef("Bksp", "backspace", 2)],
        [KeyDef("Tab", "tab", 1), KeyDef("[", "["), KeyDef("]", "]"), KeyDef("{", "{"),
         KeyDef("}", "}"), KeyDef(";", ";"), KeyDef(":", ":"), KeyDef("'", "'"),
         KeyDef('"', '"'), KeyDef(",", ","), KeyDef(".", "."), KeyDef("/", "/"),
         KeyDef("\\", "\\", 2)],
        [KeyDef("Shift", "shift", 2), KeyDef("!", "!"), KeyDef("@", "@"), KeyDef("#", "#"),
         KeyDef("$", "$"), KeyDef("%", "%"), KeyDef("^", "^"), KeyDef("&", "&"),
         KeyDef("*", "*"), KeyDef("(", "("), KeyDef(")", ")"), KeyDef("_", "_"),
         KeyDef("+", "+")],
        [KeyDef("Ctrl", "ctrl", 1), KeyDef("Alt", "alt", 1),
         KeyDef("Space", "space", 6), KeyDef("Alt", "alt", 1), KeyDef("Ctrl", "ctrl", 2)],
    ],
}

_EMOJI_ROWS = [
    [KeyDef(u"\U0001f600", u"\U0001f600"), KeyDef(u"\U0001f642", u"\U0001f642"),
     KeyDef(u"\U0001f609", u"\U0001f609"), KeyDef(u"\U0001f60d", u"\U0001f60d"),
     KeyDef(u"\U0001f914", u"\U0001f914"), KeyDef(u"\U0001f923", u"\U0001f923"),
     KeyDef(u"\U0001f62d", u"\U0001f62d"), KeyDef(u"\U0001f621", u"\U0001f621")],
    [KeyDef(u"\U0001f44d", u"\U0001f44d"), KeyDef(u"\U0001f44e", u"\U0001f44e"),
     KeyDef(u"\U0001f44b", u"\U0001f44b"), KeyDef(u"\U0001f44f", u"\U0001f44f"),
     KeyDef(u"\U0001f525", u"\U0001f525"), KeyDef(u"\u2764\ufe0f", u"\u2764\ufe0f"),
     KeyDef(u"\U0001f680", u"\U0001f680"), KeyDef(u"\u2b50", u"\u2b50")],
]

_LAYOUTS[KeyboardLayout.EMOJI] = _EMOJI_ROWS  # type: ignore[assignment]


class VirtualKeyboard:
    """Provides keyboard layout definitions for on-screen rendering."""

    def __init__(self, layout: KeyboardLayout = KeyboardLayout.QWERTY_EN) -> None:
        self.layout = layout

    @property
    def keys(self) -> list[list[KeyDef]]:
        return _LAYOUTS.get(self.layout, _LAYOUTS[KeyboardLayout.QWERTY_EN])

    def set_layout(self, layout) -> None:
        if isinstance(layout, int):
            layout = KeyboardLayout(layout)
        self.layout = layout

    @property
    def available_layouts(self) -> list[KeyboardLayout]:
        return list(KeyboardLayout)