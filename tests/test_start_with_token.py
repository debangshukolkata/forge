"""D-648: the fresh sign-in token for one approved program, and for nothing else."""

from __future__ import annotations

import time
from pathlib import Path
from typing import Any

import pytest

from forge.safety.permissions import SHELL_TOOLS
from forge.safety.redact import default_redactor
from forge.toolkit.app_logins import TokenStore
from forge.toolkit.background import BackgroundManager
from forge.toolkit.base import ToolContext
from forge.toolkit.shell import ShellSession, execute
from forge.tools import start_with_token as module
from forge.tools.app_login import Ensured
from forge.tools.start_with_token import StartWithToken, forget_approvals
from forge.workspace.create import create_workspace
from tests.test_app_logins import GOOD, jwt, write_logins

PROGRAM = (
    "import os, time\n"
    "value = os.environ.get('DEV_FILE_TOKEN', '')\n"
    "print('length', len(value), flush=True)\n"
    "print('value', value, flush=True)\n"
    "time.sleep(60)\n"
)


@pytest.fixture
def setup(
    original_repo: Path, tmp_path: Path, isolated_forge_home: Path, monkeypatch: pytest.MonkeyPatch
) -> Any:
    write_logins(isolated_forge_home, GOOD)
    token = jwt(exp=time.time() + 900)
    TokenStore(isolated_forge_home).put("DEV_TOKEN", token)

    async def ensured(login: Any, home: Any = None, ask: Any = None, force: bool = False) -> Ensured:
        return Ensured(TokenStore(home).get(login.token_name) or "")

    monkeypatch.setattr(module, "ensure_token", ensured)
    workspace = create_workspace(original_repo, tmp_path / "ws", "backend")
    context = ToolContext(workspace=workspace, shell=ShellSession(workspace), background=BackgroundManager())
    (Path(workspace.repo_dir) / "prog.py").write_text(PROGRAM, encoding="utf-8")
    asked: list[str] = []
    answers = [True]

    async def card(question: str, details: str, label: str) -> tuple[bool, str]:
        asked.append(question + details)
        return answers[-1], ""

    context.confirm_danger = card
    return context, token, asked, answers


def args(**more: Any) -> Any:
    base = {
        "name": "app", "command": "python prog.py", "ready_pattern": "value", "cwd": ".",
        "variable": "DEV_FILE_TOKEN", "reason": "the file service",
    }  # fmt: skip
    return StartWithToken.Args(**{**base, **more})


async def test_the_program_gets_it_once_approved_and_no_other_command_does(
    setup: Any, isolated_forge_home: Path
) -> None:
    context, token, asked, _ = setup
    try:
        first = await StartWithToken().run(args(), context)
        assert first.ok and f"length {len(token)}" in first.content
        assert token not in default_redactor.redact(first.content)
        assert len(asked) == 1 and "python prog.py" in asked[0] and token not in asked[0]
        again = await StartWithToken().run(args(), context)
        assert again.ok and len(asked) == 1  # the same command is not asked about again
        other = await execute(
            context, "python -c \"import os; print('seen', 'DEV_FILE_TOKEN' in os.environ)\"", 60, None
        )
        assert "seen False" in other.content
        await StartWithToken().run(args(command="python prog.py --x"), context)
        assert len(asked) == 2  # a changed command is
    finally:
        await context.background.stop_all()
    for saved in isolated_forge_home.rglob("*.json"):
        if saved.name != "tokens.json":
            assert token not in saved.read_text(encoding="utf-8")
    log = (isolated_forge_home / "logs" / "field.jsonl").read_text(encoding="utf-8")
    assert "app_token_given" in log and token not in log
    assert forget_approvals(context) and not forget_approvals(context)


async def test_without_approval_nothing_starts(setup: Any) -> None:
    context, _, _, answers = setup
    answers.append(False)
    refused = await StartWithToken().run(args(), context)
    assert not refused.ok and "did not agree" in refused.content and not context.background.processes
    context.confirm_danger = None  # a subagent, a headless run
    assert not (await StartWithToken().run(args(), context)).ok


@pytest.mark.parametrize("variable", ["PATH", "AZURE_OPENAI_API_KEY", "a b", "PYTHONPATH"])
async def test_only_a_name_of_the_application_can_be_used(setup: Any, variable: str) -> None:
    context, _, asked, _ = setup
    assert not (await StartWithToken().run(args(variable=variable), context)).ok and not asked


async def test_an_environment_the_user_did_not_set_up_is_refused(setup: Any) -> None:
    context, _, asked, _ = setup
    assert not (await StartWithToken().run(args(environment="prod"), context)).ok and not asked


def test_its_command_passes_the_permission_gate_like_every_other() -> None:
    assert "start_with_token" in SHELL_TOOLS
