"""Detects an existing Node/React app in a Mode A app folder (D-137/D-138): the package manager, the node
binary, and the real script names the repo's own package.json defines — Forge never assumes 'npm run build'
or 'npm test' literally, since repos customise these (mirrors pyenv.py's shape for the Python side)."""

from __future__ import annotations

import json
import os
import shutil
from pathlib import Path
from typing import Literal

from pydantic import BaseModel

PackageManager = Literal["npm", "yarn", "pnpm"]

# Lockfile presence decides the package manager, the same way a repo's own choice is read rather than assumed.
_LOCKFILES: tuple[tuple[str, PackageManager], ...] = (
    ("package-lock.json", "npm"),
    ("yarn.lock", "yarn"),
    ("pnpm-lock.yaml", "pnpm"),
)

RUN_PREFIX: dict[PackageManager, str] = {"npm": "npm run", "yarn": "yarn", "pnpm": "pnpm run"}
INSTALL_COMMAND: dict[PackageManager, str] = {
    "npm": "npm install",
    "yarn": "yarn install",
    "pnpm": "pnpm install",
}


class NodeEnvironment(BaseModel):
    """How Forge runs an existing React/Node app: which package manager it uses, the node binary found on
    this machine, and the real script names from the app's own package.json (never assumed)."""

    node: str  # the node binary path (shutil.which result)
    package_manager: PackageManager
    app_dir: str  # the app folder inside the workspace copy (same folder as the Python app, phase 1)
    install_command: str
    build_command: str | None = None
    test_command: str | None = None
    lint_command: str | None = None
    typecheck_command: str | None = None
    dev_command: str | None = None  # for the browser smoke check (D-138/D-14x): the repo's own dev/start/
    # preview script, never a literal "npm run dev" assumed — same "read the repo's own scripts" rule.


def find_node_app_candidates(repo_root: Path, max_depth: int = 2) -> list[str]:
    """Folders that look like a Node/React app (have their own package.json), best candidates first
    (shallower folders with a "start"/"build" script rank first, mirroring pyenv's has_venv-first scoring)."""
    scored: list[tuple[int, str]] = []
    for directory, subdirectories, filenames in os.walk(repo_root):
        depth = len(Path(directory).relative_to(repo_root).parts)
        subdirectories[:] = [d for d in subdirectories if not d.startswith(".") and d != "node_modules"]
        if depth > max_depth:
            subdirectories[:] = []
            continue
        if "package.json" in filenames:
            scripts = _read_scripts(Path(directory) / "package.json")
            has_app_scripts = bool({"build", "start"} & scripts.keys())
            relative = Path(directory).relative_to(repo_root).as_posix()
            scored.append((0 if has_app_scripts else 1, relative))
    return [relative for _, relative in sorted(scored)]


def detect_node_environment(app_dir: Path) -> NodeEnvironment | None:
    """None when the folder has no package.json (no Node/React app here) or no node binary is on PATH —
    matching how setup_python_environment returns None when there is nothing to run against."""
    package_json = app_dir / "package.json"
    if not package_json.is_file():
        return None
    node = shutil.which("node")
    if not node:
        return None
    package_manager = _detect_package_manager(app_dir)
    scripts = _read_scripts(package_json)
    return NodeEnvironment(
        node=node,
        package_manager=package_manager,
        app_dir=str(app_dir),
        install_command=INSTALL_COMMAND[package_manager],
        build_command=_run_command(package_manager, scripts, "build"),
        test_command=_run_command(package_manager, scripts, "test"),
        lint_command=_run_command(package_manager, scripts, "lint"),
        typecheck_command=_run_command(package_manager, scripts, ("typecheck", "type-check")),
        dev_command=_run_command(package_manager, scripts, ("dev", "start", "preview")),
    )


def _detect_package_manager(app_dir: Path) -> PackageManager:
    for lockfile, manager in _LOCKFILES:
        if (app_dir / lockfile).is_file():
            return manager
    return "npm"  # no lockfile found: npm is the ecosystem default


def _read_scripts(package_json: Path) -> dict[str, str]:
    try:
        data = json.loads(package_json.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    scripts = data.get("scripts")
    return scripts if isinstance(scripts, dict) else {}


def _run_command(
    package_manager: PackageManager, scripts: dict[str, str], names: str | tuple[str, ...]
) -> str | None:
    """The command to invoke a package.json script by its REAL name, or None when the repo has none of the
    candidate names (a rung then skips rather than inventing a script the repo doesn't define)."""
    candidates = (names,) if isinstance(names, str) else names
    for name in candidates:
        if name in scripts:
            return f"{RUN_PREFIX[package_manager]} {name}"
    return None
