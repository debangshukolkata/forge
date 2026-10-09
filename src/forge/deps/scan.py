"""Finds the libraries a project uses by reading its manifests and lock files (D-238). Nothing is executed and
nothing leaves the computer: this is pure file reading, so it is quick and works offline."""

from __future__ import annotations

import json
import re
import tomllib
from collections.abc import Iterator
from pathlib import Path
from typing import Any

from forge.deps.license_read import npm_installed_license, python_installed_licenses
from forge.deps.model import SOURCE_INSTALLED, Dependency, Ecosystem, normalise

SKIP_FOLDERS = {
    "node_modules",
    ".git",
    ".venv",
    "venv",
    "env",
    "__pycache__",
    "dist",
    "build",
    ".forge",
    ".tox",
}
MAX_DEPTH = 3
MAX_FILE_BYTES = 5_000_000
DEV_GROUPS = {"dev", "test", "tests", "lint", "docs", "typing", "ci", "develop"}
_REQUIREMENT = re.compile(r"^\s*([A-Za-z0-9][A-Za-z0-9._-]*)\s*(?:\[[^\]]*\])?\s*([^;#]*)")
_PINNED = re.compile(r"^\s*(?:==|===)\s*([A-Za-z0-9][A-Za-z0-9._+!-]*)\s*$")


def _read_text(path: Path) -> str:
    if path.stat().st_size > MAX_FILE_BYTES:
        return ""
    return path.read_text(encoding="utf-8", errors="replace")


def _json(path: Path) -> Any:
    try:
        return json.loads(_read_text(path))
    except (OSError, ValueError):
        return None


def _toml(path: Path) -> dict[str, Any]:
    try:
        return tomllib.loads(_read_text(path))
    except (OSError, tomllib.TOMLDecodeError):
        return {}


def manifest_folders(root: Path) -> Iterator[Path]:
    """The project folder and its sub-folders (a few levels), skipping environments and build output."""
    stack = [(root, 0)]
    while stack:
        folder, depth = stack.pop()
        yield folder
        if depth >= MAX_DEPTH:
            continue
        try:
            children = sorted(p for p in folder.iterdir() if p.is_dir() and not p.is_symlink())
        except OSError:
            continue
        stack.extend((child, depth + 1) for child in children if child.name not in SKIP_FOLDERS)


# --- Python ---


def _python_spec(text: str) -> tuple[str, str] | None:
    """(name, spec) from a PEP 508 line such as 'requests[socks]>=2.0,<3 ; python_version>"3.8"'."""
    match = _REQUIREMENT.match(text)
    return (match.group(1), match.group(2).strip()) if match else None


def _requirement_lines(path: Path, seen: set[Path], depth: int = 0) -> Iterator[tuple[str, str]]:
    if path in seen or depth > 3 or not path.is_file():
        return
    seen.add(path)
    for raw in _read_text(path).splitlines():
        line = raw.split(" #")[0].strip()
        if line.startswith(("-r", "-c")) and not line.startswith("--"):
            included = line[2:].strip().lstrip("=").strip()
            yield from _requirement_lines((path.parent / included).resolve(), seen, depth + 1)
            continue
        if not line or line.startswith(("#", "-", "git+", "http")):  # blank, comment, option, editable, URL
            continue
        parsed = _python_spec(line)
        if parsed:
            yield parsed


def _from_requirements(folder: Path, root: Path) -> Iterator[Dependency]:
    for path in sorted(folder.glob("requirements*.txt")):
        dev = any(word in path.stem.lower() for word in ("dev", "test", "lint", "docs"))
        for name, spec in _requirement_lines(path.resolve(), set()):
            pinned = _PINNED.match(spec)
            yield Dependency(
                name=name,
                ecosystem="PyPI",
                spec=spec,
                version=pinned.group(1) if pinned else None,
                dev=dev,
                file=path.relative_to(root).as_posix(),
            )


