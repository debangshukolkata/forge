"""RS9 (D-599): a streamed answer is read by event. The summariser is pure; the call goes through a real local server."""

from __future__ import annotations

import json
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import pytest

from forge.toolkit.base import ToolContext
from forge.tools.http_request import HttpRequest
from forge.tools.stream_summary import parse_stream, summarize_stream
from forge.workspace.create import create_workspace
from forge.workspace.run_notes import RunNotes

FAKE_KEY = "console-" + "4k9Zq2Lm" * 4  # check_secrets: fake


def sse(*events: tuple[float, str, dict[str, object] | str]) -> list[tuple[float, str]]:
    """(second, event name, data) as the lines a server-sent stream is made of."""
    lines: list[tuple[float, str]] = []
    for at, name, data in events:
        text = data if isinstance(data, str) else json.dumps(data)
        if name:
            lines.append((at, f"event: {name}"))
        lines.append((at, f"data: {text}"))
        lines.append((at, ""))
    return lines


def test_server_sent_events_are_grouped_by_their_blank_lines() -> None:
    events = parse_stream(
        sse(
            (0.1, "run_started", {"agent": "ops"}),
            (0.4, "", {"type": "tool_call", "name": "list_deployments"}),
        )
    )
    assert [(e.kind, round(e.at, 1)) for e in events] == [("run_started", 0.1), ("tool_call", 0.4)]
    assert events[1].payload == {"type": "tool_call", "name": "list_deployments"}


def test_the_account_names_the_tool_events_the_silence_the_error_and_the_final_answer() -> None:
    items = sse(
        (0.2, "run_started", {"agent": "ops"}),
        (0.9, "", {"type": "tool_call", "name": "list_deployments"}),
        (9.5, "", {"type": "tool_result", "name": "list_deployments", "content": "x" * 3000}),
        (9.6, "", {"type": "error", "message": "the result is larger than the context"}),
        (9.7, "", {"type": "final", "answer": "I could not list them."}),
    )
    text = "\n".join(summarize_stream(items, 9.8))

    assert "5 events in 9.8 s" in text and "tool_call x1" in text and "final x1" in text
    assert "tool_call list_deployments" in text and "tool_result list_deployments" in text
    assert text.index("tool_call list_deployments") < text.index("tool_result list_deployments")  # in order
    assert "Longest silence: 8.6 s before the tool_result event" in text  # the call that stalled is visible
    assert "Error event at 9.6 s: the result is larger than the context" in text
    assert "Final answer (22 characters): I could not list them." in text


def test_a_json_lines_stream_is_read_too_and_tokens_are_joined_into_the_answer() -> None:
    items = [
        (0.1, json.dumps({"type": "token", "text": "The names "})),
        (0.2, json.dumps({"type": "token", "text": "are a, b."})),
        (0.3, json.dumps({"type": "tool_call", "tool": "lookup"})),
        (0.4, ""),
    ]
    text = "\n".join(summarize_stream(items, 0.5))
    assert "3 events" in text and "tool_call" in text and "lookup" in text
    assert "Final answer (19 characters): The names are a, b." in text


def test_an_empty_stream_and_one_without_an_answer_say_so() -> None:
    assert summarize_stream([], 3.0) == ["Stream: no events in 3.0 s."]
    text = "\n".join(summarize_stream(sse((0.1, "ping", {"n": 1})), 0.2, cut=True))
    assert "cut at the time limit" in text and "No final answer text was found" in text


class StreamingHandler(BaseHTTPRequestHandler):
    def do_POST(self) -> None:
        self.rfile.read(int(self.headers.get("Content-Length") or 0))
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream")
        self.end_headers()
        auth = self.headers.get("Authorization", "")  # echoes the header, as an API that logs it would
        for at, chunk in (
            (0.0, f"event: run_started\ndata: {json.dumps({'authorization': auth})}\n\n"),
            (0.3, 'data: {"type": "tool_call", "name": "list_deployments"}\n\n'),
            (0.3, 'data: {"type": "final", "answer": "payments-api-000, search-worker-001"}\n\n'),
        ):
            time.sleep(at)
            self.wfile.write(chunk.encode())
            self.wfile.flush()

    def log_message(self, *args: object) -> None:
        pass


@pytest.fixture
def stream_server() -> str:
    server = ThreadingHTTPServer(("127.0.0.1", 0), StreamingHandler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{server.server_port}"  # type: ignore[misc]
    server.shutdown()


async def test_a_streamed_call_returns_the_account_keeps_the_stream_and_hides_the_token(
    stream_server: str, original_repo: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    workspace = create_workspace(original_repo, tmp_path / "ws", "backend")
    env_file = tmp_path / "debcraft.env"
    env_file.write_text(f"DEVELOPMENT_INSTANCE_TOKEN={FAKE_KEY}\n", encoding="utf-8")
    monkeypatch.setenv("FORGE_ENV_FILE", str(env_file))
    monkeypatch.delenv("DEVELOPMENT_INSTANCE_TOKEN", raising=False)
    context = ToolContext(workspace=workspace)

    result = await HttpRequest().run(
        HttpRequest.Args(
            method="POST",
            url=f"{stream_server}/run",
            json={"question": "names?"},
            token_env="DEVELOPMENT_INSTANCE_TOKEN",
            stream=True,
        ),
        context,
    )

    assert result.ok and "HTTP 200" in result.content
    assert "Stream: 3 events" in result.content and "run_started x1" in result.content
    assert "tool_call list_deployments" in result.content
    assert "Final answer" in result.content and "payments-api-000" in result.content
    assert FAKE_KEY not in result.content  # the echoed header is hidden in the account and in the raw start
    assert result.full_output_path is not None
    saved = Path(result.full_output_path).read_text(encoding="utf-8")
    assert "list_deployments" in saved and FAKE_KEY not in saved  # the saved stream is masked too
    assert "stream.txt" in result.full_output_path

    notes = RunNotes(workspace).render() or ""
    assert "stream=true" in notes  # a later session repeats it as a stream


async def test_a_stream_that_never_ends_is_cut_at_the_time_limit(original_repo: Path, tmp_path: Path) -> None:
    class Endless(BaseHTTPRequestHandler):
        def do_POST(self) -> None:
            self.rfile.read(int(self.headers.get("Content-Length") or 0))
            self.send_response(200)
            self.send_header("Content-Type", "text/event-stream")
            self.end_headers()
            try:
                for number in range(1000):
                    self.wfile.write(f'data: {{"type": "tick", "n": {number}}}\n\n'.encode())
                    self.wfile.flush()
                    time.sleep(0.2)
            except OSError:
                pass

        def log_message(self, *args: object) -> None:
            pass

    server = ThreadingHTTPServer(("127.0.0.1", 0), Endless)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    workspace = create_workspace(original_repo, tmp_path / "ws", "backend")
    try:
        result = await HttpRequest().run(
            HttpRequest.Args(
                method="POST",
                url=f"http://127.0.0.1:{server.server_port}/run",
                json={},
                stream=True,
                timeout_s=1,
            ),
            ToolContext(workspace=workspace),
        )
    finally:
        server.shutdown()
    assert result.ok and "cut at the time limit" in result.content and "tick x" in result.content
