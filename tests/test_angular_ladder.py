"""D-143/D-144: Angular detection, the Angular-aware typecheck/test rungs, the critical `ng test` CI-mode
safety guard (must never run the bare test command against a Karma project), custom Karma launcher pickup,
and the dispatcher's Angular-vs-React routing — including the regression guard that a plain React project's
behaviour is completely unchanged."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from forge.tools.base import ToolContext, ToolResult
from forge.tools.shell import ShellSession
from forge.verify import angular_ladder as angular_ladder_module
from forge.verify import react_ladder as react_ladder_module
from forge.verify.angular_ladder import AngularVerifyLadder, is_angular_project
from forge.verify.ladder import LadderReport, StepResult, VerifyLadder
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
def angular_workspace(original_repo: Path, tmp_path: Path) -> Workspace:
    """The fixture repo's backend app folder reused as a stand-in Angular app dir, same trick
    `tests/test_react_ladder.py` already uses for React."""
    return create_workspace(original_repo, tmp_path / "ws", "backend", max_file_mb=1)


@pytest.fixture
def context(angular_workspace: Workspace) -> ToolContext:
    return ToolContext(workspace=angular_workspace, shell=ShellSession(angular_workspace, sandbox="off"))


def _write_angular_json(app_dir: Path, configurations: dict[str, object] | None = None) -> None:
    architect: dict[str, object] = {"build": {"builder": "@angular-devkit/build-angular:application"}}
    if configurations is not None:
        architect["build"] = {**architect["build"], "configurations": configurations}  # type: ignore[dict-item]
    data = {"projects": {"my-app": {"architect": architect}}}
    (app_dir / "angular.json").write_text(json.dumps(data), encoding="utf-8")


async def _fake_execute_failing(*_args: object, **_kwargs: object) -> ToolResult:
    return ToolResult(ok=False, content="boom")


# --- detection -------------------------------------------------------------------------------------


def test_is_angular_project_true_with_angular_json(context: ToolContext) -> None:
    _write_angular_json(context.workspace.app_dir)
    assert is_angular_project(context.workspace.app_dir)


def test_is_angular_project_false_without_angular_json(context: ToolContext) -> None:
    assert not is_angular_project(context.workspace.app_dir)


# --- typecheck rung ----------------------------------------------------------------------------------


async def test_typecheck_skips_without_a_tsconfig(context: ToolContext) -> None:
    ladder = AngularVerifyLadder(context, _node_env(context.workspace.app_dir))
    step = await ladder._typecheck()
    assert step.skipped and step.ok


async def test_typecheck_uses_ng_build_not_bare_tsc(
    context: ToolContext, monkeypatch: pytest.MonkeyPatch
) -> None:
    (context.workspace.app_dir / "tsconfig.json").write_text("{}", encoding="utf-8")
    _write_angular_json(context.workspace.app_dir)
    seen_commands = []

    async def fake_execute(_context: ToolContext, command: str, *_a: object, **_kw: object) -> ToolResult:
        seen_commands.append(command)
        return ToolResult(ok=True, content="done")

    monkeypatch.setattr(angular_ladder_module, "execute", fake_execute)
    ladder = AngularVerifyLadder(context, _node_env(context.workspace.app_dir, build_command="npm run build"))
    step = await ladder._typecheck()
    assert step.ok
    assert seen_commands == ["npm run build"]
    assert "tsc" not in seen_commands[0]


async def test_typecheck_prefers_development_configuration_when_declared(
    context: ToolContext, monkeypatch: pytest.MonkeyPatch
) -> None:
    (context.workspace.app_dir / "tsconfig.json").write_text("{}", encoding="utf-8")
    _write_angular_json(context.workspace.app_dir, configurations={"production": {}, "development": {}})
    seen_commands = []

    async def fake_execute(_context: ToolContext, command: str, *_a: object, **_kw: object) -> ToolResult:
        seen_commands.append(command)
        return ToolResult(ok=True, content="done")

    monkeypatch.setattr(angular_ladder_module, "execute", fake_execute)
    ladder = AngularVerifyLadder(context, _node_env(context.workspace.app_dir, build_command="npm run build"))
    await ladder._typecheck()
    assert seen_commands == ["npm run build --configuration=development"]


async def test_typecheck_falls_back_to_npx_ng_build_without_a_build_script(
    context: ToolContext, monkeypatch: pytest.MonkeyPatch
) -> None:
    (context.workspace.app_dir / "tsconfig.json").write_text("{}", encoding="utf-8")
    _write_angular_json(context.workspace.app_dir)
    seen_commands = []

    async def fake_execute(_context: ToolContext, command: str, *_a: object, **_kw: object) -> ToolResult:
        seen_commands.append(command)
        return ToolResult(ok=True, content="done")

    monkeypatch.setattr(angular_ladder_module, "execute", fake_execute)
    ladder = AngularVerifyLadder(context, _node_env(context.workspace.app_dir, build_command=None))
    await ladder._typecheck()
    assert seen_commands == ["npx ng build"]


# --- test framework detection --------------------------------------------------------------------------


async def test_unit_tests_skip_without_any_known_framework(context: ToolContext) -> None:
    (context.workspace.app_dir / "package.json").write_text(
        json.dumps({"name": "app", "devDependencies": {}}), encoding="utf-8"
    )
    ladder = AngularVerifyLadder(context, _node_env(context.workspace.app_dir))
    step = await ladder._unit_tests()
    assert step.skipped and step.ok


async def test_karma_detected_from_dependencies(context: ToolContext) -> None:
    (context.workspace.app_dir / "package.json").write_text(
        json.dumps({"name": "app", "devDependencies": {"karma": "^6.0.0", "jasmine-core": "^5.0.0"}}),
        encoding="utf-8",
    )
    ladder = AngularVerifyLadder(context, _node_env(context.workspace.app_dir))
    assert ladder._test_framework() == "karma"


async def test_karma_detected_from_conf_file_alone(context: ToolContext) -> None:
    (context.workspace.app_dir / "package.json").write_text(
        json.dumps({"name": "app", "devDependencies": {}}), encoding="utf-8"
    )
    (context.workspace.app_dir / "karma.conf.js").write_text("module.exports = () => {};", encoding="utf-8")
    ladder = AngularVerifyLadder(context, _node_env(context.workspace.app_dir))
    assert ladder._test_framework() == "karma"


async def test_jest_detected_for_angular(context: ToolContext) -> None:
    (context.workspace.app_dir / "package.json").write_text(
        json.dumps({"name": "app", "devDependencies": {"jest": "^29.0.0"}}), encoding="utf-8"
    )
    ladder = AngularVerifyLadder(context, _node_env(context.workspace.app_dir))
    assert ladder._test_framework() == "jest"


# --- THE critical safety test: ng test CI-mode flags ---------------------------------------------------


async def test_karma_test_rung_appends_ci_flags_and_never_runs_the_bare_command(
    context: ToolContext, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The regression test that matters most (per the task brief): a Karma-detected project's test rung
    must never invoke the bare test_command unmodified — that hangs forever in watch mode against a real
    browser. Assert the EXACT command string, not just "it didn't crash"."""
    (context.workspace.app_dir / "package.json").write_text(
        json.dumps({"name": "app", "devDependencies": {"karma": "^6.0.0", "jasmine-core": "^5.0.0"}}),
        encoding="utf-8",
    )
    seen_commands = []

    async def fake_execute(_context: ToolContext, command: str, *_a: object, **_kw: object) -> ToolResult:
        seen_commands.append(command)
        return ToolResult(ok=True, content="Executed 3 of 3 SUCCESS")

    monkeypatch.setattr(angular_ladder_module, "execute", fake_execute)
    ladder = AngularVerifyLadder(context, _node_env(context.workspace.app_dir, test_command="npm run test"))
    step = await ladder._unit_tests()
    assert step.ok
    assert seen_commands == ["npm run test --watch=false --browsers=ChromeHeadless"]
    # The dangerous case this guards against: the bare command alone, with no CI flags.
    assert seen_commands[0] != "npm run test"


