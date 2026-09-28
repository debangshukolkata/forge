"""Mode B deliverable (spec §6A.6, §6A.7): output/ with the project files at host-relative paths plus
INTEGRATION_GUIDE.md, INTERFACE_CONTRACT.md, ASSUMPTIONS.md and REVISION_NOTES.md. Every export is a new
revision: the previous output/ is archived to .forge/revisions/r<N>/, and REVISION_NOTES lists exactly what
to re-copy. The agent maintains INTERFACE_CONTRACT and INTEGRATION_NOTES (registrations, config keys) in
.forge/modeb/ with the modeb_document tool."""

from __future__ import annotations

import hashlib
import json
import re
import shutil
from pathlib import Path

from forge.modeb.assumptions import AssumptionRegister
from forge.modeb.contract_scan import contract_with_host_symbols, host_symbols_used
from forge.safety.paths import os_path
from forge.workspace.output import OutputManifest, build_db_changes, compute_changes
from forge.workspace.workspace import Workspace

DOCUMENT_NAMES = ("INTERFACE_CONTRACT", "INTEGRATION_NOTES")
MODEB_DOCS = {
    "INTEGRATION_GUIDE.md",
    "INTERFACE_CONTRACT.md",
    "ASSUMPTIONS.md",
    "REVISION_NOTES.md",
    "MANIFEST.json",
    "DB_CHANGES.sql",
}


def documents_dir(workspace: Workspace) -> Path:
    return workspace.forge_dir / "modeb"


def read_document(workspace: Workspace, name: str) -> str:
    path = documents_dir(workspace) / f"{name}.md"
    return path.read_text(encoding="utf-8") if path.exists() else ""


def write_document(workspace: Workspace, name: str, markdown: str) -> None:
    if name not in DOCUMENT_NAMES:
        raise ValueError(f"document must be one of {', '.join(DOCUMENT_NAMES)}")
    path = workspace.jail.check(documents_dir(workspace) / f"{name}.md")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(markdown.strip() + "\n", encoding="utf-8")


def current_revision(workspace: Workspace) -> int:
    path = workspace.forge_dir / "revision.json"
    return int(json.loads(path.read_text(encoding="utf-8"))["revision"]) if path.exists() else 0


def build_modeb_output(workspace: Workspace) -> OutputManifest:
    previous = current_revision(workspace)
    previous_hashes = _archive(workspace, previous) if previous else {}
    revision = previous + 1
    for child in list(workspace.output_dir.iterdir()):
        target = workspace.jail.check(child)
        shutil.rmtree(target) if target.is_dir() else target.unlink()
    everything = [c for c in compute_changes(workspace) if c.status != "deleted" and not c.secret]
    # Files that already exist in the host (per its structure export) were written without seeing the
    # host's version: delivering them would overwrite the host's code. They become merge instructions.
    existing = host_paths(workspace)
    merges = [c.path for c in everything if c.path in existing]
    changes = [c for c in everything if c.path not in existing]
    for change in changes:
        target = workspace.jail.check(workspace.output_dir / change.path)
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(os_path(workspace.repo_dir / change.path), os_path(target))
    for path in merges:
        target = workspace.jail.check(workspace.output_dir / "_merge" / f"{path}.proposed")
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(os_path(workspace.repo_dir / path), os_path(target))
    manifest = OutputManifest.model_validate(
        {
            "generated": "",
            "repository": f"host (Mode B, revision {revision})",
            "files": [c.model_dump() for c in changes],
        }
    )
    _write(workspace, "MANIFEST.json", manifest.model_dump_json(indent=1))
    db_changes = build_db_changes(workspace, changes)
    if db_changes:
        _write(workspace, "DB_CHANGES.sql", db_changes)
    symbols = host_symbols_used(workspace, [c.path for c in changes])
    contract = contract_with_host_symbols(read_document(workspace, "INTERFACE_CONTRACT"), symbols)
    _write(workspace, "INTERFACE_CONTRACT.md", contract)
    _write(workspace, "ASSUMPTIONS.md", AssumptionRegister(workspace).markdown())
    _write(
        workspace,
        "INTEGRATION_GUIDE.md",
        integration_guide(workspace, [c.path for c in changes], bool(db_changes), merges),
    )
    current_hashes = {c.path: _hash(workspace.output_dir / c.path) for c in changes}
    _write(workspace, "REVISION_NOTES.md", revision_notes(revision, previous_hashes, current_hashes))
    workspace.jail.check(workspace.forge_dir / "revision.json").write_text(
        json.dumps({"revision": revision}), encoding="utf-8"
    )
    return manifest


def host_paths(workspace: Workspace) -> set[str]:
    """Host-relative paths the host already has (the profile's structure export tree)."""
    from forge.config import forge_home
    from forge.modeb.profile import ProfileError, ProfileStore
    from forge.modeb.workspace import profile_ref

    try:
        profile = ProfileStore(forge_home()).open(str(profile_ref(workspace).get("profile")))
    except ProfileError:
        return set()
    tree: list[str] = profile.structure().get("tree", [])
    return set(tree)


