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
import subprocess
import sys
from datetime import datetime
from pathlib import Path

from forge.modeb.profile import HostProfile
from forge.workspace.manifest import BaselineManifest
from forge.workspace.pyenv import PythonEnvironment, venv_python
from forge.workspace.workspace import Workspace, WorkspaceError, WorkspaceInfo

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
    root: Path, profile: HostProfile, base_python: str | None = None
) -> Workspace:
    root = root.resolve()
    if root.exists() and any(root.iterdir()):
        raise WorkspaceError(f"{root} is not empty: choose a new folder for the workspace.")
    for folder in ("project", "_harness/host_stubs", "output", ".forge"):
        (root / folder).mkdir(parents=True, exist_ok=True)
    (root / "_harness" / "harness_conftest.py").write_text(HARNESS_CONFTEST, encoding="utf-8")
    (root / "_harness" / "run_app.py").write_text(RUN_APP, encoding="utf-8")
    (root / "_harness" / "host_stubs" / "README.md").write_text(STUBS_README, encoding="utf-8")
    python = _create_venv(root / ".venv", base_python or sys.executable)
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


EXTEND_PATH_LINE = '__path__ = __import__("pkgutil").extend_path(__path__, __name__)'


def ensure_shared_stub_packages(workspace: Workspace) -> list[str]:
    """Every stub package that project/ also has must extend its __path__, or the stub hides the new code
    ("cannot import name 'x_service' from 'pkg.services'", seen live, the agent losing tasks to it). This is
    plumbing, not a design choice, so Forge does it before each test run. Returns the fixed files."""
    stubs = workspace.harness_dir / "host_stubs"
    fixed = []
    for init in sorted(stubs.rglob("__init__.py")) if stubs.is_dir() else []:
        package = init.parent.relative_to(stubs)
        if not (workspace.repo_dir / package).is_dir():
            continue
        text = init.read_text(encoding="utf-8")
        if "extend_path" in text:
            continue
        relative = f"_harness/host_stubs/{package.as_posix()}/__init__.py"
        workspace.write_text(
            relative, EXTEND_PATH_LINE + "\n" + text, reason="share the package with project/"
        )
        fixed.append(package.as_posix())
    return fixed


def profile_ref(workspace: Workspace) -> dict[str, object]:
    path = workspace.forge_dir / "host_profile_ref.json"
    data: dict[str, object] = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
    return data