async def test_karma_test_rung_uses_npx_ng_test_fallback_without_a_test_script(
    context: ToolContext, monkeypatch: pytest.MonkeyPatch
) -> None:
    (context.workspace.app_dir / "package.json").write_text(
        json.dumps({"name": "app", "devDependencies": {"karma": "^6.0.0"}}), encoding="utf-8"
    )
    seen_commands = []

    async def fake_execute(_context: ToolContext, command: str, *_a: object, **_kw: object) -> ToolResult:
        seen_commands.append(command)
        return ToolResult(ok=True, content="Executed 1 of 1 SUCCESS")

    monkeypatch.setattr(angular_ladder_module, "execute", fake_execute)
    ladder = AngularVerifyLadder(context, _node_env(context.workspace.app_dir, test_command=None))
    await ladder._unit_tests()
    assert seen_commands == ["npx ng test --watch=false --browsers=ChromeHeadless"]


async def test_karma_test_rung_prefers_a_custom_launcher_from_karma_conf(
    context: ToolContext, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A repo's own karma.conf.js customLaunchers entry (commonly ChromeHeadlessCI, often adding
    --no-sandbox for containers) must win over Forge's generic ChromeHeadless guess."""
    (context.workspace.app_dir / "package.json").write_text(
        json.dumps({"name": "app", "devDependencies": {"karma": "^6.0.0"}}), encoding="utf-8"
    )
    (context.workspace.app_dir / "karma.conf.js").write_text(
        """
        module.exports = function (config) {
          config.set({
            customLaunchers: {
              ChromeHeadlessCI: {
                base: 'ChromeHeadless',
                flags: ['--no-sandbox', '--disable-gpu']
              }
            }
          });
        };
        """,
        encoding="utf-8",
    )
    seen_commands = []

    async def fake_execute(_context: ToolContext, command: str, *_a: object, **_kw: object) -> ToolResult:
        seen_commands.append(command)
        return ToolResult(ok=True, content="Executed 2 of 2 SUCCESS")

    monkeypatch.setattr(angular_ladder_module, "execute", fake_execute)
    ladder = AngularVerifyLadder(context, _node_env(context.workspace.app_dir, test_command="npm run test"))
    await ladder._unit_tests()
    assert seen_commands == ["npm run test --watch=false --browsers=ChromeHeadlessCI"]


