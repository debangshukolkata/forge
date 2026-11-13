"""D-597: DebCraft writes down how it ran the system, so a new session or conversation does not start over."""

from __future__ import annotations

import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from types import SimpleNamespace

import httpx2

from forge.engine.session_host import SessionHost
from forge.protocol.events import EventBus
from forge.safety.redact import Redactor
from forge.toolkit.background import BackgroundManager, StartBackground, StopBackground
from forge.toolkit.base import ToolContext
from forge.toolkit.shell import ShellSession
from forge.tools.conversation_recall import ConversationRecall
from forge.tools.http_request import HttpRequest
from forge.workspace.conversations import ConversationStore
from forge.workspace.create import create_workspace
from forge.workspace.run_notes import RunNotes
from tests.helpers import mocked_router

FAKE_KEY = "sk-live-" + "5d2e8a1c" * 4  # check_secrets: fake


def _workspace(original_repo: Path, tmp_path: Path):  # type: ignore[no-untyped-def]
    return create_workspace(original_repo, tmp_path / "ws", "backend")


def test_starts_and_calls_are_recorded_replaced_and_capped(original_repo: Path, tmp_path: Path) -> None:
    workspace = _workspace(original_repo, tmp_path)
    notes = RunNotes(workspace)
    assert notes.render() is None

    notes.record_start("agent", "python -m app --port {port}", "backend", 8765, ["DATABASE_URL", "DB_HOST"])
    notes.record_start("agent", "python -m app --port {port} --reload", "backend", 8766, ["DATABASE_URL"])
    notes.record_call("POST", "http://127.0.0.1:8766/api/run?debug=1", {"question": "hi"}, "DEV_TOKEN", 200)
    notes.record_call("POST", "http://127.0.0.1:8766/api/run", {"question": "again"}, "DEV_TOKEN", 200)
    text = notes.render() or ""

    assert (
        text.count("Started 'agent'") == 1 and "--reload" in text and "port 8766" in text
    )  # replaced, not added
    assert "settings it was given: DATABASE_URL" in text
    assert text.count("Worked: POST") == 1 and "again" in text and "debug=1" not in text  # no query string
    assert "token from DEV_TOKEN" in text

    for number in range(12):
        notes.record_start(f"p{number}", "x", None, None, [])
        notes.record_call("GET", f"http://127.0.0.1:1/{number}", None, "", 200)
    data = notes.load()
    assert len(data["starts"]) == 6 and len(data["calls"]) == 8


def test_no_secret_is_written_to_the_notes(original_repo: Path, tmp_path: Path) -> None:
    workspace = _workspace(original_repo, tmp_path)
    notes = RunNotes(workspace)
    notes.record_start("api", f"python app.py --key {FAKE_KEY}", None, 1, [])
    notes.record_call("POST", "http://127.0.0.1:1/x", {"api_key": FAKE_KEY}, "TOKEN_NAME", 200)

    assert FAKE_KEY not in notes.path.read_text(encoding="utf-8")
    assert "TOKEN_NAME" in notes.path.read_text(encoding="utf-8")  # the name of a variable is fine


def test_a_damaged_notes_file_is_ignored(original_repo: Path, tmp_path: Path) -> None:
    workspace = _workspace(original_repo, tmp_path)
    notes = RunNotes(workspace)
    notes.path.parent.mkdir(parents=True, exist_ok=True)
    for text in ("{not json", '{"version": 99, "starts": [{"name": "x"}]}', "[]"):
        notes.path.write_text(text, encoding="utf-8")
        assert notes.render() is None
    notes.record_start("ok", "run", None, None, [])  # and it can be written again over the damage
    assert "Started 'ok'" in (notes.render() or "")


async def test_a_started_process_writes_its_own_note_and_the_pin(original_repo: Path, tmp_path: Path) -> None:
    workspace = _workspace(original_repo, tmp_path)
    pinned: dict[str, str | None] = {}
    context = ToolContext(
        workspace=workspace,
        shell=ShellSession(workspace),
        background=BackgroundManager(),
        pin=lambda slot, text: pinned.__setitem__(slot, text),
    )
    command = 'Write-Output "agent ready"; Start-Sleep -Seconds 20'
    try:
        started = await StartBackground().run(
            StartBackground.Args(name="agent", command=command, ready_pattern="agent ready", timeout_s=30),
            context,
        )
        assert started.ok, started.content
    finally:
        await StopBackground().run(StopBackground.Args(name="agent"), context)

    text = RunNotes(workspace).render() or ""
    assert "Started 'agent'" in text and "agent ready" in text
    assert pinned["run_notes"] == text  # the model sees it at once, not only in the next session


class _Echo(BaseHTTPRequestHandler):
    def do_POST(self) -> None:
        length = int(self.headers.get("Content-Length") or 0)
        self.rfile.read(length)
        body = json.dumps({"ok": True}).encode()
        self.send_response(200 if self.path == "/ok" else 500)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *args: object) -> None:
        pass


