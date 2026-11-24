"""Invented settings and fake data the application was run with (D-644): names only, never a value."""

from __future__ import annotations

import re

from forge.toolkit.base import ToolContext

SECRET_SETTING = re.compile(
    r"(?:\$env:|\bexport\s+|\bset\s+|(?<![\w$]))([A-Z][A-Z0-9_]*(?:SECRET|PASSWORD|TOKEN|_KEY|KEY_STRING|CLIENT_ID)[A-Z0-9_]*)"
    r"\s*=\s*['\"]?([^\s'\";&|]+)"
)
# a switch that replaces a real part, such as APP_FAKE_MODEL=true (seen in a live run as the only proof)
FAKE_SWITCH = re.compile(
    r"(?:\$env:|\bexport\s+|\bset\s+|(?<![\w$]))([A-Z][A-Z0-9_]*(?:FAKE|MOCK|STUB|DUMMY)[A-Z0-9_]*)\s*=\s*['\"]?(?!0\b|false|no\b|off\b)\w",
    re.IGNORECASE,
)
MADE_UP_DATA = re.compile(
    r"\b(?:FAKE|DUMMY|MOCK)_[A-Z0-9_]{2,}\b|\bfake[-_ ](?:video|mp4|data|bytes|response)\b"
)


def note_made_up(context: ToolContext, text: str, settings: bool = False) -> None:
    """Remembers invented settings in a command (their names, never a value) and fake data in what a call returned."""
    if settings:
        for name, value in SECRET_SETTING.findall(text):
            if not value.startswith(("$", "%", "(", "<")):  # a reference to a real value is not invented
                context.made_up.add(f"setting {name}")
        for name in FAKE_SWITCH.findall(text):
            context.made_up.add(f"setting {name}")
    for match in MADE_UP_DATA.findall(text)[:5]:
        context.made_up.add(f"data {match[:40]}")
