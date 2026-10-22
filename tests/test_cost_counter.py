"""D-463: the project cost in the top bar moves with every model call and shows at once on a reopened project."""

from __future__ import annotations

import asyncio
from pathlib import Path

import pytest

from forge.engine.session_host import SessionHost
from forge.llm.base import Usage
from forge.protocol.events import EventBus, EventType
from forge.safety.redact import Redactor
from forge.session import build_session
from forge.workspace.create import create_workspace
from tests.helpers import default_config, fake_secrets, mocked_router, reply, responses_body, text_output


async def test_a_reopened_project_announces_its_cost_before_any_call(
    original_repo: Path, tmp_path: Path
) -> None:
    workspace = create_workspace(original_repo, tmp_path / "ws", "backend")
    router = mocked_router(lambda request: reply(request, responses_body([text_output("x")])))
    host = SessionHost(router, EventBus(redactor=Redactor()), workspace=workspace)
    assert router.cost.ledger is not None  # the host attaches the project's ledger
    router.cost.ledger.add("execute", None, Usage(input_tokens=1000, output_tokens=100), 0.25)
    runner = asyncio.create_task(host.run())
    await asyncio.sleep(0.2)
    runner.cancel()
    updates = [e.payload for e in host.bus.events_since(0) if e.type == EventType.COST_UPDATED]
    assert updates and updates[0]["project"]["total"]["cost_usd"] == 0.25


async def test_every_model_call_publishes_the_running_total(
    original_repo: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A long autonomous run is one turn that lasts hours; the counter must not wait for its end."""
    monkeypatch.setenv("FORGE_HOME", str(tmp_path / "home"))
    workspace = create_workspace(original_repo, tmp_path / "ws", "backend")
    host = build_session(workspace=workspace, config=default_config(), secrets=fake_secrets())
    summary = {"total_usd": 0.42, "budget_usd": 0.0, "calls": 3, "project": None}
    await host.router._notice(
        "usage", {"role": "coder", "summary": summary}
    )  # what the router does after a call
    updates = [e.payload for e in host.bus.events_since(0) if e.type == EventType.COST_UPDATED]
    assert updates == [summary]
