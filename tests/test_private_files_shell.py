"""D-606: a command that names DebCraft's own private files (token store, browser profiles, login and tunnel
descriptions, app.env) always asks the user, whatever way the path is spelled."""

from __future__ import annotations

from pathlib import Path

import pytest

from forge.safety.shell_classifier import ShellScope, classify

WORKSPACE = Path("/ws")


def level(command: str) -> tuple[str, bool]:
    scope = ShellScope(workspace_root=WORKSPACE, original_repo=Path("/repo"), cwd=WORKSPACE / "repo")
    result = classify(command, scope)
    return result.level, result.always_ask


@pytest.mark.parametrize(
    "command",
    [
        r"type C:\Users\me\.forge\tokens.json",
        "cat ~/.forge/tokens.json",
        "python -c \"print(open('tokens.json'))\" # .forge/tokens.json",
        r"Get-Content C:\Users\me\.forge\app_logins.yaml",
        "cat ~/.forge/tunnels.yaml",
        r"dir C:\Users\me\.forge\browser_profile\dev",
        "cat ~/.forge/app.env",
    ],
)
def test_private_files_always_ask(command: str) -> None:
    assert level(command) == ("ask", True)


@pytest.mark.parametrize("command", ["cat design-tokens.json", "cat src/tokens.json", "ls"])
def test_ordinary_files_are_not_caught(command: str) -> None:
    assert level(command)[0] != "ask" or not level(command)[1]
