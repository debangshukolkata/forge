"""X2 (D-305): parallel builders: protocol helpers, the write jail, ports, batching and a real run with a mocked model."""

from __future__ import annotations

import json
import threading
import time
from pathlib import Path

import httpx2
import pytest

from forge.engine.session_host import SessionHost
from forge.llm.base import ToolCall
from forge.protocol.events import EventBus
from forge.safety.redact import Redactor
from forge.subagents.builder import (
    append_ledger,
    clean_folder,
    folders_disjoint,
    parse_status,
    result_text,
    safe_name,
)
from forge.subagents.spawn_tool import SpawnSubagent
from forge.toolkit.background import free_port
from forge.toolkit.base import ToolResult
from forge.workspace.create import create_workspace
from tests.helpers import function_call_output, mocked_router, reply, responses_body, text_output


def test_the_status_is_read_from_the_last_status_line_and_missing_means_blocked() -> None:
    assert parse_status("Built it.\nSTATUS: DONE - checked") == "DONE"
    assert parse_status("status: done_with_concerns - slow") == "DONE_WITH_CONCERNS"
    assert parse_status("STATUS: NEEDS_CONTEXT - which API key?") == "NEEDS_CONTEXT"
    assert parse_status("STATUS: BLOCKED\nlater\nSTATUS: DONE") == "DONE"  # the last line counts
    assert parse_status("I think it works.") == "BLOCKED"  # nothing is counted as done by luck


@pytest.mark.parametrize(
    "raw,clean",
    [
        ("designs/a", "designs/a"),
        ("./designs/a/", "designs/a"),
        ("designs\\a", "designs/a"),
        ("", ""),
        ("../x", ""),
        ("a/../b", ""),
        ("C:\\x", ""),
    ],
)
def test_folders_are_cleaned_and_unsafe_ones_refused(raw: str, clean: str) -> None:
    assert clean_folder(raw) == clean


def test_folders_must_not_overlap() -> None:
    assert folders_disjoint("designs/a", "designs/b")
    assert not folders_disjoint("designs/a", "designs/a")
    assert not folders_disjoint("designs", "designs/a")  # one inside the other
    assert not folders_disjoint("designs/a/x", "designs/a")
    assert folders_disjoint("designs/a", "designs/ab")  # a shared prefix is not a shared folder
    assert not folders_disjoint("", "designs/a")


def test_names_ledger_and_result_text(tmp_path: Path) -> None:
    assert safe_name("Design A!", "designs/a") == "design-a"
    assert safe_name("", "designs/a") == "designs-a"
    append_ledger(tmp_path, "design-a", "designs/a", "DONE", "Built the page\nwith a form")
    append_ledger(tmp_path, "design-b", "designs/b", "BLOCKED", "no logo file")
    lines = (tmp_path / "builders" / "ledger.md").read_text(encoding="utf-8").splitlines()
    assert len(lines) == 2 and "design-a [designs/a] DONE: Built the page with a form" in lines[0]
    text = result_text("design-a", "designs/a", "BLOCKED", "report", ".forge/builders/design-a-report.md")
    assert "Do not retry unchanged" in text and "design-a-report.md" in text


