"""Creating a Mode B (standalone) workspace (spec §6A.1): no repository is read or even named.

<workspace>/project/    the deliverable, host-relative paths      (Forge's "repo" in this mode)
<workspace>/_harness/   host_stubs/ (on PYTHONPATH after project/), harness_conftest.py (pytest -p),
                        run_app.py
<workspace>/output/     built at EXPORT
<workspace>/.forge/     state + host_profile_ref.json
<workspace>/.venv/      the workspace venv; host package versions are installed into it by `pip install`
                        through the agent's shell (always asks the user first)
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from collections.abc import Callable
from datetime import datetime
from pathlib import Path

from forge.modeb.profile import HostProfile
from forge.workspace.manifest import BaselineManifest
from forge.workspace.pyenv import PythonEnvironment, venv_python
from forge.workspace.workspace import Workspace, WorkspaceError, WorkspaceInfo

SetupProgressCallback = Callable[[str], None]

HARNESS_CONFTEST = '''"""Forge Mode B test harness (NOT delivered): loaded with `pytest -p harness_conftest`.

Put fixtures that stand in for the host here — e.g. a database session bound to the scratch schema, an app
built by _harness/run_app.py, fake LLM clients — so project/tests run without the host.
"""
'''

RUN_APP = '''"""Minimal Flask app for smoke tests and the OpenAPI check (NOT delivered).

Register the new blueprint(s) the way the host does (see the host profile), e.g.:

    from flask import Flask
    from flask_smorest import Api
    from <package>.api.<feature>.routes import blp

    def create_app() -> Flask:
        app = Flask(__name__)
        app.config.update(API_TITLE="harness", API_VERSION="v1", OPENAPI_VERSION="3.0.3",
                          OPENAPI_URL_PREFIX="/", OPENAPI_JSON_PATH="openapi.json")
        Api(app).register_blueprint(blp)
        return app
"""
'''

STUBS_README = """# Host stubs (NOT delivered)

Only the host symbols the new code imports, at the same import paths (e.g. `<package>/db.py` with
`get_session()`), behaving as the host profile describes. They are generated from INTERFACE_CONTRACT.md so
the two never drift. This folder is on PYTHONPATH after project/, so real new code always wins.

Every stub package's `__init__.py` must start with

    __path__ = __import__("pkgutil").extend_path(__path__, __name__)

so the host package is shared between project/ (the new code) and here (the stubs) instead of one hiding
the other. Delivered code in project/ never contains the host's own package `__init__.py`.
"""


def create_standalone_workspace(
    root: Path,
    profile: HostProfile,
    base_python: str | None = None,
    on_progress: SetupProgressCallback | None = None,
) -> Workspace:
    def notify(phase: str) -> None:
        if on_progress is not None:
            on_progress(phase)

    root = root.resolve()
    if root.exists() and any(root.iterdir()):
        raise WorkspaceError(f"{root} is not empty: choose a new folder for the workspace.")
    notify("Creating workspace folders…")
    for folder in ("project", "_harness/host_stubs", "output", ".forge"):
        (root / folder).mkdir(parents=True, exist_ok=True)
    (root / "_harness" / "harness_conftest.py").write_text(HARNESS_CONFTEST, encoding="utf-8")
    (root / "_harness" / "run_app.py").write_text(RUN_APP, encoding="utf-8")
    (root / "_harness" / "host_stubs" / "README.md").write_text(STUBS_README, encoding="utf-8")
    notify("Creating the Python environment…")
    python = _create_venv(root / ".venv", base_python or sys.executable)
    notify("Installing the test runner (pytest)…")
    setup_note = install_test_runner(python)
    (root / ".forge" / "setup.json").write_text(json.dumps({"test_runner": setup_note}), encoding="utf-8")
    env = PythonEnvironment(
        python=str(python),
        venv=str(root / ".venv"),
        app_dir=str(root / "project"),
        top_packages=[],
        extra_paths=[str(root / "_harness" / "host_stubs"), str(root / "_harness")],
    )
    info = WorkspaceInfo(
        mode="B",
        name=root.name,
        repo_path="",
        app_subfolder="",
        created=datetime.now().isoformat(timespec="seconds"),
        python_env=env,
    )
    workspace = Workspace(root, info)
    workspace.save_info()
    BaselineManifest.empty().save(root / ".forge" / "baseline_manifest.json")
    reference = {"profile": profile.name, "version": profile.version}
    (root / ".forge" / "host_profile_ref.json").write_text(json.dumps(reference), encoding="utf-8")
    return workspace


def _create_venv(folder: Path, base_python: str) -> Path:
    """An empty venv; the host's package versions are installed with the user's approval (pip install)."""
    subprocess.run([base_python, "-m", "venv", str(folder)], check=True, capture_output=True, timeout=300)
    return venv_python(folder)


TEST_RUNNER = "pytest"
PIP_TIMEOUT_S = 600


def install_test_runner(python: Path) -> str:
    """pytest into the new, empty workspace venv (DECISIONS D-111). Without it no task can be verified, and
    in a headless run the approval for `pip install` can't be given, so every task blocked (seen live).
    Creating the workspace is the user's own action and pytest changes nothing on the host.
    Returns "installed" or why not."""
    if os.environ.get("FORGE_SKIP_TEST_RUNNER_INSTALL"):
        return "skipped (FORGE_SKIP_TEST_RUNNER_INSTALL)"
    try:
        result = subprocess.run(
            [str(python), "-m", "pip", "install", "--disable-pip-version-check", "-q", TEST_RUNNER],
            capture_output=True,
            text=True,
            timeout=PIP_TIMEOUT_S,
        )
    except (OSError, subprocess.TimeoutExpired) as error:
        return f"not installed: {error}"
    if result.returncode != 0:
        return "not installed: " + (result.stderr or result.stdout).strip()[-300:]
    return "installed"


def test_runner_note(workspace: Workspace) -> str:
    path = workspace.forge_dir / "setup.json"
    try:
        return str(json.loads(path.read_text(encoding="utf-8")).get("test_runner", ""))
    except (OSError, ValueError):
        return ""


def profile_ref(workspace: Workspace) -> dict[str, object]:
    path = workspace.forge_dir / "host_profile_ref.json"
    data: dict[str, object] = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
    return data
