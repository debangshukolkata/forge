"""D-187: shell commands that reach Forge's own .env or folder indirectly (a variable, a name inside a quoted
string) are always asked about, never run silently and never remembered as "always allow"."""

from __future__ import annotations

from pathlib import Path

import pytest

from forge.safety.shell_classifier import ShellScope, classify


@pytest.fixture
def scope(tmp_path: Path) -> ShellScope:
    return ShellScope(workspace_root=tmp_path, original_repo=None, cwd=tmp_path)


@pytest.mark.parametrize(
    "command",
    [
        r"Get-Content $env:FORGE_ENV_FILE",
        r"type %FORGE_ENV_FILE%",
        r"Get-Content ($env:USERPROFILE + '\.forge\.e*')",
        r"Get-ChildItem $HOME\.forge -Force",
        r'Get-Content "$env:APPDATA\forge\x"',
        "python -c \"print(open('.env').read())\"",
        r"""python -c "print(open(r'C:\Users\a\.forge\.env').read())" """,
        "python -c \"print(open('../.env.local').read())\"",
        r"Get-Content ..\.env",
    ],
)
def test_indirect_secret_reads_always_ask(scope: ShellScope, command: str) -> None:
    result = classify(command, scope)
    assert result.level in ("ask", "blocked") and result.always_ask, command


@pytest.mark.parametrize(
    "command",
    [
        "Get-Content README.md",
        "cat .env.example",
        "Get-Content config.env.sample",
        "python -m pytest -q",
        "git status",
        "Get-ChildItem Env:",
        "python -c \"print('environment')\"",
    ],
)
def test_ordinary_commands_are_not_caught(scope: ShellScope, command: str) -> None:
    assert not classify(command, scope).always_ask, command
