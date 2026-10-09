"""show_app (D-243): only opens a page that comes from the process Forge started."""

from __future__ import annotations

import asyncio
import socket
import sys
from collections import deque
from types import SimpleNamespace

import pytest

from forge.toolkit.background import BackgroundManager, BackgroundProcess
from forge.tools import show_app
from forge.tools.show_app import ShowApp, ports_in_output


def test_ports_in_output_newest_first() -> None:
    lines = ["Serving on http://127.0.0.1:5055", "retry on localhost:5056", "unrelated 12:30"]
    assert ports_in_output(lines) == [5056, 5055]


async def _run(entry: BackgroundProcess, monkeypatch: pytest.MonkeyPatch, opened: list[str]) -> object:
    monkeypatch.setattr(show_app.webbrowser, "open", lambda url: opened.append(url) or True)
    manager = BackgroundManager()
    manager.processes["app"] = entry
    context = SimpleNamespace(background=manager)
    return await ShowApp().run(ShowApp.Args(name="app"), context)  # type: ignore[arg-type]


def test_refuses_a_port_held_by_another_program(monkeypatch: pytest.MonkeyPatch) -> None:
    async def scenario() -> None:
        # Another program (this test) holds the port; the "app" is a quiet child that listens on nothing.
        stranger = socket.socket()
        stranger.bind(("127.0.0.1", 0))
        stranger.listen()
        port = stranger.getsockname()[1]
        child = await asyncio.create_subprocess_exec(
            sys.executable, "-c", "import time; time.sleep(30)", stdout=asyncio.subprocess.PIPE
        )
        try:
            entry = BackgroundProcess("app", "x", child, port, deque([f"Running on http://127.0.0.1:{port}"]))
            opened: list[str] = []
            result = await _run(entry, monkeypatch, opened)
            assert not result.ok and not opened  # type: ignore[attr-defined]
            assert "not listening" in result.content  # type: ignore[attr-defined]
        finally:
            child.kill()
            await child.wait()
            stranger.close()

    asyncio.run(scenario())


def test_opens_the_page_of_its_own_process(monkeypatch: pytest.MonkeyPatch) -> None:
    async def scenario() -> None:
        code = (
            "import http.server\n"
            "s=http.server.HTTPServer(('127.0.0.1',0),http.server.SimpleHTTPRequestHandler)\n"
            "print('Running on http://127.0.0.1:%d' % s.server_port, flush=True)\n"
            "s.serve_forever()\n"
        )
        child = await asyncio.create_subprocess_exec(
            sys.executable, "-c", code, stdout=asyncio.subprocess.PIPE
        )
        try:
            assert child.stdout is not None
            line = (await child.stdout.readline()).decode().strip()
            entry = BackgroundProcess("app", "x", child, None, deque([line]))
            opened: list[str] = []
            result = await _run(entry, monkeypatch, opened)
            assert result.ok, result.content  # type: ignore[attr-defined]
            assert opened and opened[0].startswith("http://127.0.0.1:")
        finally:
            child.kill()
            await child.wait()

    asyncio.run(scenario())
