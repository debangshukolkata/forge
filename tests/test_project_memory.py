"""D-196: what the project list says Forge remembers about each project. No model calls."""

from __future__ import annotations

import sys
from pathlib import Path

from forge.memory.scope import project_dir, repo_key
from forge.memory.store import STATE_MEMORY, MemoryStore
from forge.modeb.profile import ProfileStore
from forge.modeb.workspace import create_standalone_workspace
from forge.web.project_list import describe_projects
from forge.web.project_memory import LINE_CHARS, _section_line, project_memory

HANDOFF = """## Goal
Mask card numbers in the audit log for the payments team.

## Decisions
- Keep the last four digits.

## Next
1. Add the CSV export of masked rows
2. Write the retrofit notes
"""


def test_section_line_takes_the_first_real_line_without_its_bullet() -> None:
    assert _section_line(HANDOFF, "goal") == "Mask card numbers in the audit log for the payments team."
    assert _section_line(HANDOFF, "next") == "Add the CSV export of masked rows"
    assert _section_line(HANDOFF, "pitfalls") == ""
    long = "## Goal\n" + "word " * 100
    assert len(_section_line(long, "goal")) == LINE_CHARS and _section_line(long, "goal").endswith("…")


def test_a_project_with_nothing_remembered(isolated_forge_home: Path, tmp_path: Path) -> None:
    entry = {"path": str(tmp_path), "repo": str(tmp_path / "repo"), "app_folder": ""}
    assert project_memory(isolated_forge_home, tmp_path, entry, "A") == {
        "memories": 0,
        "instructions": False,
        "state": None,
    }
    # A Standalone workspace whose profile reference is missing is "nothing", never an error.
    assert project_memory(isolated_forge_home, tmp_path, {"repo": "standalone"}, "B")["state"] is None


def test_a_repository_project_reports_its_notes_instructions_and_handoff(
    isolated_forge_home: Path, tmp_path: Path
) -> None:
    repo = tmp_path / "claims-repo"
    repo.mkdir()
    scope = f"repo:{repo_key(repo, 'backend')}"
    store = MemoryStore(isolated_forge_home, scope)
    store.save("prefers-pytest", "Uses pytest", "project", "Run python -m pytest -q.")
    store.save("port", "Dev server port", "reference", "Port 8100.")
    store.save(STATE_MEMORY, "Where the work stands", "project", HANDOFF)
    project_dir(isolated_forge_home, scope).joinpath("FORGE.md").write_text("# Rules\n", encoding="utf-8")

    entry = {"path": str(tmp_path), "repo": str(repo), "app_folder": "backend"}
    memory = project_memory(isolated_forge_home, tmp_path, entry, "A")
    assert memory["memories"] == 2  # the handoff is reported separately
    assert memory["instructions"] is True
    assert memory["state"]["goal"].startswith("Mask card numbers")
    assert memory["state"]["next"] == "Add the CSV export of masked rows"
    assert memory["state"]["saved"].endswith("+00:00")


def test_a_standalone_project_reads_its_profile(isolated_forge_home: Path, tmp_path: Path) -> None:
    profile = ProfileStore(isolated_forge_home).create("acme")
    created = create_standalone_workspace(tmp_path / "ws", profile)
    assert created.info.python_env is not None
    created.info.python_env = created.info.python_env.model_copy(update={"python": sys.executable})
    created.save_info()
    MemoryStore(isolated_forge_home, "profile:acme").save(STATE_MEMORY, "state", "project", HANDOFF)
    (profile.root / "FORGE.md").write_text("# Host rules\n", encoding="utf-8")
    log = created.root / ".forge" / "transcripts"
    log.mkdir(parents=True, exist_ok=True)
    (log / "events.jsonl").write_text("", encoding="utf-8")

    entry = {"path": str(created.root), "name": "ws", "repo": "standalone (Mode B)", "app_folder": None}
    [project] = describe_projects([entry], isolated_forge_home)
    assert project["mode"] == "B"
    assert project["memory"]["instructions"] is True
    assert project["memory"]["state"]["next"] == "Add the CSV export of masked rows"
