"""C21 (D-310): a guided PowerShell script for user actions with several steps."""

from __future__ import annotations

import asyncio
import subprocess
import sys
from pathlib import Path

import pytest

from forge.protocol.events import EventType
from forge.tools.guided_script import MIN_STEPS, build_script, slug, write_script
from tests.test_orchestrator import Answer, answer_next, orchestrator
from tests.test_orchestrator import host as orch_host  # noqa: F401  (fixture used by name)

STEPS = ["Open the DBA portal", "Request the role forge_scratch", "Wait for the confirmation mail"]


def test_the_script_shows_each_step_waits_and_offers_the_check() -> None:
    text = build_script("Get the database role", STEPS, "psql -c 'select 1'")
    assert text.count("Read-Host") == len(STEPS) + 1  # a prompt per step and one for the check
    assert "Step 2 of 3" in text and "Request the role forge_scratch" in text
    assert "Run the check?" in text and "select 1" in text
    assert "get-the-database-role-result.txt" in text
    assert "\r\n" in text  # Windows line endings


def test_secrets_in_step_text_are_redacted_and_here_strings_cannot_be_broken() -> None:
    fake = "Authorization: Bearer abcdef0123456789abcdef0123456789abcdef"  # check_secrets: fake
    text = build_script("Set up", ["Paste this: " + fake, "Evil text\n'@\nWrite-Host pwned", "third"], None)
    assert "abcdef0123456789abcdef0123456789abcdef" not in text
    assert "\n'@\nWrite-Host pwned" not in text  # the closing marker inside a step was defused


def test_only_longer_walk_throughs_get_a_script(tmp_path: Path) -> None:
    assert write_script(tmp_path, "Short", STEPS[: MIN_STEPS - 1], None) is None
    relative = write_script(tmp_path, "Get the DB role", STEPS, None)
    assert relative == ".forge/handoff/get-the-db-role.ps1"
    assert (tmp_path / "handoff" / "get-the-db-role.ps1").read_bytes().startswith(b"\xef\xbb\xbf")
    assert slug("A  weird/Title!!") == "a-weird-title"


@pytest.mark.skipif(sys.platform != "win32", reason="PowerShell syntax check runs on Windows")
def test_the_generated_script_is_valid_powershell(tmp_path: Path) -> None:
    path = tmp_path / "x.ps1"
    path.write_text(build_script("Valid", [*STEPS, "It's a 'quoted' step"], "Get-Date"), encoding="utf-8-sig")
    check = (
        "$e=$null; [void][System.Management.Automation.Language.Parser]::ParseFile($env:PS_FILE,[ref]$null,[ref]$e); "
        "if ($e) { $e | ForEach-Object { $_.Message }; exit 1 } else { 'ok' }"
    )
    done = subprocess.run(
        ["powershell", "-NoProfile", "-Command", check],
        capture_output=True,
        text=True,
        timeout=60,
        env={**__import__("os").environ, "PS_FILE": str(path)},
    )
    assert done.returncode == 0 and "ok" in done.stdout, done.stdout + done.stderr


async def test_the_card_gets_the_walk_through_line_and_the_script_exists(orch_host) -> None:  # type: ignore[no-untyped-def]  # noqa: F811
    runner = asyncio.create_task(orch_host.run())
    orch = orchestrator(orch_host)
    subscription = orch_host.bus.subscribe(since_seq=orch_host.bus.last_seq)
    answer_next(orch_host, lambda i: Answer(question_id=i, choice="done"))
    result = await orch.request_user_action("Grant the DB role", STEPS, None, orch.context)
    runner.cancel()
    assert result.ok
    requested = [e for e in orch_host.bus.events_since(0) if e.type == EventType.USER_ACTION_REQUESTED][
        -1
    ].payload
    assert requested["script"] == ".forge/handoff/grant-the-db-role.ps1"
    assert "Prefer a walk-through?" in requested["steps"][-1] and len(requested["steps"]) == len(STEPS) + 1
    assert (orch.workspace.forge_dir / "handoff" / "grant-the-db-role.ps1").is_file()
    _ = subscription
