"""The React/TS verify ladder (D-138) after edits to a Node/React app already in a Mode A repo: type-check,
lint, unit tests, then build — each rung reusing the repo's OWN tools and script names (from NodeEnvironment,
`workspace/nodeenv.py`), never inventing a command the repo doesn't already define. Not a VerifyLadder
subclass: these rungs don't decompose the same way TS has no separate "compile" step (tsc covers parse and
typecheck together) and a build rung has no Python equivalent — see D-138 for the full rationale.

Deliberately NOT here: the browser smoke-check rung. D-138 puts it at task/export checkpoints only, not on
every verify call (mirroring how Python's own slow full-suite rung is reserved for checkpoints too). It is
built in `agent/frontend_smoke.py` and called from `Orchestrator._export()` (agent/orchestrator.py), using
the existing headless browser tool (tools/browser.py, BrowserSession) — intentionally left out of this
module, not a missed rung.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from forge.tools.base import ToolContext
from forge.tools.shell import execute
from forge.verify.ladder import LadderReport, StepResult
from forge.workspace.nodeenv import NodeEnvironment

STEP_TIMEOUT_S = 300
BUILD_TIMEOUT_S = 600

# Jest/Vitest summary lines, e.g. "Tests:       1 failed, 3 passed, 4 total" / "Test Files  1 failed (1)".
_JEST_SUMMARY = re.compile(r"Tests:\s+(?:(\d+) failed, )?(?:(\d+) passed, )?(\d+) total")
_VITEST_SUMMARY = re.compile(r"Test Files\s+(?:(\d+) failed.*?)?(?:(\d+) passed.*?)?\((\d+)\)")


class ReactVerifyLadder:
    """Runs against an app folder's own package.json scripts; rungs skip (never fail) when the repo has no
    tsconfig/eslint config/test framework/build script, matching how the Python ladder skips mypy/ruff when
    the repo doesn't configure them."""

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
        output, ok = await self._run("npx tsc --noEmit", STEP_TIMEOUT_S)
        return StepResult("typecheck (tsc)", ok, output[-2000:] if not ok else "tsc --noEmit: clean")

    async def _lint(self) -> StepResult:
        if self.node_env.lint_command is None and not self._has_eslint_config():
            return StepResult("lint", True, "the repo has no ESLint config", skipped=True)
        command = self.node_env.lint_command or "npx eslint ."
        output, ok = await self._run(command, STEP_TIMEOUT_S)
        return StepResult("lint (eslint)", ok, output[-2000:] if not ok else "eslint: clean")

    async def _unit_tests(self) -> StepResult:
        framework = self._test_framework()
        if framework is None:
            return StepResult("unit tests", True, "no Jest or Vitest found in devDependencies", skipped=True)
        command = self.node_env.test_command or f"npx {framework} run"
        output, ok = await self._run(command, STEP_TIMEOUT_S)
        summary = _parse_js_test_summary(output, framework) or (output[-2000:] if not ok else "tests passed")
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
        data = _read_package_json(self.context.workspace.app_dir / "package.json")
        dependencies = {**data.get("dependencies", {}), **data.get("devDependencies", {})}
        if "vitest" in dependencies:
            return "vitest"
        if "jest" in dependencies:
            return "jest"
        return None

    async def _run(self, command: str, timeout_s: int) -> tuple[str, bool]:
        result = await execute(self.context, command, timeout_s, self.app_subfolder)
        return result.content, result.ok


def _read_package_json(path: Path) -> dict[str, Any]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return data if isinstance(data, dict) else {}


def _parse_js_test_summary(output: str, framework: str) -> str | None:
    """A reasonable regex on the summary line (v1, per D-138) — not the sophistication of parse_pytest."""
    pattern = _VITEST_SUMMARY if framework == "vitest" else _JEST_SUMMARY
    match = pattern.search(output)
    if not match:
        return None
    failed, passed, total = match.groups()
    parts = []
    if failed:
        parts.append(f"{failed} failed")
    if passed:
        parts.append(f"{passed} passed")
    parts.append(f"{total} total")
    return f"{framework}: " + ", ".join(parts)
