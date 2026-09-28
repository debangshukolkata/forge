"""Builds and incrementally refreshes a repository's Knowledge Base (spec §11.3-11.4)."""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path

from forge.kb import docs
from forge.kb.facts import RepoFacts, collect_facts
from forge.kb.narrative import DocWriter, top_conventions, write_architecture, write_conventions, write_module
from forge.kb.store import doc_path, is_pinned, load_manifest, save_manifest, write_doc, write_index

MAJOR_CHANGE_SHARE = 0.25  # at or above this share of changed Python files, global narratives are rewritten
PARALLEL_LLM_CALLS = 4
Progress = Callable[[str], None]


@dataclass
class FileChanges:
    added: list[str] = field(default_factory=list)
    modified: list[str] = field(default_factory=list)
    deleted: list[str] = field(default_factory=list)

    @property
    def all(self) -> list[str]:
        return sorted(self.added + self.modified + self.deleted)


@dataclass
class BuildReport:
    changes: FileChanges
    docs_written: list[str] = field(default_factory=list)
    docs_kept_pinned: list[str] = field(default_factory=list)
    llm_documents: list[str] = field(default_factory=list)
    full: bool = False


def diff_hashes(old: dict[str, str], new: dict[str, str]) -> FileChanges:
    return FileChanges(
        added=sorted(set(new) - set(old)),
        modified=sorted(p for p in set(new) & set(old) if new[p] != old[p]),
        deleted=sorted(set(old) - set(new)),
    )


def status(repo_path: Path, app_subfolder: str, kb_dir: Path) -> FileChanges | None:
    """Files changed in the repository since the KB was built; None if there is no KB yet."""
    manifest = load_manifest(kb_dir)
    if manifest is None:
        return None
    return diff_hashes(manifest.file_hashes, collect_facts(repo_path, app_subfolder).file_hashes)


async def build(
    repo_path: Path,
    app_subfolder: str,
    kb_dir: Path,
    writer: DocWriter,
    *,
    full: bool = False,
    on_progress: Progress | None = None,
) -> BuildReport:
    say = on_progress or (lambda message: None)
    kb_dir.mkdir(parents=True, exist_ok=True)
    say("Reading the code…")
    facts = collect_facts(repo_path, app_subfolder)
    previous = None if full else load_manifest(kb_dir)
    changes = diff_hashes(previous.file_hashes if previous else {}, facts.file_hashes)
    report = BuildReport(changes=changes, full=previous is None)

    _write(kb_dir, report, "STACK", docs.stack_md(facts))
    _write(kb_dir, report, "COMMANDS", docs.commands_md(facts))
    _write(kb_dir, report, "API_CATALOG", docs.api_catalog_md(facts))
    _write(kb_dir, report, "DB_SCHEMA", docs.db_schema_md(facts))
    _write(kb_dir, report, "LLM_GRAPHS", docs.llm_graphs_md(facts))

    packages = facts.packages()
    changed_py = [p for p in changes.all if p.endswith(".py")]
    if previous is None:
        to_describe = list(packages)
    else:
        affected = {facts.package_of(path) for path in changes.added + changes.modified}
        affected |= {pkg for pkg, files in previous.packages.items() if set(files) & set(changes.deleted)}
        to_describe = sorted(pkg for pkg in affected if pkg in packages)
    for removed in set(previous.packages if previous else {}) - set(packages):
        doc_path(kb_dir, f"modules/{removed}").unlink(missing_ok=True)

    python_files = max(1, len([p for p in facts.file_hashes if p.endswith(".py")]))
    rewrite_globals = previous is None or len(changed_py) / python_files >= MAJOR_CHANGE_SHARE
    say(
        f"Writing {len(to_describe)} package doc(s)"
        + (" and the architecture/conventions docs…" if rewrite_globals else "…")
    )
    await _write_narratives(kb_dir, facts, writer, report, to_describe, rewrite_globals)
    if not rewrite_globals and changes.all:
        _patch_recent_changes(kb_dir, changes)

    conventions = doc_path(kb_dir, "CONVENTIONS")
    top = top_conventions(conventions.read_text(encoding="utf-8")) if conventions.exists() else None
    (kb_dir / "ESSENTIALS.md").write_text(docs.essentials(facts, top), encoding="utf-8")
    write_index(kb_dir, facts)
    narrative = sorted({*(previous.narrative_docs if previous else []), *report.llm_documents})
    save_manifest(kb_dir, facts, narrative)
    say("Knowledge base ready.")
    return report


async def _write_narratives(
    kb_dir: Path,
    facts: RepoFacts,
    writer: DocWriter,
    report: BuildReport,
    packages: list[str],
    rewrite_globals: bool,
) -> None:
    limit = asyncio.Semaphore(PARALLEL_LLM_CALLS)
    grouped = facts.packages()

    async def module(package: str) -> None:
        if _pinned(kb_dir, f"modules/{package}"):
            report.docs_kept_pinned.append(f"modules/{package}")
            return
        async with limit:
            text = await write_module(package, grouped[package], writer)
        _write(kb_dir, report, f"modules/{package}", text)
        report.llm_documents.append(f"modules/{package}")

    async def global_doc(name: str) -> None:
        if _pinned(kb_dir, name):
            report.docs_kept_pinned.append(name)
            return
        async with limit:
            text = await (
                write_architecture(facts, writer)
                if name == "ARCHITECTURE"
                else write_conventions(facts, writer)
            )
        _write(kb_dir, report, name, text)
        report.llm_documents.append(name)

    jobs = [module(package) for package in packages]
    if rewrite_globals:
        jobs += [global_doc("ARCHITECTURE"), global_doc("CONVENTIONS")]
    await asyncio.gather(*jobs)


def _write(kb_dir: Path, report: BuildReport, name: str, text: str) -> None:
    if write_doc(kb_dir, name, text):
        report.docs_written.append(name)
    else:
        report.docs_kept_pinned.append(name)


def _pinned(kb_dir: Path, name: str) -> bool:
    path = doc_path(kb_dir, name)
    return path.exists() and is_pinned(path.read_text(encoding="utf-8"))


def _patch_recent_changes(kb_dir: Path, changes: FileChanges) -> None:
    """Small refreshes patch the global narratives instead of rewriting them (spec §11.4)."""
    note = (
        "\n\n## Recent changes (not yet reflected above)\n"
        + "\n".join(
            [f"- added {p}" for p in changes.added]
            + [f"- modified {p}" for p in changes.modified]
            + [f"- deleted {p}" for p in changes.deleted]
        )
        + "\n"
    )
    for name in ("ARCHITECTURE", "CONVENTIONS"):
        path = doc_path(kb_dir, name)
        if path.exists() and not is_pinned(text := path.read_text(encoding="utf-8")):
            base = text.split("\n\n## Recent changes (not yet reflected above)")[0]
            path.write_text(base + note, encoding="utf-8")
