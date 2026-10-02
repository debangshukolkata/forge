"""The fresh copy run (spec §6.6 step 2): copy the user's real repository again, with their pasted
changes, into <workspace>/.forge/diagnose_run/<n>/ and run the test suite there with their venv. Nothing
runs inside the real repository; commands run in the low-integrity sandbox when available, so they
can't write to it."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from forge.safety.sandbox import SandboxUnavailableError, label_low
from forge.toolkit.powershell import ps_quote, run_powershell
from forge.verify.checks import DEFAULT_OPENAPI_SETUP, MARKER, OPENAPI_SCRIPT
from forge.verify.ladder import PYTEST_ARGS
from forge.verify.parsers import TestReport, parse_pytest
from forge.workspace.copy_repo import copy_app_folder
from forge.workspace.ignore import IgnoreRules
from forge.workspace.pyenv import PythonEnvironment, write_import_shim
from forge.workspace.workspace import Workspace

RUN_TIMEOUT_S = 900
SMOKE_TIMEOUT_S = 120
MAX_FILE_BYTES = 5 * 1024 * 1024


@dataclass
class FreshRun:
    folder: Path
    tests: TestReport | None
    output_tail: str
    sandboxed: bool
    note: str = ""
    # App smoke (spec §6.6): the app built in-process from the fresh copy, and the routes it serves.
    smoke: dict[str, Any] = field(default_factory=dict)


async def fresh_copy_run(workspace: Workspace, number: int, sandbox: bool = True) -> FreshRun:
    repo = Path(workspace.info.repo_path)
    app = workspace.info.app_subfolder
    folder = workspace.jail.check(workspace.forge_dir / "diagnose_run" / str(number))
    copy_app_folder(repo, app, folder, IgnoreRules(repo), workspace.jail, MAX_FILE_BYTES)
    env = workspace.info.python_env
    if env is None:
        return FreshRun(folder, None, "", False, "No usable venv for the app: the tests couldn't run.")
    app_dir = folder / app if app else folder
    run_env = PythonEnvironment(
        python=env.python, venv=env.venv, app_dir=str(app_dir), top_packages=env.top_packages
    )
    if env.shim_dir:  # the venv has an editable install of the real repo: redirect it to this copy
        shim = workspace.jail.check(folder.parent / f"{number}-pyshim")
        write_import_shim(shim, app_dir, repo / app, env.top_packages)
        run_env = run_env.model_copy(update={"shim_dir": str(shim)})
    scratch = workspace.jail.check(folder.parent / f"{number}-tmp")
    sandboxed = False
    if sandbox:
        try:
            label_low(folder)
            label_low(scratch)
            sandboxed = True
        except SandboxUnavailableError:
            sandboxed = False
    variables = run_env.command_env()
    if sandboxed:
        variables["TEMP"] = variables["TMP"] = str(scratch)
    command = f"& {ps_quote(env.python)} -m pytest {PYTEST_ARGS}"
    try:
        outcome = await run_powershell(command, app_dir, variables, RUN_TIMEOUT_S, scratch, sandboxed)
    except SandboxUnavailableError:
        sandboxed = False
        outcome = await run_powershell(command, app_dir, variables, RUN_TIMEOUT_S, scratch)
    tests = parse_pytest(outcome.output)
    note = "timed out" if outcome.timed_out else ""
    smoke = await _app_smoke(workspace, env.python, env.top_packages, app_dir, scratch, variables, sandboxed)
    return FreshRun(folder, tests if tests.ran else None, outcome.output[-6000:], sandboxed, note, smoke)


async def _app_smoke(
    workspace: Workspace,
    python: str,
    packages: list[str],
    app_dir: Path,
    scratch: Path,
    variables: dict[str, str],
    sandboxed: bool,
) -> dict[str, Any]:
    """Builds the app from the fresh copy (create_app() of its top package) and lists its OpenAPI routes —
    catches an import error or a missing registration that the tests happen not to cover."""
    if not packages:
        return {"ok": False, "error": "no top-level package found to build the app from"}
    setup = "    " + DEFAULT_OPENAPI_SETUP.format(package=packages[0]).replace("\n", "\n    ")
    script = workspace.jail.check(scratch / "app_smoke.py")
    script.parent.mkdir(parents=True, exist_ok=True)
    script.write_text(OPENAPI_SCRIPT.replace("__SETUP__", setup), encoding="utf-8")
    command = f"& {ps_quote(python)} {ps_quote(str(script))}"
    try:
        outcome = await run_powershell(command, app_dir, variables, SMOKE_TIMEOUT_S, scratch, sandboxed)
    except SandboxUnavailableError:
        outcome = await run_powershell(command, app_dir, variables, SMOKE_TIMEOUT_S, scratch)
    for line in reversed(outcome.output.splitlines()):
        if line.startswith(MARKER):
            result: dict[str, Any] = json.loads(line[len(MARKER) :])
            return result
    return {"ok": False, "error": "the smoke script printed no result: " + outcome.output[-800:]}