def _from_pyproject(folder: Path, root: Path) -> Iterator[Dependency]:
    path = folder / "pyproject.toml"
    if not path.is_file():
        return
    data = _toml(path)
    relative = path.relative_to(root).as_posix()

    def entries(lines: Any, dev: bool) -> Iterator[Dependency]:
        for line in lines if isinstance(lines, list) else []:
            parsed = _python_spec(str(line))
            if parsed:
                pinned = _PINNED.match(parsed[1])
                yield Dependency(
                    name=parsed[0],
                    ecosystem="PyPI",
                    spec=parsed[1],
                    version=pinned.group(1) if pinned else None,
                    dev=dev,
                    file=relative,
                )

    project = data.get("project", {})
    yield from entries(project.get("dependencies"), False)
    for group, lines in (project.get("optional-dependencies") or {}).items():
        yield from entries(lines, str(group).lower() in DEV_GROUPS)
    for lines in (data.get("dependency-groups") or {}).values():
        yield from entries(lines, True)
    poetry = data.get("tool", {}).get("poetry", {})
    tables = [(poetry.get("dependencies") or {}, False), (poetry.get("dev-dependencies") or {}, True)]
    tables += [((g or {}).get("dependencies") or {}, True) for g in (poetry.get("group") or {}).values()]
    for table, dev in tables:
        for name, value in table.items():
            if name.lower() == "python":
                continue
            spec = value if isinstance(value, str) else str((value or {}).get("version", ""))
            pinned = re.fullmatch(r"=*\s*(\d[\w.+!-]*)", spec)
            yield Dependency(
                name=name,
                ecosystem="PyPI",
                spec=spec,
                version=pinned.group(1) if pinned else None,
                dev=dev,
                file=relative,
            )


def _python_lock_versions(path: Path) -> dict[str, str]:
    """name -> locked version from a poetry.lock, uv.lock or Pipfile.lock."""
    if path.name == "Pipfile.lock":
        data = _json(path) or {}
        return {
            name: str((info or {}).get("version", "")).lstrip("=")
            for section in ("default", "develop")
            for name, info in (data.get(section) or {}).items()
            if (info or {}).get("version")
        }
    return {
        str(package["name"]): str(package["version"])
        for package in _toml(path).get("package", [])
        if package.get("name") and package.get("version")
    }


PYTHON_LOCKS = ("poetry.lock", "uv.lock", "Pipfile.lock")


def _python_locks(folder: Path) -> dict[str, str]:
    """normalised name -> locked version, from every lock file in the folder."""
    return {
        normalise(name): version
        for filename in PYTHON_LOCKS
        if (folder / filename).is_file()
        for name, version in _python_lock_versions(folder / filename).items()
    }


def _locked_python_packages(folder: Path, root: Path) -> list[Dependency]:
    """Everything a lock file pins (mostly indirect libraries; direct ones merge with their entry)."""
    return [
        Dependency(
            name=name, ecosystem="PyPI", version=version, direct=False, file=path.relative_to(root).as_posix()
        )
        for filename in PYTHON_LOCKS
        if (path := folder / filename).is_file()
        for name, version in _python_lock_versions(path).items()
    ]


# --- JavaScript ---


def _npm_lock_versions(folder: Path) -> dict[str, str]:
    """name -> top-level locked version, from package-lock.json (lockfile v1, v2 and v3)."""
    data = _json(folder / "package-lock.json")
    versions: dict[str, str] = {}
    if not isinstance(data, dict):
        return versions
    for location, info in (data.get("packages") or {}).items():
        if location.startswith("node_modules/") and "version" in (info or {}):
            nested = location.count("node_modules/") > 1
            name = location.rsplit("node_modules/", 1)[1]
            if not nested or name not in versions:
                versions[name] = str(info["version"])
    if not versions:

        def walk(table: dict[str, Any]) -> None:
            for name, info in table.items():
                if isinstance(info, dict) and "version" in info:
                    versions.setdefault(name, str(info["version"]))
                    walk(info.get("dependencies") or {})

        walk(data.get("dependencies") or {})
    return versions


def _from_package_json(folder: Path, root: Path) -> Iterator[Dependency]:
    path = folder / "package.json"
    data = _json(path) if path.is_file() else None
    if not isinstance(data, dict):
        return
    locked = _npm_lock_versions(folder)
    for table, dev in (("dependencies", False), ("optionalDependencies", False), ("devDependencies", True)):
        for name, spec in (data.get(table) or {}).items():
            version = locked.get(name)
            if version is None:
                installed = _json(folder / "node_modules" / name / "package.json")
                version = (
                    str(installed["version"])
                    if isinstance(installed, dict) and "version" in installed
                    else None
                )
            yield Dependency(
                name=name,
                ecosystem="npm",
                spec=str(spec),
                version=version,
                dev=dev,
                file=path.relative_to(root).as_posix(),
            )
    direct = {
        name
        for table in ("dependencies", "optionalDependencies", "devDependencies")
        for name in (data.get(table) or {})
    }
    for name, version in locked.items():
        if name not in direct:
            yield Dependency(
                name=name,
                ecosystem="npm",
                version=version,
                direct=False,
                file=f"{folder.relative_to(root).as_posix()}/package-lock.json".lstrip("./"),
            )


