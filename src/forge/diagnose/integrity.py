"""The integrity check (spec §6.6 step 1), read-only on the real repository: did everything in output/ land
where COPY_INSTRUCTIONS said, completely? Each finding carries an exact instruction for the user.

- missing files (and the same file name somewhere else: wrong location);
- partially pasted files: the lines of Forge's version that are missing, with registration lines
  (register_blueprint, add_url_rule, ...) called out as missing registrations;
- line-ending/encoding-only differences (harmless, reported as info);
- files Forge deleted that are still there;
- packages the new code needs that the user's venv doesn't have;
- environment variables the new code reads that are set nowhere (names only — values are never read);
- tables/columns from DB_CHANGES.sql that don't exist in the database (read-only introspection).
"""

from __future__ import annotations

import json
import re
import subprocess
import sys
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal

from forge.workspace.output import OutputManifest
from forge.workspace.text_format import decode_text, detect_format
from forge.workspace.workspace import Workspace

Severity = Literal["error", "warning", "info"]
FORGE_DOCUMENTS = {
    "MANIFEST.json",
    "CHANGES.md",
    "changes.patch",
    "COPY_INSTRUCTIONS.md",
    "DB_CHANGES.sql",
    "SERVER_RUN.md",
    "NEW_DEPENDENCIES.md",
    "ENV_CHANGES.md",
    "INTEGRATION_GUIDE.md",
}
REGISTRATION = re.compile(
    r"register_blueprint|add_url_rule|include_router|register_error_handlers|add_resource|app\.register\("
)
ENV_READ = re.compile(
    r"""(?:os\.environ(?:\.get)?|os\.getenv|environ\.get|getenv)\s*[\[(]\s*["']([A-Z][A-Z0-9_]*)["']"""
)
IMPORT = re.compile(r"^\s*(?:from\s+([\w]+)[\w.]*\s+import|import\s+([\w]+))", re.MULTILINE)
REQUIREMENT = re.compile(r"^\s*([A-Za-z0-9][A-Za-z0-9._-]*)")
CREATE_TABLE = re.compile(
    r"create\s+table\s+(?:if\s+not\s+exists\s+)?(?:\"?(\w+)\"?\.)?\"?(\w+)\"?", re.IGNORECASE
)
ADD_COLUMN = re.compile(
    r"alter\s+table\s+(?:if\s+exists\s+)?(?:only\s+)?(?:\"?(\w+)\"?\.)?\"?(\w+)\"?\s+add\s+(?:column\s+)?(?:if\s+not\s+exists\s+)?\"?(\w+)\"?",
    re.IGNORECASE,
)
MAX_LINES_SHOWN = 12


@dataclass
class Finding:
    kind: str  # missing_file | partial_paste | missing_registration | wrong_location | line_endings | ...
    severity: Severity
    path: str
    detail: str
    instruction: str

    def render(self) -> str:
        return f"**[{self.severity}] {self.kind}** `{self.path}` — {self.detail}\n  → {self.instruction}"


@dataclass
class IntegrityReport:
    findings: list[Finding] = field(default_factory=list)
    checked_files: int = 0

    @property
    def problems(self) -> list[Finding]:
        return [f for f in self.findings if f.severity != "info"]

    def add(self, *args: Any) -> None:
        self.findings.append(Finding(*args))


def check_integrity(workspace: Workspace, db: Any = None) -> IntegrityReport:
    report = IntegrityReport()
    repo = Path(workspace.info.repo_path)
    manifest_path = workspace.output_dir / "MANIFEST.json"
    if not manifest_path.exists():
        report.add(
            "no_output",
            "error",
            "output/",
            "output/ has not been built yet",
            "Run /export (or forge export) first.",
        )
        return report
    manifest = OutputManifest.model_validate_json(manifest_path.read_text(encoding="utf-8"))
    for change in manifest.files:
        if change.secret:
            continue
        real = repo / change.path
        if change.status == "deleted":
            moved = next((c.path for c in manifest.files if c.moved_from == change.path), None)
            if real.exists():
                report.add(
                    "not_deleted",
                    "warning",
                    change.path,
                    "Forge deleted (or moved) this file, but it is still in your repository",
                    f"Delete `{change.path}`" + (f" (it now lives at `{moved}`)." if moved else "."),
                )
            continue
        report.checked_files += 1
        delivered = workspace.output_dir / change.path
        if not delivered.exists():
            continue
        if not real.exists():
            _missing(report, repo, change.path)
            continue
        _compare(report, change.path, _text(delivered), _text(real))
    _check_packages(report, workspace, manifest)
    _check_env_vars(report, workspace, manifest)
    _check_db_objects(report, workspace, db)
    return report