async def test_jest_test_rung_does_not_append_karma_ci_flags(
    context: ToolContext, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Jest's own default run is already one-shot: the Karma CI-flag rewrite must not apply to it."""
    (context.workspace.app_dir / "package.json").write_text(
        json.dumps({"name": "app", "devDependencies": {"jest": "^29.0.0"}}), encoding="utf-8"
    )
    seen_commands = []

    async def fake_execute(_context: ToolContext, command: str, *_a: object, **_kw: object) -> ToolResult:
        seen_commands.append(command)
        return ToolResult(ok=True, content="Tests:       3 passed, 3 total")

    monkeypatch.setattr(angular_ladder_module, "execute", fake_execute)
    ladder = AngularVerifyLadder(context, _node_env(context.workspace.app_dir, test_command="npm run test"))
    await ladder._unit_tests()
    assert seen_commands == ["npm run test"]


# --- lint / build (confirmed unchanged, ordinary npm scripts) ----------------------------------------


async def test_lint_runs_the_repos_own_script(context: ToolContext, monkeypatch: pytest.MonkeyPatch) -> None:
    (context.workspace.app_dir / ".eslintrc.json").write_text("{}", encoding="utf-8")
    seen_commands = []

    async def fake_execute(_context: ToolContext, command: str, *_a: object, **_kw: object) -> ToolResult:
        seen_commands.append(command)
        return ToolResult(ok=True, content="done")

    monkeypatch.setattr(angular_ladder_module, "execute", fake_execute)
    ladder = AngularVerifyLadder(context, _node_env(context.workspace.app_dir, lint_command="npm run lint"))
    step = await ladder._lint()
    assert step.ok and seen_commands == ["npm run lint"]


async def test_lint_skips_without_eslint_config(context: ToolContext) -> None:
    ladder = AngularVerifyLadder(context, _node_env(context.workspace.app_dir))
    step = await ladder._lint()
    assert step.skipped and step.ok


async def test_build_runs_the_repos_own_script_name(
    context: ToolContext, monkeypatch: pytest.MonkeyPatch
) -> None:
    seen_commands = []

    async def fake_execute(_context: ToolContext, command: str, *_a: object, **_kw: object) -> ToolResult:
        seen_commands.append(command)
        return ToolResult(ok=True, content="done")

    monkeypatch.setattr(angular_ladder_module, "execute", fake_execute)
    ladder = AngularVerifyLadder(
        context, _node_env(context.workspace.app_dir, build_command="pnpm run build")
    )
    step = await ladder._build()
    assert step.ok and seen_commands == ["pnpm run build"]


async def test_build_skips_without_a_build_script(context: ToolContext) -> None:
    ladder = AngularVerifyLadder(context, _node_env(context.workspace.app_dir, build_command=None))
    step = await ladder._build()
    assert step.skipped and step.ok


# --- dispatcher: Angular vs React routing -------------------------------------------------------------


async def test_dispatcher_routes_angular_project_to_the_angular_ladder(
    context: ToolContext, monkeypatch: pytest.MonkeyPatch
) -> None:
    _write_angular_json(context.workspace.app_dir)
    context.workspace.info.node_env = _node_env(context.workspace.app_dir)
    context.workspace.write_text("backend/app.component.ts", "export class AppComponent {}\n")

    async def fake_angular_run(self: AngularVerifyLadder) -> LadderReport:
        return LadderReport(steps=[StepResult("typecheck (ng build)", True, "clean")])

    def fail_if_react_used(*_args: object, **_kwargs: object) -> None:
        raise AssertionError("ReactVerifyLadder must not run for an Angular project")

    monkeypatch.setattr(AngularVerifyLadder, "run", fake_angular_run)
    monkeypatch.setattr(react_ladder_module, "ReactVerifyLadder", fail_if_react_used)
    report = await VerifyLadder(context).run()
    assert any(s.name == "typecheck (ng build)" for s in report.steps)


async def test_dispatcher_routes_plain_project_to_the_react_ladder(
    context: ToolContext, monkeypatch: pytest.MonkeyPatch
) -> None:
    """No angular.json present: the dispatcher must still pick the React ladder, not Angular's."""
    context.workspace.info.node_env = _node_env(context.workspace.app_dir)
    context.workspace.write_text("backend/App.tsx", "export const App = () => null;\n")

    async def fake_react_run(self: ReactVerifyLadder) -> LadderReport:
        return LadderReport(steps=[StepResult("typecheck (tsc)", True, "clean")])

    def fail_if_angular_used(*_args: object, **_kwargs: object) -> None:
        raise AssertionError("AngularVerifyLadder must not run without angular.json")

    monkeypatch.setattr(ReactVerifyLadder, "run", fake_react_run)
    monkeypatch.setattr(angular_ladder_module, "AngularVerifyLadder", fail_if_angular_used)
    report = await VerifyLadder(context).run()
    assert any(s.name == "typecheck (tsc)" for s in report.steps)


# --- regression guard: plain React project behaviour is completely unchanged --------------------------


async def test_react_project_behaviour_is_unaffected_by_angular_support(
    context: ToolContext, monkeypatch: pytest.MonkeyPatch
) -> None:
    """No angular.json anywhere in the workspace: dispatcher behaviour, rung names and invocations must be
    identical to before D-144 — the same discipline D-139/D-140 already applied to "Python-only workspace
    unaffected"."""
    assert not (context.workspace.app_dir / "angular.json").exists()
    (context.workspace.app_dir / "package.json").write_text(
        json.dumps({"name": "app", "devDependencies": {"vitest": "^1.0.0"}}), encoding="utf-8"
    )
    context.workspace.info.node_env = _node_env(context.workspace.app_dir, test_command="npm run test")
    context.workspace.write_text("backend/App.tsx", "export const App = () => null;\n")

    seen_commands = []

    async def fake_execute(_context: ToolContext, command: str, *_a: object, **_kw: object) -> ToolResult:
        seen_commands.append(command)
        return ToolResult(ok=True, content="Test Files  1 passed (1)\n")

    monkeypatch.setattr(react_ladder_module, "execute", fake_execute)
    report = await VerifyLadder(context).run()
    assert any(s.name == "unit tests (vitest)" for s in report.steps)
    # The React ladder must never gain the Angular CI-flag rewrite: exactly the plain test command.
    assert "npm run test" in seen_commands
    assert not any("--watch=false" in c for c in seen_commands)


def test_fixture_is_present() -> None:
    assert (FIXTURE_REPO / "backend").exists()
