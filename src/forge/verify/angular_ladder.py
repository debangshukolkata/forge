"""The Angular verify ladder (D-143/D-144): typecheck, lint, unit tests, then build for an Angular-CLI app
already in a Mode A repo. A separate module from `react_ladder.py`, not Angular-aware branches inside it,
for the same reason `react_ladder.py` itself isn't a `VerifyLadder` subclass — Angular's rungs don't decompose
the same way React's do:
- typecheck goes through the Angular CLI (template type-checking, multiple tsconfig.*.json files), not bare
  `tsc --noEmit`;
- the default test framework (Karma+Jasmine) needs CI-mode flags appended or `ng test` hangs forever in watch
  mode against a real browser — a correctness concern with no React/Jest/Vitest equivalent to branch around.
Mixing these into `react_ladder.py` would turn every rung into a five-way "if Angular do X else do Y", which
is exactly the kind of rung-shape mismatch D-138 already used to justify a dedicated module over a shared
base class. Lint and build ARE ordinary npm scripts once wrapped (confirmed by reading `ng lint`/`ng build`'s
own docs and the fixture project's package.json shape) and are reused as-is via `NodeEnvironment`, the same
as React — those two rungs are thin wrappers with no Angular-specific logic to justify their own functions.

`workspace/nodeenv.py` needs no changes (D-143): a standard Angular-CLI project's package.json already
exposes build/test/lint/typecheck as ordinary npm scripts, so `NodeEnvironment` detection already works.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from forge.tools.base import ToolContext
from forge.tools.shell import execute
from forge.verify.ladder import LadderReport, StepResult
from forge.verify.react_ladder import _parse_js_test_summary, _read_package_json
from forge.workspace.nodeenv import NodeEnvironment

STEP_TIMEOUT_S = 300
BUILD_TIMEOUT_S = 600

# A custom Karma launcher declared in the repo's own karma.conf.js, e.g.:
#   customLaunchers: { ChromeHeadlessCI: { base: 'ChromeHeadless', flags: [...] } }
# Angular projects commonly define one of these (often to add --no-sandbox for CI containers); when present,
# it is the launcher the repo actually wants used in CI, not Forge's own generic ChromeHeadless guess.
_CUSTOM_LAUNCHER = re.compile(r"customLaunchers\s*:\s*\{\s*([A-Za-z_][\w]*)\s*:")

DEFAULT_HEADLESS_BROWSER = "ChromeHeadless"


def is_angular_project(app_dir: Path) -> bool:
    """The one detection signal D-143 names: an `angular.json` file at the app root. Distinct from Karma/
    Jasmine detection (`_test_framework`), which decides the TEST rung specifically — a project could in
    theory swap Karma for Jest while remaining an Angular-CLI project, so the two checks stay independent."""
    return (app_dir / "angular.json").is_file()


class AngularVerifyLadder:
    """Runs against an Angular-CLI app folder's own package.json scripts, same skip-don't-fail discipline as
    `ReactVerifyLadder`: a rung skips (never fails) when the repo has no tsconfig/ESLint config/test
    framework/build script."""

    def __init__(self, context: ToolContext, node_env: NodeEnvironment) -> None:
        assert context.shell is not None
        self.context = context
        self.node_env = node_env
        self.app_subfolder = context.workspace.info.app_subfolder or None

    async def run(self) -> LadderReport:
        report = LadderReport()
        for rung in (self._typecheck, self._lint, self._unit_tests, self._build):
            step = await rung()
            report.steps.append(step)
            if not step.ok:
                report.signature = step.summary
                break
        return report

    # --- rungs ---

    async def _typecheck(self) -> StepResult:
        app_dir = self.context.workspace.app_dir
        if not (app_dir / "tsconfig.json").is_file():
            return StepResult("typecheck", True, "no tsconfig.json: not a TypeScript app", skipped=True)
        # Bare `tsc --noEmit` (React's rung) skips Angular's own compiler pass, so it never exercises
        # `strictTemplates` and only ever sees whichever single tsconfig `tsc` picks up by default — an
        # Angular app typically has app/spec/e2e tsconfig.*.json files feeding different parts of the build.
        # `ng build` runs the full Angular compiler (ngc) against the app's real tsconfig, which does template
        # type-checking; it's slower than a typecheck-only pass but there is no dedicated "ng typecheck"
        # command in the Angular CLI (checked: `ng build`, `ng test`, `ng lint`, `ng e2e`, `ng serve` are the
        # CLI's own build-related commands, none of them a typecheck-only variant), so `ng build` doubles as
        # the typecheck rung here. `--configuration=development` is preferred over the (slower, minifying)
        # production default when the repo defines it, mirroring "prefer the repo's own convention" elsewhere
        # in this codebase; this rung only checks for errors; the separate `_build` rung below does the real
        # (production, by default) build the repo would actually ship.
        command = self._typecheck_command()
        output, ok = await self._run(command, BUILD_TIMEOUT_S)
        return StepResult("typecheck (ng build)", ok, output[-2000:] if not ok else f"{command}: clean")

    def _typecheck_command(self) -> str:
        app_dir = self.context.workspace.app_dir
        angular_json = _read_json(app_dir / "angular.json")
        configurations = _project_configurations(angular_json)
        base = self.node_env.build_command or "npx ng build"
        if "development" in configurations:
            return f"{base} --configuration=development"
        return base

    async def _lint(self) -> StepResult:
        if self.node_env.lint_command is None and not self._has_eslint_config():
            return StepResult("lint", True, "the repo has no ESLint config", skipped=True)
        command = self.node_env.lint_command or "npx ng lint"
        output, ok = await self._run(command, STEP_TIMEOUT_S)
        return StepResult("lint (ng lint)", ok, output[-2000:] if not ok else "ng lint: clean")

    async def _unit_tests(self) -> StepResult:
        framework = self._test_framework()
        if framework is None:
            return StepResult(
                "unit tests", True, "no Karma/Jasmine or Jest found in devDependencies", skipped=True
            )
        if framework == "karma":
            command = self._karma_ci_command()
        else:  # Angular's newer Jest builder: Jest's own default run is already one-shot, unlike ng test.
            command = self.node_env.test_command or "npx jest"
        output, ok = await self._run(command, STEP_TIMEOUT_S)
        summary = _parse_js_test_summary(output, "jest" if framework == "jest" else "karma") or (
            output[-2000:] if not ok else "tests passed"
        )
        return StepResult(f"unit tests ({framework})", ok, summary)

    async def _build(self) -> StepResult:
        if self.node_env.build_command is None:
            return StepResult("build", True, "no build script in package.json", skipped=True)
        output, ok = await self._run(self.node_env.build_command, BUILD_TIMEOUT_S)
        return StepResult("build", ok, output[-2000:] if not ok else "build succeeded")

    # --- helpers ---

    def _has_eslint_config(self) -> bool:
        app_dir = self.context.workspace.app_dir
        if any(
            (app_dir / name).is_file()
            for name in (".eslintrc", ".eslintrc.js", ".eslintrc.cjs", ".eslintrc.json", ".eslintrc.yml")
        ):
            return True
        if (app_dir / "eslint.config.js").is_file() or (app_dir / "eslint.config.mjs").is_file():
            return True
        return "eslintConfig" in _read_package_json(app_dir / "package.json")

    def _test_framework(self) -> str | None:
        """Karma/Jasmine (Angular's default) or Jest (supported by newer Angular versions). Checked via
        dependencies first (works regardless of config file layout), then a karma.conf.js file as a fallback
        for a repo that declares karma only as a transitive/global dependency."""
        app_dir = self.context.workspace.app_dir
        data = _read_package_json(app_dir / "package.json")
        dependencies = {**data.get("dependencies", {}), **data.get("devDependencies", {})}
        if "jest" in dependencies:
            return "jest"
        if "karma" in dependencies or "jasmine-core" in dependencies:
            return "karma"
        if (app_dir / "karma.conf.js").is_file():
            return "karma"
        return None

    def _karma_ci_command(self) -> str:
        """THE dangerous rung (D-143): `ng test`'s default is watch mode against a real browser, which never
        exits on its own. The repo's plain test_command (`npm run test` -> `ng test`) MUST NOT be run
        unmodified here — it is a real hang risk, not a style preference. CI-mode flags are always appended:
        `--watch=false` to stop the watcher, and `--browsers=<launcher>` to force a headless run. The launcher
        name prefers a custom one the repo's own karma.conf.js declares (commonly `ChromeHeadlessCI`, often
        adding `--no-sandbox` for CI containers) over Forge's own generic `ChromeHeadless` guess, per "prefer
        the repo's own convention" (the same rule `dev_command`/`build_command` etc. already follow)."""
        base = self.node_env.test_command or "npx ng test"
        browser = self._custom_karma_launcher() or DEFAULT_HEADLESS_BROWSER
        return f"{base} --watch=false --browsers={browser}"

    def _custom_karma_launcher(self) -> str | None:
        karma_conf = self.context.workspace.app_dir / "karma.conf.js"
        if not karma_conf.is_file():
            return None
        try:
            text = karma_conf.read_text(encoding="utf-8", errors="replace")
        except OSError:
            return None
        match = _CUSTOM_LAUNCHER.search(text)
        return match.group(1) if match else None

    async def _run(self, command: str, timeout_s: int) -> tuple[str, bool]:
        result = await execute(self.context, command, timeout_s, self.app_subfolder)
        return result.content, result.ok


def _read_json(path: Path) -> dict[str, Any]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return data if isinstance(data, dict) else {}


def _project_configurations(angular_json: dict[str, Any]) -> set[str]:
    """The build-target configuration names across every project in angular.json (usually just one project),
    e.g. {"production", "development"} — read generically rather than assuming the default CLI project name,
    since a repo may have renamed or restructured it."""
    names: set[str] = set()
    projects = angular_json.get("projects")
    if not isinstance(projects, dict):
        return names
    for project in projects.values():
        if not isinstance(project, dict):
            continue
        build_target = project.get("architect", {}).get("build", {})
        if isinstance(build_target, dict):
            configurations = build_target.get("configurations", {})
            if isinstance(configurations, dict):
                names.update(configurations.keys())
    return names
