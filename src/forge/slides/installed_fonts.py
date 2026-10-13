"""Which font families this Windows computer has (TODO L3, D-330), so a deck that names a font the computer lacks is flagged: the
PowerPoint preview and the fit check would silently draw it in a substitute, and a fit check on the wrong font proves nothing.

Read from the font lists of the registry (machine and current user; fonts installed per user by `install-fonts.ps1` are listed in
the user's). Elsewhere there is no answer (None) and nothing is flagged."""

from __future__ import annotations

import re
import sys
from functools import lru_cache

STYLE_WORDS = {
    "regular",
    "bold",
    "italic",
    "light",
    "medium",
    "semibold",
    "extrabold",
    "black",
    "thin",
    "demi",
    "oblique",
    "condensed",
}
KEYS = (
    ("HKEY_LOCAL_MACHINE", r"SOFTWARE\Microsoft\Windows NT\CurrentVersion\Fonts"),
    ("HKEY_CURRENT_USER", r"Software\Microsoft\Windows NT\CurrentVersion\Fonts"),
)


@lru_cache(maxsize=1)
def installed_names() -> frozenset[str] | None:
    """Lower-case font names as the registry lists them ('calibri bold'), or None when this is not Windows."""
    if sys.platform != "win32":
        return None
    import winreg

    names: set[str] = set()
    for hive, path in KEYS:
        try:
            with winreg.OpenKey(getattr(winreg, hive), path) as key:
                index = 0
                while True:
                    try:
                        value_name, _, _ = winreg.EnumValue(key, index)
                    except OSError:
                        break
                    index += 1
                    for part in re.sub(r"\s*\((TrueType|OpenType)\)\s*$", "", value_name).split(" & "):
                        names.add(part.strip().lower())
        except OSError:
            continue
    return frozenset(names)


def is_installed(family: str, names: frozenset[str] | None = None) -> bool | None:
    """True or False for Windows, None when it cannot be known."""
    names = installed_names() if names is None else names
    if names is None:
        return None
    wanted = family.strip().lower()
    for name in names:
        if name == wanted:
            return True
        if name.startswith(wanted + " ") and set(name[len(wanted) :].split()) <= STYLE_WORDS | {"variable"}:
            return True
    return False


def missing_fonts(families: list[str]) -> list[str]:
    """The families that are definitely not installed here (empty when it cannot be known)."""
    return [f for f in dict.fromkeys(families) if f and is_installed(f) is False]
