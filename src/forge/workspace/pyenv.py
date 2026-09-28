"""Finds the app's own venv and makes its interpreter import the workspace copy (spec §6.1 step 5)."""

from __future__ import annotations

import configparser
import os
import subprocess
import sys
import tempfile
from pathlib import Path

from pydantic import BaseModel

APP_MARKERS = ("app.py", "wsgi.py", "manage.py", "requirements.txt", "pyproject.toml", "setup.py")
NOT_PACKAGES = {"tests", "test", "venv", ".venv", "env", "build", "dist", "docs", "scripts", "migrations"}

# Reports where a package would be imported from, without executing it (importing could run app code).
ORIGIN_PROBE = (
    "import importlib.util, sys\n"
    "spec = importlib.util.find_spec(sys.argv[1])\n"
    "print(spec.origin if spec and spec.origin else '')"
)

SHIM_TEMPLATE = '''"""Written by Forge (spec §6.1). Runs after .pth files, so it can undo an editable
install of the ORIGINAL app that would otherwise shadow the workspace copy.
Chains to any other sitecustomize."""
import importlib.util
import os
import sys

_COPY = {copy!r}
_ORIGINAL = {original!r}
_TOP_PACKAGES = {top_packages!r}


def _norm(path):
    return os.path.normcase(os.path.abspath(path)) if path else path


sys.path[:] = [entry for entry in sys.path if _norm(entry) not in (_norm(_ORIGINAL), _norm(_COPY))]
sys.path.insert(0, _COPY)


def _maps_top_package(finder):
    module = sys.modules.get(getattr(finder, "__module__", ""))
    mapping = getattr(module, "MAPPING", None) or {{}}
    return any(name in mapping for name in _TOP_PACKAGES)


sys.meta_path[:] = [finder for finder in sys.meta_path if not _maps_top_package(finder)]

_here = _norm(os.path.dirname(__file__))
for _entry in list(sys.path):
    _candidate = os.path.join(_entry or ".", "sitecustomize.py")
    if _norm(os.path.dirname(_candidate)) != _here and os.path.isfile(_candidate):
        _spec = importlib.util.spec_from_file_location("_forge_chained_sitecustomize", _candidate)
        if _spec and _spec.loader:
            _spec.loader.exec_module(importlib.util.module_from_spec(_spec))
        break
'''


class VenvInfo(BaseModel):
    path: str
    python: str
    base_interpreter_ok: bool
    version: str | None = None


class PythonEnvironment(BaseModel):
    """How Forge runs the app: its own venv interpreter, with imports pointed at the workspace copy."""

    python: str
    venv: str
    app_dir: str  # the app folder inside the workspace copy
    top_packages: list[str]
    shim_dir: str | None = None  # set only when an editable install of the original had to be undone
    extra_paths: list[str] = []  # after the app on PYTHONPATH (Mode B: _harness, so real new code wins)

    def command_env(self, base: dict[str, str] | None = None) -> dict[str, str]:
        env = dict(os.environ if base is None else base)
        env.pop("PYTHONHOME", None)
        paths = [self.shim_dir, self.app_dir] if self.shim_dir else [self.app_dir]
        paths += self.extra_paths
        env["PYTHONPATH"] = os.pathsep.join(p for p in paths if p)
        env["PYTHONDONTWRITEBYTECODE"] = "1"
        env["PYTHONUTF8"] = "1"
        # The same effect as activating the venv, without touching the user's shell.
        env["VIRTUAL_ENV"] = self.venv
        env["PATH"] = str(Path(self.python).parent) + os.pathsep + env.get("PATH", "")
        return env


def venv_python(venv_dir: Path) -> Path:
    return venv_dir / ("Scripts/python.exe" if sys.platform == "win32" else "bin/python")


def find_venvs(app_dir: Path) -> list[VenvInfo]:
    found = []
    for child in sorted(app_dir.iterdir()) if app_dir.is_dir() else []:
        config_file = child / "pyvenv.cfg"
        if not (child.is_dir() and config_file.is_file()):
            continue
        parser = configparser.ConfigParser()
        parser.read_string("[venv]\n" + config_file.read_text(encoding="utf-8", errors="replace"))
        home = parser.get("venv", "home", fallback="")
        base_ok = bool(home) and any(
            (Path(home) / name).exists() for name in ("python.exe", "python", "python3")
        )
        found.append(
            VenvInfo(
                path=str(child),
                python=str(venv_python(child)),
                base_interpreter_ok=base_ok and venv_python(child).exists(),
                version=parser.get("venv", "version", fallback=None)
                or parser.get("venv", "version_info", fallback=None),
            )
        )
    return found


def find_top_packages(app_dir: Path) -> list[str]:
    return sorted(
        child.name
        for child in app_dir.iterdir()
        if child.is_dir() and (child / "__init__.py").is_file() and child.name not in NOT_PACKAGES
    )


def find_app_folder_candidates(repo_root: Path, max_depth: int = 2) -> list[str]:
    """Folders that look like a Python app with its own venv, best candidates first."""
    scored: list[tuple[int, str]] = []
    for directory, subdirectories, filenames in os.walk(repo_root):
        depth = len(Path(directory).relative_to(repo_root).parts)
        subdirectories[:] = [
            d for d in subdirectories if not d.startswith(".") and d not in {"node_modules", "venv"}
        ]
        if depth > max_depth:
            subdirectories[:] = []
            continue
        has_venv = bool(find_venvs(Path(directory)))
        has_marker = any(name in filenames for name in APP_MARKERS)
        if has_venv or (has_marker and find_top_packages(Path(directory))):
            relative = Path(directory).relative_to(repo_root).as_posix()
            scored.append((0 if has_venv else 1, relative))
    return [relative for _, relative in sorted(scored)]


def import_origin(env: PythonEnvironment, package: str) -> str:
    # Worst case on purpose: `python -c` or `-m` from the copy would put the copy first on sys.path and
    # hide shadowing, but console scripts (pytest.exe, flask.exe) get no such entry. Running the probe
    # as a script from a neutral folder reproduces what they see.
    with tempfile.TemporaryDirectory(prefix="forge-probe-") as probe_dir:
        probe = Path(probe_dir) / "forge_origin_probe.py"
        probe.write_text(ORIGIN_PROBE, encoding="utf-8")
        result = subprocess.run(
            [env.python, str(probe), package],
            cwd=probe_dir,
            env=env.command_env(),
            capture_output=True,
            text=True,
            timeout=60,
            check=False,
        )
    return result.stdout.strip()


def write_import_shim(
    shim_dir: Path, copy_app_dir: Path, original_app_dir: Path, top_packages: list[str]
) -> None:
    shim_dir.mkdir(parents=True, exist_ok=True)
    (shim_dir / "sitecustomize.py").write_text(
        SHIM_TEMPLATE.format(
            copy=str(copy_app_dir), original=str(original_app_dir), top_packages=top_packages
        ),
        encoding="utf-8",
    )


def origins_outside_copy(env: PythonEnvironment) -> dict[str, str]:
    """Top packages whose import would NOT come from the workspace copy -> where they come from."""
    copy_root = os.path.normcase(os.path.abspath(env.app_dir))
    wrong = {}
    for package in env.top_packages:
        origin = import_origin(env, package)
        if not os.path.normcase(os.path.abspath(origin or ".")).startswith(copy_root + os.sep):
            wrong[package] = origin or "(not importable)"
    return wrong
