"""The browser smoke-check rung at export (D-138's deferred piece, built here): a Python-only workspace must
behave exactly as before (regression guard, mirroring test_react_ladder.py's dispatcher guards), and a
workspace with a detected React/Node frontend must run the check and add an informational, never-blocking
report section."""

from __future__ import annotations

from pathlib import Path

import pytest

from forge.agent import frontend_smoke as frontend_smoke_module
from forge.agent import orchestrator as orchestrator_module
from forge.agent.frontend_smoke import (
    SmokeCheckResult,
    render_smoke_check_section,
    run_frontend_smoke_check,
)
from forge.engine.events import EventBus
from forge.engine.session_host import SessionHost
from forge.safety.redact import Redactor
from forge.tools.base import ToolContext
from forge.workspace.create import create_workspace
from forge.workspace.nodeenv import NodeEnvironment
from tests.helpers import mocked_router


def _node_env(app_dir: Path, **overrides: object) -> NodeEnvironment:
    defaults: dict[str, object] = dict(
        node="C:\\node\\node.exe",
        package_manager="npm",
        app_dir=str(app_dir),
        install_command="npm install",
        build_command=None,
        test_command=None,
        lint_command=None,
        typecheck_command=None,
        dev_command=None,
    )
    defaults.update(overrides)
    return NodeEnvironment.model_validate(defaults)


def unreachable(request: object) -> object:
    raise AssertionError("no LLM call expected")


@pytest.fixture
def host(original_repo: Path, tmp_path: Path) -> SessionHost:
    workspace = create_workspace(original_repo, tmp_path / "ws", "backend")
    return SessionHost(
        mocked_router(unreachable),
        EventBus(redactor=Redactor()),
        workspace=workspace,  # type: ignore[arg-type]
        orchestrated=True,
    )


def orchestrator(host: SessionHost):  # mirrors test_orchestrator.py's own helper of the same name/shape
    assert host.orchestrator is not None
    return host.orchestrator


# --- regression guard: a Python-only workspace's _export() is untouched -----------------------------------


async def test_export_never_runs_the_smoke_check_without_a_node_env(
    host: SessionHost, monkeypatch: pytest.MonkeyPatch
) -> None:
    orch = orchestrator(host)
    assert orch.workspace.info.node_env is None

    def fail_if_called(*_args: object, **_kwargs: object) -> None:
        raise AssertionError("run_frontend_smoke_check must not be called for a Python-only workspace")

    monkeypatch.setattr(orchestrator_module, "run_frontend_smoke_check", fail_if_called)
    orch.state.started = True
    orch.state.requirement = "Do something"

    await orch._export()

    report = (orch.workspace.forge_dir / "reports" / "final.md").read_text(encoding="utf-8")
    assert "Frontend smoke check" not in report


# --- _export() wiring when node_env is present --------------------------------------------------------


async def test_export_adds_a_passing_smoke_check_section(
    host: SessionHost, monkeypatch: pytest.MonkeyPatch
) -> None:
    orch = orchestrator(host)
    orch.workspace.info.node_env = _node_env(orch.workspace.app_dir, dev_command="npm run dev")

    async def fake_check(context: ToolContext, node_env: NodeEnvironment) -> SmokeCheckResult:
        return SmokeCheckResult(ok=True, skipped=False, url="http://127.0.0.1:5055", detail="HTTP 200")

    monkeypatch.setattr(orchestrator_module, "run_frontend_smoke_check", fake_check)
    orch.state.started = True
    orch.state.requirement = "Build a frontend"

    await orch._export()

    report = (orch.workspace.forge_dir / "reports" / "final.md").read_text(encoding="utf-8")
    assert "## Frontend smoke check" in report
    assert "PASSED" in report
    assert "http://127.0.0.1:5055" in report


async def test_export_reports_a_failing_smoke_check_without_failing_export(
    host: SessionHost, monkeypatch: pytest.MonkeyPatch
) -> None:
    orch = orchestrator(host)
    orch.workspace.info.node_env = _node_env(orch.workspace.app_dir, dev_command="npm run dev")

    async def fake_check(context: ToolContext, node_env: NodeEnvironment) -> SmokeCheckResult:
        return SmokeCheckResult(
            ok=False, skipped=False, url="http://127.0.0.1:5055", detail="console errors:\n[pageerror] boom"
        )

    monkeypatch.setattr(orchestrator_module, "run_frontend_smoke_check", fake_check)
    orch.state.started = True
    orch.state.requirement = "Build a frontend"

    await orch._export()  # must not raise

    report = (orch.workspace.forge_dir / "reports" / "final.md").read_text(encoding="utf-8")
    assert "FAILED" in report and "pageerror" in report
    assert orch.state.exported is True  # export still completes