async def test_a_call_that_worked_is_written_down_and_one_that_failed_is_not(
    original_repo: Path, tmp_path: Path, monkeypatch
) -> None:  # type: ignore[no-untyped-def]
    import threading

    server = ThreadingHTTPServer(("127.0.0.1", 0), _Echo)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    workspace = _workspace(original_repo, tmp_path)
    env_file = tmp_path / "debcraft.env"
    env_file.write_text(f"DEVELOPMENT_INSTANCE_TOKEN={FAKE_KEY}\n", encoding="utf-8")
    monkeypatch.setenv("FORGE_ENV_FILE", str(env_file))
    monkeypatch.delenv("DEVELOPMENT_INSTANCE_TOKEN", raising=False)
    context = ToolContext(workspace=workspace)
    base = f"http://127.0.0.1:{server.server_port}"
    try:
        good = await HttpRequest().run(
            HttpRequest.Args(
                method="POST",
                url=f"{base}/ok",
                json={"question": "names?"},
                token_env="DEVELOPMENT_INSTANCE_TOKEN",
            ),
            context,
        )
        bad = await HttpRequest().run(HttpRequest.Args(method="POST", url=f"{base}/fail", json={}), context)
    finally:
        server.shutdown()
    assert good.ok and "HTTP 200" in good.content
    assert "HTTP 500" in bad.content

    data = RunNotes(workspace).load()
    assert [call["url"] for call in data["calls"]] == [f"{base}/ok"]
    assert data["calls"][0]["token_env"] == "DEVELOPMENT_INSTANCE_TOKEN"
    assert FAKE_KEY not in RunNotes(workspace).path.read_text(encoding="utf-8")


async def test_a_new_session_pins_how_the_project_was_run(original_repo: Path, tmp_path: Path) -> None:
    workspace = _workspace(original_repo, tmp_path)
    RunNotes(workspace).record_start(
        "agent", "python -m argocd_agent --port {port}", "backend", 8765, ["DB_HOST"]
    )

    def unreachable(request: httpx2.Request) -> httpx2.Response:
        raise AssertionError("no model call expected")

    host = SessionHost(mocked_router(unreachable), EventBus(redactor=Redactor()), workspace=workspace)
    pin = host.context_manager.pinned.get("run_notes") or ""
    assert "python -m argocd_agent --port {port}" in pin
    assert "How this project was run before" in host.context_manager.pinned.render(5000)
    await host.close()


def test_the_database_line_names_the_tables_and_settings_already_in_place(
    original_repo: Path, tmp_path: Path
) -> None:
    from forge.db.session import DbSession

    workspace = _workspace(original_repo, tmp_path)
    session = DbSession.__new__(DbSession)  # only the line is under test, not a connection
    session.workspace = workspace
    session.reports = {}
    session.requests = SimpleNamespace(all=lambda: [])  # type: ignore[assignment]
    session.scratch = SimpleNamespace(  # type: ignore[assignment]
        target=SimpleNamespace(name="local"),
        schema="forge_scratch_x",
        key="local:forge_scratch_x",
        registry=SimpleNamespace(
            objects=lambda key: [("schema", "forge_scratch_x"), ("table", "agents"), ("table", "tools")]
        ),
    )
    (workspace.forge_dir).mkdir(parents=True, exist_ok=True)
    session.app_variables = lambda: {"DATABASE_URL": "url"}  # type: ignore[method-assign]
    session.reports = {"local": SimpleNamespace(line=lambda: "local: L3")}  # type: ignore[assignment]

    line = session.status_line()
    assert "Scratch schema in use: local / forge_scratch_x" in line
    assert "tables already in it" in line and "agents, tools" in line
    assert "DATABASE_URL already point at it" in line and "applied automatically at session start" in line


async def test_recall_lists_the_steps_that_ran_the_system(original_repo: Path, tmp_path: Path) -> None:
    workspace = _workspace(original_repo, tmp_path)
    store = ConversationStore(workspace)
    log = store.events_path("c1")
    log.parent.mkdir(parents=True, exist_ok=True)
    events = [
        {"type": "user_message", "payload": {"text": "run the argocd agent"}},
        {"type": "tool_call_started", "payload": {"name": "read_file", "summary": "read a.py"}},
        {"type": "tool_call_started", "payload": {"name": "db_copy_table", "summary": "copy table agents"}},
        {
            "type": "tool_call_started",
            "payload": {
                "name": "start_background",
                "summary": f"start 'agent': python -m x --key {FAKE_KEY}",
            },
        },
        {
            "type": "tool_call_started",
            "payload": {"name": "http_request", "summary": "POST http://127.0.0.1:8765/run"},
        },
    ]
    log.write_text("\n".join(json.dumps(e) for e in events) + "\n", encoding="utf-8")
    store.create("second")

    result = await ConversationRecall().run(
        ConversationRecall.Args(id="c1", what="steps"), ToolContext(workspace=workspace)
    )

    assert result.ok and "copy table agents" in result.content and "start 'agent'" in result.content
    assert "POST http://127.0.0.1:8765/run" in result.content
    assert "read a.py" not in result.content and "run the argocd agent" not in result.content
    assert FAKE_KEY not in result.content
