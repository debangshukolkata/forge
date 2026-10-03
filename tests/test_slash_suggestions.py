"""D-198: the web message box suggests exactly the slash commands the engine has (it once kept suggesting
seven that had been removed)."""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
NOT_SUGGESTED = {"/exit"}  # ends the terminal session; a browser tab has no use for it


def engine_commands() -> set[str]:
    source = (ROOT / "src" / "forge" / "engine" / "slash_commands.py").read_text(encoding="utf-8")
    return set(re.findall(r'^\s+"(/[\w-]+)":\s*self\.', source, re.M))


def suggested_commands() -> set[str]:
    source = (ROOT / "ui-react" / "src" / "components" / "Composer.tsx").read_text(encoding="utf-8")
    start = source.index("const SLASH = [")
    block = source[start : source.index("];", start)]
    return set(re.findall(r'"(/[\w-]+)(?: [^"]*)?"', block))


def test_every_suggestion_is_a_real_command() -> None:
    assert suggested_commands() - engine_commands() == set()


def test_every_real_command_is_suggested() -> None:
    assert engine_commands() - suggested_commands() - NOT_SUGGESTED == set()