def _missing(report: IntegrityReport, repo: Path, path: str) -> None:
    name = Path(path).name
    elsewhere = [
        p.relative_to(repo).as_posix()
        for p in repo.rglob(name)
        if "venv" not in p.parts and ".git" not in p.parts
    ]
    if elsewhere:
        report.add(
            "wrong_location",
            "error",
            path,
            f"not at this path, but a file with this name is at `{elsewhere[0]}`",
            f"Move it to `{path}` (every path in COPY_INSTRUCTIONS is relative to the repository root).",
        )
    else:
        report.add(
            "missing_file",
            "error",
            path,
            "the new file is not in your repository",
            f"Copy `output/{path}` to `{path}` in your repository.",
        )


def _compare(report: IntegrityReport, path: str, delivered: str | None, real: str | None) -> None:
    if delivered is None or real is None:
        return  # binary: size/hash comparison is enough
    if delivered == real:
        return
    if _normalise(delivered) == _normalise(real):
        report.add(
            "line_endings",
            "info",
            path,
            "same content, different line endings/encoding/trailing spaces",
            "Nothing to do (your editor changed the line endings).",
        )
        return
    delivered_lines = [line.rstrip() for line in delivered.splitlines()]
    real_lines = {line.rstrip() for line in real.splitlines()}
    missing = [line for line in delivered_lines if line.strip() and line not in real_lines]
    if not missing:
        report.add(
            "extra_changes",
            "info",
            path,
            "your file has lines Forge's version doesn't (local edits?)",
            "Fine if intended; otherwise compare with output/ in CHANGES.md.",
        )
        return
    registrations = [line.strip() for line in missing if REGISTRATION.search(line)]
    shown = "\n".join(f"    {line.strip()}" for line in missing[:MAX_LINES_SHOWN])
    more = (
        f"\n    … and {len(missing) - MAX_LINES_SHOWN} more line(s)" if len(missing) > MAX_LINES_SHOWN else ""
    )
    if registrations:
        report.add(
            "missing_registration",
            "error",
            path,
            f"the registration isn't there: {'; '.join(registrations[:3])}",
            f"Add these lines to `{path}` as shown in CHANGES.md (or replace the file with "
            f"output/{path}):\n{shown}{more}",
        )
    else:
        report.add(
            "partial_paste",
            "error",
            path,
            f"{len(missing)} line(s) of Forge's version are missing (partial paste?)",
            f"Replace `{path}` with `output/{path}`, or paste the missing lines:\n{shown}{more}",
        )


def _check_packages(report: IntegrityReport, workspace: Workspace, manifest: OutputManifest) -> None:
    env = workspace.info.python_env
    if env is None:
        return
    # Modules the repository already imported were installed before Forge; only new ones are checked.
    top_packages = set(env.top_packages) | _modules_already_imported(workspace)
    modules: set[str] = set()
    requirements: set[str] = set()
    for change in manifest.files:
        if change.status == "deleted" or change.secret:
            continue
        text = _text(workspace.output_dir / change.path) or ""
        if change.path.endswith(".py") and change.status == "added":
            for from_name, import_name in IMPORT.findall(text):
                name = from_name or import_name
                if (
                    name
                    and name not in sys.stdlib_module_names
                    and name not in top_packages
                    and name != "__future__"
                ):
                    modules.add(name)
        if Path(change.path).name.startswith("requirements") and change.path.endswith(".txt"):
            before = _text(Path(workspace.info.repo_path) / change.path) if change.status != "added" else ""
            old = {
                m.group(1).lower() for line in (before or "").splitlines() if (m := REQUIREMENT.match(line))
            }
            for line in text.splitlines():
                match = REQUIREMENT.match(line)
                if match and not line.strip().startswith(("#", "-")) and match.group(1).lower() not in old:
                    requirements.add(match.group(1))
    if not modules and not requirements:
        return
    probe = (
        "import importlib.metadata as m, importlib.util as u, json, sys\n"
        f"mods, reqs = {sorted(modules)!r}, {sorted(requirements)!r}\n"
        "missing = [n for n in mods if u.find_spec(n) is None]\n"
        "def installed(d):\n    try:\n        m.version(d); return True\n    except "
        "m.PackageNotFoundError:\n        return False\n"
        "missing += ['req:' + d for d in reqs if not installed(d)]\n"
        "print(json.dumps(missing))\n"
    )
    with tempfile.TemporaryDirectory() as neutral:  # not the app folder: its packages mustn't mask anything
        result = subprocess.run(
            [env.python, "-c", probe], cwd=neutral, capture_output=True, text=True, timeout=60
        )
    try:
        missing = json.loads(result.stdout.strip().splitlines()[-1])
    except (ValueError, IndexError):
        report.add(
            "package_check_failed",
            "info",
            "venv",
            f"could not check packages: {result.stderr[-300:]}",
            "Check by hand with pip show.",
        )
        return
    for name in missing:
        package = name.removeprefix("req:")
        report.add(
            "missing_package",
            "error",
            "requirements",
            f"`{package}` is not installed in {env.venv}",
            f"Install it in your venv: `& '{env.python}' -m pip install {package}` (see "
            f"NEW_DEPENDENCIES.md / requirements).",
        )