async def test_export_reports_skipped_without_crashing_when_there_is_no_dev_script(
    host: SessionHost, monkeypatch: pytest.MonkeyPatch
) -> None:
    orch = orchestrator(host)
    orch.workspace.info.node_env = _node_env(orch.workspace.app_dir, dev_command=None)
    orch.state.started = True
    orch.state.requirement = "Build a frontend"

    await orch._export()  # real run_frontend_smoke_check: no mocking needed, dev_command is None

    report = (orch.workspace.forge_dir / "reports" / "final.md").read_text(encoding="utf-8")
    assert "SKIPPED" in report
    assert orch.state.exported is True


# --- run_frontend_smoke_check itself: skip/fail/pass logic in isolation ------------------------------------


async def test_skips_when_the_repo_has_no_dev_command(host: SessionHost) -> None:
    orch = orchestrator(host)
    node_env = _node_env(orch.workspace.app_dir, dev_command=None)

    result = await run_frontend_smoke_check(orch.context, node_env)

    assert result.skipped and not result.ok
    assert "no dev/start/preview script" in result.detail


async def test_skips_when_the_dev_server_never_becomes_ready(
    host: SessionHost, monkeypatch: pytest.MonkeyPatch
) -> None:
    orch = orchestrator(host)
    node_env = _node_env(orch.workspace.app_dir, dev_command="npm run dev")

    class _FakeProcess:
        returncode = None
        pid = 12345

    async def fake_start(*_args: object, **_kwargs: object) -> object:
        return _FakeProcess()

    async def fake_wait(*_args: object, **_kwargs: object) -> bool:
        return False  # the port never opens

    stopped = {}

    def fake_kill_tree(pid: int) -> None:
        stopped["pid"] = pid

    monkeypatch.setattr(frontend_smoke_module, "start_process", fake_start)
    monkeypatch.setattr(frontend_smoke_module, "_wait_for_port", fake_wait)
    monkeypatch.setattr(frontend_smoke_module, "kill_tree", fake_kill_tree)

    result = await run_frontend_smoke_check(orch.context, node_env)

    assert result.skipped and not result.ok
    assert "never became ready" in result.detail
    assert stopped["pid"] == 12345  # the server is stopped even though the check never got to the browser


async def test_skips_when_no_browser_can_be_started(
    host: SessionHost, monkeypatch: pytest.MonkeyPatch
) -> None:
    orch = orchestrator(host)
    node_env = _node_env(orch.workspace.app_dir, dev_command="npm run dev")

    class _FakeProcess:
        returncode = None
        pid = 999

    async def fake_start(*_args: object, **_kwargs: object) -> object:
        return _FakeProcess()

    async def fake_wait(*_args: object, **_kwargs: object) -> bool:
        return True

    class _NoBrowserSession:
        def __init__(self) -> None:
            self.console: list[str] = []

        async def ensure(self) -> object:
            raise RuntimeError("No browser could be started (msedge: not found; chrome: not found)")

        async def close(self) -> None:
            pass

    monkeypatch.setattr(frontend_smoke_module, "start_process", fake_start)
    monkeypatch.setattr(frontend_smoke_module, "_wait_for_port", fake_wait)
    monkeypatch.setattr(frontend_smoke_module, "kill_tree", lambda pid: None)
    monkeypatch.setattr(frontend_smoke_module, "BrowserSession", _NoBrowserSession)

    result = await run_frontend_smoke_check(orch.context, node_env)

    assert result.skipped and not result.ok
    assert "no browser could be started" in result.detail


async def test_render_smoke_check_section_matches_the_restructure_check_style() -> None:
    passed = render_smoke_check_section(
        SmokeCheckResult(ok=True, skipped=False, url="http://127.0.0.1:5055", detail="HTTP 200")
    )
    assert "## Frontend smoke check" in passed and "PASSED" in passed and "5055" in passed

    failed = render_smoke_check_section(
        SmokeCheckResult(ok=False, skipped=False, url="http://127.0.0.1:5055", detail="console errors:\nboom")
    )
    assert "FAILED" in failed and "boom" in failed

    skipped = render_smoke_check_section(
        SmokeCheckResult(ok=False, skipped=True, url=None, detail="no browser could be started")
    )
    assert "SKIPPED" in skipped
