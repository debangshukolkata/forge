"""D-138: the React/TS verify ladder's rung skipping, its dispatcher wiring in VerifyLadder, and the
regression guard that a Python-only workspace's behaviour never changes."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from forge.toolkit.base import ToolContext, ToolResult
from forge.toolkit.shell import ShellSession
from forge.verify import react_ladder as react_ladder_module
from forge.verify.ladder import VerifyLadder
from forge.verify.react_ladder import ReactVerifyLadder
from forge.workspace.create import create_workspace
from forge.workspace.nodeenv import NodeEnvironment
from forge.workspace.workspace import Workspace
from tests.conftest import FIXTURE_REPO


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
    )
    defaults.update(overrides)
    return NodeEnvironment.model_validate(defaults)


@pytest.fixture
def react_workspace(original_repo: Path, tmp_path: Path) -> Workspace:
    """The fixture repo's backend app folder, reused as a stand-in "app dir" for a React app: phase 1 only
    detects a Node app in the SAME app_subfolder the user already gave, so this is enough to exercise it."""
    return create_workspace(original_repo, tmp_path / "ws", "backend", max_file_mb=1)


@pytest.fixture
def context(react_workspace: Workspace) -> ToolContext:
    return ToolContext(workspace=react_workspace, shell=ShellSession(react_workspace, sandbox="off"))


async def _fake_execute_failing(*_args: object, **_kwargs: object) -> ToolResult:
    return ToolResult(ok=False, content="boom")


async def test_typecheck_skips_without_a_tsconfig(context: ToolContext) -> None:
    ladder = ReactVerifyLadder(context, _node_env(context.workspace.app_dir))
    step = await ladder._typecheck()
    assert step.skipped and step.ok


async def test_lint_skips_without_an_eslint_config(context: ToolContext) -> None:
    ladder = ReactVerifyLadder(context, _node_env(context.workspace.app_dir))
    step = await ladder._lint()
    assert step.skipped and step.ok


async def test_unit_tests_skip_without_jest_or_vitest(context: ToolContext) -> None:
    (context.workspace.app_dir / "package.json").write_text(
        json.dumps({"name": "app", "devDependencies": {}}), encoding="utf-8"
    )
    ladder = ReactVerifyLadder(context, _node_env(context.workspace.app_dir))
    step = await ladder._unit_tests()
    assert step.skipped and step.ok


async def test_build_skips_without_a_build_script(context: ToolContext) -> None:
    ladder = ReactVerifyLadder(context, _node_env(context.workspace.app_dir, build_command=None))
    step = await ladder._build()
    assert step.skipped and step.ok


async def test_lint_runs_when_an_eslintrc_is_present(
    context: ToolContext, monkeypatch: pytest.MonkeyPatch
) -> None:
    (context.workspace.app_dir / ".eslintrc.json").write_text("{}", encoding="utf-8")
    monkeypatch.setattr(react_ladder_module, "execute", _fake_execute_failing)
    ladder = ReactVerifyLadder(context, _node_env(context.workspace.app_dir))
    step = await ladder._lint()
    assert not step.ok and not step.skipped


async def test_unit_tests_detect_vitest_from_dependencies_and_parse_the_summary(
    context: ToolContext, monkeypatch: pytest.MonkeyPatch
) -> None:
    (context.workspace.app_dir / "package.json").write_text(
        json.dumps({"name": "app", "devDependencies": {"vitest": "^1.0.0"}}), encoding="utf-8"
    )

    async def fake_execute(*_args: object, **_kwargs: object) -> ToolResult:
        return ToolResult(ok=True, content="Test Files  1 passed (1)\n")

    monkeypatch.setattr(react_ladder_module, "execute", fake_execute)
    ladder = ReactVerifyLadder(context, _node_env(context.workspace.app_dir))
    step = await ladder._unit_tests()
    assert step.ok and "vitest" in step.summary and "1 total" in step.summary


async def test_build_runs_the_repos_own_script_name(
    context: ToolContext, monkeypatch: pytest.MonkeyPatch
) -> None:
    seen_commands = []

    async def fake_execute(
        _context: ToolContext, command: str, *_args: object, **_kwargs: object
    ) -> ToolResult:
        seen_commands.append(command)
        return ToolResult(ok=True, content="done")

    monkeypatch.setattr(react_ladder_module, "execute", fake_execute)
    ladder = ReactVerifyLadder(context, _node_env(context.workspace.app_dir, build_command="pnpm run build"))
    step = await ladder._build()
    assert step.ok and seen_commands == ["pnpm run build"]


# --- dispatcher regression guard -----------------------------------------------------------------


async def test_python_only_workspace_never_invokes_the_react_ladder(
    context: ToolContext, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The critical regression guard (per the task brief): a workspace with no node_env must behave
    exactly as before the dispatcher existed — the React ladder must not even be instantiated."""
    assert context.workspace.info.node_env is None

    def fail_if_called(*_args: object, **_kwargs: object) -> None:
        raise AssertionError("ReactVerifyLadder must not be instantiated for a Python-only workspace")

    monkeypatch.setattr(react_ladder_module, "ReactVerifyLadder", fail_if_called)
    report = await VerifyLadder(context).run()
    assert [s.name for s in report.steps]  # the ordinary Python rungs still ran
    assert not any("react" in s.name.lower() or "typecheck" in s.name.lower() for s in report.steps)


async def test_node_env_present_but_no_frontend_files_changed_skips_the_react_ladder(
    context: ToolContext, monkeypatch: pytest.MonkeyPatch
) -> None:
    """node_env alone isn't enough to run the React ladder — mirrors how the Python ladder already skips
    rungs when there's nothing to check; only actually-changed frontend files trigger it."""
    context.workspace.info.node_env = _node_env(context.workspace.app_dir)

    def fail_if_called(*_args: object, **_kwargs: object) -> None:
        raise AssertionError("ReactVerifyLadder must not run when no frontend files changed")

    monkeypatch.setattr(react_ladder_module, "ReactVerifyLadder", fail_if_called)
    report = await VerifyLadder(context).run()
    assert report.steps  # Python rungs still ran normally


async def test_frontend_change_runs_the_react_ladder_and_combines_reports(
    context: ToolContext, monkeypatch: pytest.MonkeyPatch
) -> None:
    context.workspace.info.node_env = _node_env(context.workspace.app_dir)
    context.workspace.write_text("backend/App.tsx", "export const App = () => null;\n")

    from forge.verify.ladder import LadderReport, StepResult

    async def fake_react_run(self: ReactVerifyLadder) -> LadderReport:
        return LadderReport(steps=[StepResult("typecheck (tsc)", True, "clean", skipped=False)])

    monkeypatch.setattr(ReactVerifyLadder, "run", fake_react_run)
    report = await VerifyLadder(context).run()
    assert any(s.name == "typecheck (tsc)" for s in report.steps)


def test_fixture_is_present() -> None:
    assert (FIXTURE_REPO / "backend").exists()
