"""D-141/D-142: setup_frontend, the Mode B tool that scaffolds a frontend from scratch (no host to conform
to) via the real npm scaffolder, then wires the result into WorkspaceInfo.node_env for the existing (phase
1) verify ladder to pick up. The actual `npm create` subprocess call is mocked throughout: no real
npm/network."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from forge.modeb.profile import ProfileStore
from forge.modeb.workspace import create_standalone_workspace
from forge.tools import frontend_setup as frontend_setup_module
from forge.tools.base import ToolContext, ToolResult
from forge.tools.frontend_setup import SetupFrontend
from forge.tools.shell import ShellSession
from forge.workspace.create import create_workspace
from forge.workspace.workspace import Workspace
from tests.conftest import FIXTURE_REPO


@pytest.fixture
def modeb_workspace(tmp_path: Path, isolated_forge_home: Path) -> Workspace:
    profile = ProfileStore(isolated_forge_home).create("host", sensitive_terms=["Contoso"])
    workspace = create_standalone_workspace(tmp_path / "wsb", profile)
    return Workspace.open(workspace.root)


@pytest.fixture
def modeb_context(modeb_workspace: Workspace) -> ToolContext:
    return ToolContext(workspace=modeb_workspace, shell=ShellSession(modeb_workspace, sandbox="off"))


@pytest.fixture
def modea_context(tmp_path: Path) -> ToolContext:
    workspace = create_workspace(FIXTURE_REPO, tmp_path / "wsa", "backend", max_file_mb=1)
    return ToolContext(workspace=workspace, shell=ShellSession(workspace, sandbox="off"))


def _write_vite_scaffold(app_dir: Path) -> None:
    """What `npm create vite@latest` actually leaves behind: enough for detect_node_environment to see it."""
    app_dir.mkdir(parents=True, exist_ok=True)
    (app_dir / "package.json").write_text(
        json.dumps(
            {
                "name": "frontend",
                "scripts": {"dev": "vite", "build": "vite build", "preview": "vite preview"},
                "devDependencies": {"vite": "^5.0.0"},
            }
        ),
        encoding="utf-8",
    )


async def test_unusable_outside_mode_b(modea_context: ToolContext) -> None:
    result = await SetupFrontend().run(SetupFrontend.Args(), modea_context)

    assert not result.ok
    assert "Mode B" in result.content
    assert modea_context.workspace.info.node_env is None


async def test_successful_scaffold_populates_node_env(
    modeb_context: ToolContext, monkeypatch: pytest.MonkeyPatch
) -> None:
    workspace = modeb_context.workspace
    seen_commands: list[str] = []

    async def fake_execute(context: ToolContext, command: str, timeout_s: int, cwd: str | None) -> ToolResult:
        seen_commands.append(command)
        assert cwd == "frontend"
        _write_vite_scaffold(workspace.repo_dir / "frontend")
        return ToolResult(ok=True, content="scaffolded")

    monkeypatch.setattr(frontend_setup_module, "execute", fake_execute)

    result = await SetupFrontend().run(SetupFrontend.Args(framework="react", typescript=True), modeb_context)

    assert result.ok, result.content
    assert "react" in seen_commands[0] and "--template react-ts" in seen_commands[0]
    assert workspace.info.node_env is not None
    assert workspace.info.node_env.build_command == "npm run build"
    # Persisted: a freshly re-opened workspace sees the same node_env, not just the in-memory object.
    reopened = Workspace.open(workspace.root)
    assert reopened.info.node_env is not None
    assert reopened.info.node_env.app_dir == workspace.info.node_env.app_dir


async def test_custom_create_command_is_used_verbatim(
    modeb_context: ToolContext, monkeypatch: pytest.MonkeyPatch
) -> None:
    workspace = modeb_context.workspace
    seen_commands: list[str] = []

    async def fake_execute(context: ToolContext, command: str, timeout_s: int, cwd: str | None) -> ToolResult:
        seen_commands.append(command)
        _write_vite_scaffold(workspace.repo_dir / "frontend")
        return ToolResult(ok=True, content="scaffolded")

    monkeypatch.setattr(frontend_setup_module, "execute", fake_execute)
    args = SetupFrontend.Args(framework="other", create_command="npm create vue@latest . -- --typescript")

    result = await SetupFrontend().run(args, modeb_context)

    assert result.ok, result.content
    assert seen_commands == ["npm create vue@latest . -- --typescript"]


def test_other_framework_requires_create_command() -> None:
    with pytest.raises(ValueError, match="create_command"):
        SetupFrontend.Args(framework="other")


async def test_already_exists_is_rejected_not_clobbered(
    modeb_context: ToolContext, monkeypatch: pytest.MonkeyPatch
) -> None:
    workspace = modeb_context.workspace
    calls = 0

    async def fake_execute(context: ToolContext, command: str, timeout_s: int, cwd: str | None) -> ToolResult:
        nonlocal calls
        calls += 1
        _write_vite_scaffold(workspace.repo_dir / "frontend")
        return ToolResult(ok=True, content="scaffolded")

    monkeypatch.setattr(frontend_setup_module, "execute", fake_execute)
    first = await SetupFrontend().run(SetupFrontend.Args(), modeb_context)
    assert first.ok

    second = await SetupFrontend().run(SetupFrontend.Args(), modeb_context)

    assert not second.ok
    assert "already set up" in second.content
    assert calls == 1  # the second call never touched the shell


async def test_scaffold_failure_leaves_workspace_state_clean(
    modeb_context: ToolContext, monkeypatch: pytest.MonkeyPatch
) -> None:
    workspace = modeb_context.workspace

    async def failing_execute(
        context: ToolContext, command: str, timeout_s: int, cwd: str | None
    ) -> ToolResult:
        return ToolResult(ok=False, content="npm error: network unreachable", meta={"exit_code": 1})

    monkeypatch.setattr(frontend_setup_module, "execute", failing_execute)

    result = await SetupFrontend().run(SetupFrontend.Args(), modeb_context)

    assert not result.ok
    assert "network unreachable" in result.content
    assert workspace.info.node_env is None
    # A retry after fixing the underlying problem must still be possible: the empty folder isn't left
    # looking "already set up" (no node_env was ever written, no partial package.json requires cleanup).
    reopened = Workspace.open(workspace.root)
    assert reopened.info.node_env is None


async def test_scaffold_exits_ok_but_leaves_no_package_json(
    modeb_context: ToolContext, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A command that reports success but doesn't actually scaffold anything must not silently claim ok."""

    async def noop_execute(context: ToolContext, command: str, timeout_s: int, cwd: str | None) -> ToolResult:
        return ToolResult(ok=True, content="did nothing")

    monkeypatch.setattr(frontend_setup_module, "execute", noop_execute)

    result = await SetupFrontend().run(SetupFrontend.Args(), modeb_context)

    assert not result.ok
    assert modeb_context.workspace.info.node_env is None