def integration_guide(
    workspace: Workspace, files: list[str], has_sql: bool, merges: list[str] | None = None
) -> str:
    notes = read_document(workspace, "INTEGRATION_NOTES")
    contract = read_document(workspace, "INTERFACE_CONTRACT")
    tests = [f for f in files if Path(f).name.startswith("test_")]
    contract_tests = [f for f in tests if "contract" in Path(f).name]
    feature_tests = [f for f in tests if f not in contract_tests]
    contract_list, feature_list = " ".join(contract_tests), " ".join(feature_tests)
    assumptions = AssumptionRegister(workspace).all()
    lines = [
        f"# Integration guide — {workspace.info.name}",
        "",
        "Every path below is relative to the host repository root and matches output/ exactly.",
        "",
        f"## 1. Files to add ({len(files)})",
        "",
        *[f"- [ ] copy `output/{f}` to `{f}`" for f in files],
        "",
        "## 2. Adapter functions to wire",
        "",
        "See INTERFACE_CONTRACT.md: each host symbol the code uses, with its expected signature/behaviour"
        + (
            " and a suggested implementation for every `_host_adapter` function."
            if "_host_adapter" in contract
            else "."
        ),
        "",
        "## 3. Registrations (blueprints, graph wiring, config keys)",
        "",
        *_unrecorded_registrations(workspace, files, notes),
        notes.strip() or "None recorded.",
        "",
        *(
            [
                "**These host files already exist, so they are NOT delivered as files** (Forge never saw "
                "your version). Merge only the new lines from the proposed version into yours:",
                "",
                *[
                    f"- [ ] `{path}` — proposed version: `output/_merge/{path}.proposed`"
                    for path in merges or []
                ],
                "",
            ]
            if merges
            else []
        ),
        "## 4. Dependencies and SQL scripts, in order",
        "",
        (
            "- Run DB_CHANGES.sql (it lists the scripts in order; each is idempotent)."
            if has_sql
            else "- No SQL."
        ),
        "- New packages, if any, are listed in NEW_DEPENDENCIES in the notes above.",
        "",
        "## 5. Assumptions to verify",
        "",
        *(
            [f"- [ ] {a.id}: {a.text} — `{a.check}`" for a in assumptions if a.status != "confirmed"]
            or ["None."]
        ),
        "",
        "## 6. Run the delivered tests inside the host",
        "",
        *(
            [f"- Contract tests (check the assumptions fast): `python -m pytest -q {contract_list}`"]
            if contract_tests
            else []
        ),
        *([f"- Feature tests: `python -m pytest -q {feature_list}`"] if feature_tests else []),
        *([] if tests else ["- No test files delivered."]),
        "",
        "## 7. If something fails, paste back to Forge",
        "",
        "- the traceback or failing test output (whole error, not just the last line);",
        "- the specific file or section Forge asks for — and nothing more.",
        "- **Never paste secrets, .env contents or customer data.**",
        "",
    ]
    return "\n".join(lines)


_ROUTER = re.compile(r"^(\w+)\s*=\s*(Blueprint|APIRouter)\(", re.MULTILINE)


def _unrecorded_registrations(workspace: Workspace, files: list[str], notes: str) -> list[str]:
    """New blueprints/routers the host must register that INTEGRATION_NOTES doesn't mention — a delivered
    route nobody registers is a 404 in the host (seen live), so this is never left to the model alone."""
    lines = []
    for relative in files:
        if not relative.endswith(".py") or Path(relative).name.startswith("test_"):
            continue
        source = (workspace.output_dir / relative).read_text(encoding="utf-8", errors="replace")
        module = relative.removesuffix(".py").replace("/", ".")
        for name, kind in _ROUTER.findall(source):
            if module in notes:
                continue
            call = "register_blueprint" if kind == "Blueprint" else "include_router"
            lines.append(
                f"- [ ] register the new {kind} `{name}` from `{module}` where the host registers the others "
                f"(`from {module} import {name}`, then `{call}(...)` in the host's own style)"
            )
    return [*lines, ""] if lines else []


def revision_notes(revision: int, previous: dict[str, str], current: dict[str, str]) -> str:
    if not previous:
        return f"# Revision {revision}\n\nFirst delivery: copy everything listed in INTEGRATION_GUIDE.md.\n"
    added = sorted(set(current) - set(previous))
    changed = sorted(p for p in set(current) & set(previous) if current[p] != previous[p])
    removed = sorted(set(previous) - set(current))
    lines = [
        f"# Revision {revision} (previous: {revision - 1})",
        "",
        "Re-copy only these; everything else is unchanged since the last revision.",
        "",
    ]
    lines += [f"- added: `{p}`" for p in added] + [f"- changed: `{p}`" for p in changed]
    lines += [f"- removed (delete it from the host): `{p}`" for p in removed]
    if not (added or changed or removed):
        lines.append("- No code changed; only the documents (assumptions/guide) may differ.")
    return "\n".join(lines) + "\n"


def _archive(workspace: Workspace, revision: int) -> dict[str, str]:
    archive = workspace.jail.check(workspace.forge_dir / "revisions" / f"r{revision}")
    if archive.exists():
        shutil.rmtree(archive)
    shutil.copytree(os_path(workspace.output_dir), os_path(archive))
    hashes = {}
    for file in archive.rglob("*"):
        relative = file.relative_to(archive).as_posix()
        if file.is_file() and relative not in MODEB_DOCS:
            hashes[relative] = _hash(file)
    return hashes


def _hash(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _write(workspace: Workspace, name: str, text: str) -> None:
    workspace.jail.check(workspace.output_dir / name).write_text(text, encoding="utf-8")
