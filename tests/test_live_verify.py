"""M8 live acceptance (spec M8): the live agent fixes an injected failing test without weakening tests, and
the agent runs the tests itself. Run with: pytest -m live"""

from __future__ import annotations

from pathlib import Path

import pytest

from forge.config import load_config, load_secrets
from forge.engine.session_host import SessionHost
from forge.llm.router import LLMRouter
from forge.protocol.events import EventBus, EventType
from forge.toolkit.base import ToolContext
from forge.toolkit.shell import ShellSession
from forge.verify.ladder import VerifyLadder
from forge.verify.test_guard import check_tests
from forge.workspace.create import create_workspace
from tests.conftest import FIXTURE_BACKEND, FIXTURE_REPO, REPO_ROOT
from tests.test_live_agent import events_of, run_turn

pytestmark = pytest.mark.live
FIXTURE_PYTHON = FIXTURE_BACKEND / "venv" / "Scripts" / "python.exe"
SERVICE = "backend/claims_app/services/claims_service.py"


@pytest.fixture
def host(tmp_path: Path, isolated_forge_home: Path, monkeypatch: pytest.MonkeyPatch) -> SessionHost:
    if not FIXTURE_PYTHON.exists():
        pytest.skip("run scripts/dev/setup_fixture_venv.ps1 first")
    monkeypatch.setenv("FORGE_ENV_FILE", str(REPO_ROOT / ".env"))
    secrets = load_secrets(isolated_forge_home)
    if not secrets.get("AZURE_OPENAI_API_KEY"):
        pytest.skip("AZURE_OPENAI_* not configured in .env")
    workspace = create_workspace(FIXTURE_REPO, tmp_path / "ws", "backend")
    return SessionHost(
        LLMRouter(load_config(isolated_forge_home), secrets),
        EventBus(workspace.forge_dir / "events.jsonl"),
        workspace=workspace,
        permission_mode="auto",
    )


async def test_injected_failure_is_fixed_without_weakening_tests(host: SessionHost) -> None:
    assert host.workspace is not None
    service = host.workspace.path_of(SERVICE)
    source = service.read_text(encoding="utf-8")
    assert "offset = (page - 1) * page_size" in source
    service.write_text(
        source.replace("offset = (page - 1) * page_size", "offset = page * page_size"), "utf-8"
    )
    context = ToolContext(workspace=host.workspace, shell=ShellSession(host.workspace, sandbox="off"))
    before, _ = await VerifyLadder(context).run_tests("")
    assert not before.ok, "the injected bug should break a test"

    await run_turn(host, "The test suite fails. Find the cause and fix the code; don't change the tests.")

    after, _ = await VerifyLadder(context).run_tests("")
    assert after.ok, after.summary
    assert "offset = (page - 1) * page_size" in service.read_text(encoding="utf-8")
    assert check_tests(host.workspace) == []
    started = events_of(host, EventType.TOOL_CALL_STARTED)
    ran_tests = [
        e for e in started if e.payload["name"] in ("verify", "run_tests") or "pytest" in e.payload["summary"]
    ]
    assert ran_tests, "the agent must run the tests itself (evidence), whichever tool it uses"
