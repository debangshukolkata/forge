"""The /skill chat command: add, list or remove skills without leaving the chat (D-225).

Same trust model as `forge skill add` (D-207): only the user's own command installs, never the model. Without
--yes the command only shows what the source holds, so the user decides after seeing it."""

from __future__ import annotations

import asyncio
import shlex
from collections.abc import Awaitable, Callable
from pathlib import Path

from forge.errors import ForgeError
from forge.parity import skill_install
from forge.parity.skills import discover

USAGE = (
    "Usage: /skill add <github.com link or folder> [--yes] [--force] | /skill list | /skill remove <name>\n"
    "Without --yes, add only shows what the source contains; run it again with --yes to install."
)


async def run_skill_command(rest: str, skills_root: Path, say: Callable[[str], Awaitable[None]]) -> bool:
    """Handles one /skill command. Returns True when the installed skills changed."""
    try:
        words = shlex.split(rest, posix=False)
    except ValueError:
        await say(USAGE)
        return False
    action = words[0].lower() if words else ""
    flags = {word for word in words[1:] if word.startswith("--")}
    values = [word.strip("\"'") for word in words[1:] if not word.startswith("--")]
    if action == "list":
        lines = [
            f"{s.name}: {s.description}" for s in sorted(discover(skills_root).values(), key=lambda s: s.name)
        ]
        await say("\n".join(lines) or "No skills installed by you yet.")
        return False
    if action == "remove" and len(values) == 1:
        removed = skill_install.remove(values[0], skills_root)
        await say("Removed." if removed else f"No installed skill named {values[0]!r}.")
        return removed
    if action != "add" or len(values) != 1:
        await say(USAGE)
        return False
    install_now = "--yes" in flags
    shown: list[str] = []

    def confirm(candidate: skill_install.Candidate) -> bool:
        shown.append(skill_install.summary(candidate))
        return install_now

    await say(f"Fetching {values[0]} ...")
    try:
        lines = await asyncio.to_thread(
            skill_install.add_from_source, values[0], skills_root, confirm, "--force" in flags
        )
    except ForgeError as error:
        await say(f"Could not add the skill: {error}")
        return False
    await say("\n".join([*shown, "", *lines]))
    if not install_now:
        await say(
            "Nothing installed yet. To install what you just read, run: /skill add " + values[0] + " --yes"
        )
    return install_now and any("installed in" in line for line in lines)