def _modules_already_imported(workspace: Workspace) -> set[str]:
    """Imports in the repository as it was before Forge (the baseline): those packages were installed."""
    names: set[str] = set()
    for relative, entry in workspace.manifest.files.items():
        if not relative.endswith(".py") or entry.secret:
            continue
        saved = workspace.forge_dir / "baseline" / relative
        source = _text(saved) if saved.exists() else _text(workspace.repo_dir / relative)
        names |= {a or b for a, b in IMPORT.findall(source or "")}
    return names


def _check_env_vars(report: IntegrityReport, workspace: Workspace, manifest: OutputManifest) -> None:
    import os

    repo = Path(workspace.info.repo_path)
    needed: dict[str, str] = {}
    for change in manifest.files:
        if change.status == "deleted" or change.secret or not change.path.endswith(".py"):
            continue
        new = set(ENV_READ.findall(_text(workspace.output_dir / change.path) or ""))
        old = set(ENV_READ.findall(_text(repo / change.path) or "")) if change.status == "modified" else set()
        # The user's copy may already be Forge's version: compare against the baseline instead.
        saved = workspace.forge_dir / "baseline" / change.path
        if saved.exists():
            old = set(ENV_READ.findall(_text(saved) or ""))
        for name in new - old:
            needed.setdefault(name, change.path)
    if not needed:
        return
    defined = set(os.environ)
    app_dir = repo / workspace.info.app_subfolder
    for env_file in {repo / ".env", app_dir / ".env"}:
        if env_file.exists():  # names only: the part before '=' on each line
            defined |= {
                line.split("=", 1)[0].strip().removeprefix("export ").strip()
                for line in env_file.read_text(encoding="utf-8", errors="replace").splitlines()
                if "=" in line and not line.lstrip().startswith("#")
            }
    for name, path in sorted(needed.items()):
        if name not in defined:
            report.add(
                "missing_env_var",
                "error",
                path,
                f"the new code reads `{name}`, which is set nowhere Forge can see",
                f"Set `{name}` in your environment or the app's .env (see ENV_CHANGES.md). Forge "
                f"never needs the value.",
            )


def _check_db_objects(report: IntegrityReport, workspace: Workspace, db: Any) -> None:
    sql_file = workspace.output_dir / "DB_CHANGES.sql"
    if not sql_file.exists():
        return
    sql = sql_file.read_text(encoding="utf-8")
    tables = {(schema or "public", name) for schema, name in CREATE_TABLE.findall(sql)}
    columns = {(schema or "public", table, column) for schema, table, column in ADD_COLUMN.findall(sql)}
    if not tables and not columns:
        return
    if db is None or not db.reports:
        report.add(
            "db_not_checked",
            "info",
            "DB_CHANGES.sql",
            "no database connection to check the tables/columns",
            "Run DB_CHANGES.sql on your database if you haven't (it is idempotent).",
        )
        return
    from forge.db.access import AccessLevel
    from forge.db.introspect import introspect

    target_name = next((n for n, r in db.reports.items() if r.level != AccessLevel.NONE), None)
    if target_name is None:
        return
    existing: dict[tuple[str, str], set[str]] = {}
    for schema in {s for s, _ in tables} | {s for s, _, _ in columns}:
        for info in introspect(db.targets[target_name], db.secrets, schema):
            existing[(schema, info.name)] = {c.name for c in info.columns}
    for schema, name in sorted(tables):
        if (schema, name) not in existing:
            report.add(
                "missing_table",
                "error",
                "DB_CHANGES.sql",
                f"table `{schema}.{name}` doesn't exist on the {target_name} database",
                "Run DB_CHANGES.sql on that database (in the order it lists).",
            )
    for schema, table, column in sorted(columns):
        if (schema, table) in existing and column not in existing[(schema, table)]:
            report.add(
                "missing_column",
                "error",
                "DB_CHANGES.sql",
                f"column `{table}.{column}` doesn't exist on the {target_name} database",
                "Run DB_CHANGES.sql on that database (in the order it lists).",
            )


def _text(path: Path) -> str | None:
    if not path.exists() or not path.is_file():
        return None
    data = path.read_bytes()
    file_format = detect_format(data)
    return None if file_format.binary else decode_text(data, file_format)


def _normalise(text: str) -> str:
    return "\n".join(line.rstrip() for line in text.replace("\r\n", "\n").strip().splitlines())
