"""D-644: a curl that was not run, calls that still fail, made-up settings and data, crashed starts, the verifier's limit."""

from __future__ import annotations

from pathlib import Path

import pytest

from forge.agent.handover_check import curl_note, curls_in, failed_calls_note, made_up_note
from forge.engine.session_host import SessionHost
from forge.llm.base import Message
from forge.protocol.events import EventBus
from forge.safety.redact import Redactor
from forge.subagents.spawn_tool import VERIFIER_RUN_LIMIT, SpawnSubagent
from forge.toolkit.background import BackgroundManager, StartBackground
from forge.toolkit.base import ToolContext
from forge.toolkit.made_up import note_made_up
from forge.toolkit.shell import ShellSession
from forge.workspace.create import create_workspace
from tests.helpers import mocked_router, reply, responses_body, text_output

CURL = """Here it is:
```bash
curl -X POST "http://127.0.0.1:5045/video-agent/index/1/2?x=1" \\
  -H "Authorization: Bearer <token>" -d '{"a": 1}'
```
and curl http://localhost:5045/health
"""


def context() -> ToolContext:
    return ToolContext(workspace=None)  # type: ignore[arg-type]


def test_the_calls_of_a_reply_are_read() -> None:
    assert curls_in(CURL) == [
        ("POST", "http://127.0.0.1:5045/video-agent/index/1/2"),
        ("GET", "http://localhost:5045/health"),
    ]
    assert curls_in("use --data: `curl https://a.example/x -d 1`")[0][0] == "POST"
    assert curls_in("no command here") == []


def test_a_curl_that_was_not_run_or_failed_is_named_once() -> None:
    c = context()
    c.api_calls["GET http://127.0.0.1:5045/health"] = 2  # localhost and 127.0.0.1 are the same machine
    note = curl_note(c, CURL)
    assert "video-agent/index" in note and "you never ran it" in note and "health" not in note
    assert curl_note(c, CURL) == ""
    c.api_calls["POST http://127.0.0.1:5045/video-agent/index/7/9"] = 3  # other ids: the same call
    c.api_failed["POST http://127.0.0.1:5045/video-agent/index/7/9"] = "HTTP 422"
    assert "HTTP 422" in curl_note(c, CURL)
    c.api_failed.clear()
    assert curl_note(c, CURL) == ""


def test_a_local_call_that_still_fails_after_a_code_change_is_named() -> None:
    c = context()
    c.api_calls["POST http://127.0.0.1:5045/ask"] = 6
    c.api_calls["GET https://dev.example.com/x"] = 6
    c.api_failed.update(
        {"POST http://127.0.0.1:5045/ask": "HTTP 422", "GET https://dev.example.com/x": "HTTP 404"}
    )
    assert failed_calls_note(c, 3) == ""  # no code was changed
    c.last_code_edit_step = 5
    note = failed_calls_note(c, 3)
    assert "ask (HTTP 422)" in note and "dev.example.com" not in note
    assert failed_calls_note(c, 3) == ""


def test_invented_settings_and_fake_data_are_named_without_a_value() -> None:
    c = context()
    command = "$env:JWT_SECRET_KEY='abc-local'; $env:AWS_CLIENT_ID='local-client'; $env:API_KEY=$env:REAL; $env:PORT='1'"
    note_made_up(c, command, settings=True)  # check_secrets: fake
    note_made_up(c, "FAKE_MP4_BYTES_FOR_LOCAL_STREAM_CHECK")
    assert c.made_up == {
        "setting JWT_SECRET_KEY",
        "setting AWS_CLIENT_ID",
        "data FAKE_MP4_BYTES_FOR_LOCAL_STREAM_CHECK",
    }
    note = made_up_note(c, "I used a made-up JWT_SECRET_KEY.")
    assert (
        "AWS_CLIENT_ID" in note
        and "FAKE_MP4" in note
        and "JWT_SECRET_KEY" not in note
        and "abc-local" not in note
    )
    assert "JWT_SECRET_KEY" in made_up_note(c, "done") and made_up_note(c, "done") == ""


async def test_the_verifier_has_a_limit_for_one_request() -> None:
    c = context()
    c.router = object()  # type: ignore[assignment]
    c.verifier_runs = VERIFIER_RUN_LIMIT
    tool = SpawnSubagent()
    result = await tool.run(tool.Args(agent="verifier", task="check"), c)
    assert not result.ok and "that is the limit" in result.content


async def test_a_program_that_crashes_is_never_ready(original_repo: Path, tmp_path: Path) -> None:
    workspace = create_workspace(original_repo, tmp_path / "ws", "backend")
    c = ToolContext(workspace=workspace, shell=ShellSession(workspace), background=BackgroundManager())
    (Path(workspace.repo_dir) / "crash_app.py").write_text(
        "import time\nprint('Traceback (most recent call last):', flush=True)\n"
        "print('KeyError: X', flush=True)\ntime.sleep(60)\n",
        encoding="utf-8",
    )
    assert c.background is not None
    try:
        args = StartBackground.Args(
            name="app", command="python crash_app.py", ready_pattern="Traceback|Running", cwd="."
        )
        result = await StartBackground().run(args, c)
    finally:
        await c.background.stop_all()
    assert not result.ok and "NOT ready" in result.content and "KeyError: X" in result.content


async def test_the_loop_asks_for_the_curl_to_be_proven_before_it_ends(
    original_repo: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    answers = iter(["Run: curl http://127.0.0.1:9/never", "Not run: nothing listens there."])
    workspace = create_workspace(original_repo, tmp_path / "ws", "backend")
    host = SessionHost(
        mocked_router(lambda request: reply(request, responses_body([text_output(next(answers))]))),
        EventBus(redactor=Redactor()),
        workspace=workspace,
    )
    assert host.agent is not None

    async def no_delta(delta: str) -> None:
        return None

    history = [Message.system("s"), Message.user("give me the curl")]
    await host.agent.run(history, no_delta)
    said = [m.content for m in history if m.role == "assistant"]
    assert len(said) == 2 and said[1].startswith("Not run")
    assert any(m.role == "system" and "you never ran it" in str(m.content) for m in history)


def test_a_switch_to_a_fake_part_is_made_up_too() -> None:
    c = context()
    note_made_up(c, "$env:APP_FAKE_MODEL='true'; $env:USE_MOCK_DB='0'; python -m app", settings=True)
    assert c.made_up == {"setting APP_FAKE_MODEL"}