# --- installed in the project's Python environment ---


def installed_python_packages(venv: Path) -> dict[str, tuple[str, str]]:
    """normalised name -> (name, version) from the *.dist-info folders of a virtual environment."""
    found: dict[str, tuple[str, str]] = {}
    for site in [venv / "Lib" / "site-packages", *sorted((venv / "lib").glob("python*/site-packages"))]:
        if not site.is_dir():
            continue
        for info in site.glob("*.dist-info"):
            name, _, version = info.name[: -len(".dist-info")].rpartition("-")
            if name[:1].isalnum() and version:  # a leftover "~orge-1.0.dist-info" is not a package
                found[normalise(name)] = (name.replace("_", "-"), version)
    return found


# --- everything together ---


def scan_project(
    root: Path,
    venv: Path | None = None,
    known_packages: dict[str, str] | None = None,
) -> list[Dependency]:
    """Every library found under `root`. A direct library without a pinned version gets the locked or
    installed version when there is one. `known_packages` (name -> version) is added as-is (the host of a
    standalone project)."""
    direct: list[Dependency] = []
    indirect: list[Dependency] = []
    for folder in manifest_folders(root):
        locks = _python_locks(folder)
        for dependency in [*_from_requirements(folder, root), *_from_pyproject(folder, root)]:
            if dependency.version is None:
                dependency.version = locks.get(normalise(dependency.name))
            direct.append(dependency)
        indirect.extend(_locked_python_packages(folder, root))
        for dependency in _from_package_json(folder, root):
            (direct if dependency.direct else indirect).append(dependency)
    installed = installed_python_packages(venv) if venv is not None else {}
    for dependency in direct:
        if dependency.version is None and dependency.ecosystem == "PyPI":
            entry = installed.get(normalise(dependency.name))
            dependency.version = entry[1] if entry else None
    for name, version in (known_packages or {}).items():
        direct.append(
            Dependency(name=name, ecosystem="PyPI", version=str(version) or None, file="host profile")
        )
    merged = _merged(direct, indirect, installed)
    _read_installed_licenses(merged, root, venv)
    return merged


def _merged(
    direct: list[Dependency], indirect: list[Dependency], installed: dict[str, tuple[str, str]]
) -> list[Dependency]:
    result: dict[tuple[Ecosystem, str], Dependency] = {}
    for dependency in direct:
        key = (dependency.ecosystem, normalise(dependency.name))
        existing = result.get(key)
        if existing is None:
            result[key] = dependency
        elif existing.version is None and dependency.version:
            existing.version = dependency.version
    for dependency in indirect:
        result.setdefault((dependency.ecosystem, normalise(dependency.name)), dependency)
    for slug, (name, version) in installed.items():
        if ("PyPI", slug) not in result:
            result[("PyPI", slug)] = Dependency(
                name=name,
                ecosystem="PyPI",
                version=version,
                direct=False,
                file="installed in the project environment",
            )
    return sorted(result.values(), key=lambda d: (not d.direct, d.dev, d.ecosystem, normalise(d.name)))


def _read_installed_licenses(dependencies: list[Dependency], root: Path, venv: Path | None) -> None:
    """License names from the installed copies; libraries not installed here stay empty for deps.dev."""
    python = python_installed_licenses(venv) if venv is not None else {}
    for dependency in dependencies:
        if dependency.ecosystem == "PyPI":
            entry = python.get(normalise(dependency.name))
            found = entry[1] if entry and entry[0] == dependency.version else ""
        else:
            folder = root / Path(dependency.file).parent
            found = npm_installed_license(folder, dependency.name, dependency.version)
        if found:
            dependency.license, dependency.license_source = found, SOURCE_INSTALLED
