"""Stack and commands (spec §11.2 STACK.md, COMMANDS.md), read from project files — no LLM."""

from __future__ import annotations

import re
import tomllib
from dataclasses import dataclass, field
from pathlib import Path

from forge.workspace.pyenv import find_venvs

KEY_PACKAGES = (
    "flask",
    "flask-smorest",
    "marshmallow",
    "sqlalchemy",
    "psycopg",
    "psycopg2",
    "psycopg2-binary",
    "asyncpg",
    "langchain",
    "langchain-core",
    "langchain-openai",
    "langgraph",
    "pydantic",
    "pytest",
    "alembic",
    "celery",
    "requests",
    "httpx",
    "pyjwt",
    "flask-jwt-extended",
    "gunicorn",
    "waitress",
)
_REQUIREMENT = re.compile(r"^\s*([A-Za-z0-9_.\-]+)(?:\[[^\]]*\])?\s*(==|>=|~=|<=|>|<)?\s*([^;#\s]*)")
_COMMAND_HINT = re.compile(
    r"^\s*(?:\$|>|PS>)?\s*((?:venv\\Scripts\\|\.venv\\Scripts\\|\.\\)?(?:python|pytest|flask|pip|ruff|mypy|black|alembic|make|uvicorn|waitress-serve|gunicorn)\b.*)$"
)


@dataclass
class StackFacts:
    python_version: str | None = None
    packages: dict[str, str] = field(default_factory=dict)  # name -> version spec
    requirement_files: list[str] = field(default_factory=list)
    lint_tools: list[str] = field(default_factory=list)
    type_checker: str | None = None
    test_runner: str | None = None


@dataclass
class CommandFacts:
    run: list[str] = field(default_factory=list)
    test: list[str] = field(default_factory=list)
    lint: list[str] = field(default_factory=list)
    other: list[str] = field(default_factory=list)
    sources: list[str] = field(default_factory=list)


def stack_facts(repo_dir: Path, original_app_dir: Path, app_subfolder: str) -> StackFacts:
    app = repo_dir / app_subfolder
    facts = StackFacts()
    venvs = find_venvs(original_app_dir)
    if venvs:
        facts.python_version = venvs[0].version
    for requirements in sorted(app.glob("requirements*.txt")):
        facts.requirement_files.append(requirements.relative_to(repo_dir).as_posix())
        for line in requirements.read_text(encoding="utf-8", errors="replace").splitlines():
            match = _REQUIREMENT.match(line)
            if match and not line.strip().startswith(("#", "-")):
                facts.packages[match.group(1).lower()] = (
                    f"{match.group(2) or ''}{match.group(3) or ''}" or "any"
                )
    pyproject = _toml(app / "pyproject.toml")
    for dependency in pyproject.get("project", {}).get("dependencies", []):
        match = _REQUIREMENT.match(dependency)
        if match:
            facts.packages.setdefault(
                match.group(1).lower(), f"{match.group(2) or ''}{match.group(3) or ''}" or "any"
            )
    tool = pyproject.get("tool", {})
    facts.lint_tools = sorted(
        {name for name in ("ruff", "black", "isort", "flake8", "pylint") if name in tool}
        | ({"ruff"} if (app / "ruff.toml").exists() else set())
        | ({"flake8"} if (app / ".flake8").exists() else set())
    )
    facts.type_checker = "mypy" if "mypy" in tool or (app / "mypy.ini").exists() else None
    facts.test_runner = (
        "pytest"
        if (
            (app / "pytest.ini").exists()
            or "pytest" in tool
            or "pytest" in facts.packages
            or (app / "tests").is_dir()
        )
        else None
    )
    return facts


def command_facts(repo_dir: Path, app_subfolder: str, stack: StackFacts) -> CommandFacts:
    app = repo_dir / app_subfolder
    commands = CommandFacts()
    for readme in [p for p in app.glob("README*") if p.is_file()]:
        commands.sources.append(readme.relative_to(repo_dir).as_posix())
        for line in readme.read_text(encoding="utf-8", errors="replace").splitlines():
            match = _COMMAND_HINT.match(line)
            if match:
                _classify(match.group(1).strip(), commands)
    makefile = app / "Makefile"
    if makefile.exists():
        commands.sources.append(makefile.relative_to(repo_dir).as_posix())
        commands.other += [
            f"make {t}" for t in re.findall(r"^([A-Za-z][\w-]*):", makefile.read_text(encoding="utf-8"), re.M)
        ]
    if stack.test_runner == "pytest" and not commands.test:
        commands.test.append("python -m pytest -q")
    for tool in stack.lint_tools:
        default = {
            "ruff": "python -m ruff check .",
            "black": "python -m black --check .",
            "flake8": "python -m flake8",
            "isort": "python -m isort --check-only .",
        }.get(tool)
        if default and default not in commands.lint:
            commands.lint.append(default)
    if stack.type_checker:
        commands.lint.append("python -m mypy")
    return commands


def _classify(command: str, commands: CommandFacts) -> None:
    lowered = command.lower()
    bucket = (
        commands.test
        if "pytest" in lowered
        else commands.lint
        if any(t in lowered for t in ("ruff", "mypy", "black", "flake8"))
        else commands.run
        if any(t in lowered for t in ("flask", "run", "uvicorn", "waitress", "gunicorn"))
        else commands.other
    )
    if command not in bucket:
        bucket.append(command)


def _toml(path: Path) -> dict:  # type: ignore[type-arg]
    if not path.exists():
        return {}
    try:
        return tomllib.loads(path.read_text(encoding="utf-8"))
    except tomllib.TOMLDecodeError:
        return {}