def test_ports_handed_out_at_the_same_moment_are_distinct() -> None:
    ports: list[int] = []
    lock = threading.Lock()

    def take() -> None:
        port = free_port(5600)
        with lock:
            ports.append(port)

    threads = [threading.Thread(target=take) for _ in range(12)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert len(set(ports)) == 12


def make_call(folder: str, agent: str = "builder") -> ToolCall:
    arguments = {"agent": agent, "task": "x", "folder": folder}
    return ToolCall(
        id=folder or "none", name="spawn_subagent", raw_arguments=json.dumps(arguments), arguments=arguments
    )


@pytest.fixture
def host(original_repo: Path, tmp_path: Path) -> SessionHost:
    workspace = create_workspace(original_repo, tmp_path / "ws", "backend")

    def handler(request: httpx2.Request) -> httpx2.Response:
        return reply(request, responses_body([text_output("ok")]))

    return SessionHost(mocked_router(handler), EventBus(redactor=Redactor()), workspace=workspace)


def test_builders_with_their_own_folders_share_a_batch_up_to_the_limit(host: SessionHost) -> None:
    loop = host.agent
    assert loop is not None
    batch: list[ToolCall] = []
    for folder in ("designs/a", "designs/b", "designs/c"):
        assert loop._builder_fits_batch(make_call(folder), batch)
        batch.append(make_call(folder))
    assert not loop._builder_fits_batch(make_call("designs/d"), batch)  # the cap is 3
    assert not loop._builder_fits_batch(
        make_call("designs/a/x"), batch[:2]
    )  # inside another builder's folder
    assert not loop._builder_fits_batch(make_call("designs/a"), batch[:1])  # the same folder
    assert not loop._builder_fits_batch(
        make_call(""), []
    )  # a builder without a folder never runs in parallel
    assert not loop._builder_fits_batch(make_call("designs/x", agent="explore"), [])


def test_the_limit_can_switch_parallel_builders_off(host: SessionHost) -> None:
    loop = host.agent
    assert loop is not None
    loop.router.config.limits.max_parallel_builders = 1
    assert not loop._builder_fits_batch(make_call("designs/a"), [])


async def test_a_builder_builds_in_its_folder_is_stopped_outside_it_and_reports_a_status(
    original_repo: Path, tmp_path: Path
) -> None:
    steps = {"n": 0}
    seen: list[str] = []

    def handler(request: httpx2.Request) -> httpx2.Response:
        steps["n"] += 1
        seen.append(request.content.decode("utf-8", errors="replace"))
        if steps["n"] == 1:
            args = json.dumps({"path": "designs/a/index.html", "content": "<h1>A</h1>"})
            return reply(request, responses_body([function_call_output("write_file", args)]))
        if steps["n"] == 2:
            args = json.dumps({"path": "backend/escape.txt", "content": "no"})
            return reply(
                request, responses_body([function_call_output("write_file", args, call_id="call_2")])
            )
        return reply(request, responses_body([text_output("Built the page.\nSTATUS: DONE - checked")]))

    workspace = create_workspace(original_repo, tmp_path / "ws", "backend")
    host = SessionHost(mocked_router(handler), EventBus(redactor=Redactor()), workspace=workspace)
    assert host.agent is not None
    result = await SpawnSubagent().run(
        SpawnSubagent.Args(agent="builder", name="design-a", folder="designs/a", task="Build page A."),
        host.agent.context,
    )

    assert result.ok and "[builder design-a in designs/a: DONE]" in result.content
    assert (workspace.repo_dir / "designs" / "a" / "index.html").read_text(encoding="utf-8") == "<h1>A</h1>"
    assert not (workspace.repo_dir / "backend" / "escape.txt").exists()  # the write jail held
    assert "may only write below designs/a/" in seen[-1]  # and the builder was told why
    assert (workspace.root / ".forge" / "builders" / "design-a-report.md").exists()
    ledger = (workspace.forge_dir / "builders" / "ledger.md").read_text(encoding="utf-8")
    assert "design-a [designs/a] DONE" in ledger


async def test_a_builder_without_a_folder_is_refused_with_the_reason(host: SessionHost) -> None:
    assert host.agent is not None
    result = await SpawnSubagent().run(SpawnSubagent.Args(agent="builder", task="Build."), host.agent.context)
    assert not result.ok and "needs `folder`" in result.content


async def test_two_builders_run_at_the_same_time_but_not_in_the_same_folder(
    host: SessionHost, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Builder calls with their own folders overlap; two for one folder queue up (the model call itself is mocked away)."""
    import asyncio

    async def slow_run(self: SpawnSubagent, args: SpawnSubagent.Args, context: object) -> ToolResult:
        await asyncio.sleep(0.5)
        return ToolResult(ok=True, content=f"done {args.folder}")

    monkeypatch.setattr(SpawnSubagent, "run", slow_run)
    loop = host.agent
    assert loop is not None

    async def timed(calls: list[ToolCall]) -> float:
        started = time.perf_counter()
        await loop._run_calls(calls, {})
        return time.perf_counter() - started

    assert await timed([make_call("designs/a"), make_call("designs/b"), make_call("designs/c")]) < 0.9
    assert await timed([make_call("designs/a"), make_call("designs/a")]) >= 0.95
