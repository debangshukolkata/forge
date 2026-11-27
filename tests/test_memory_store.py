"""D-199: FORGE.md lives in the project's memory folder but is the instructions, not a remembered note."""

from __future__ import annotations

from pathlib import Path

from forge.memory.store import INSTRUCTIONS_FILE, MemoryStore, combined_index

SCOPE = "repo:demo-abc123"


def test_forge_md_is_not_listed_as_a_memory(isolated_forge_home: Path) -> None:
    store = MemoryStore(isolated_forge_home, SCOPE)
    store.save("a-note", "A note", "project", "Run python -m pytest -q.")
    (store.folder / INSTRUCTIONS_FILE).write_text("# Repo rules\nUse tabs.\n", encoding="utf-8")

    assert [m.name for m in store.all()] == ["a-note"]
    index = combined_index(isolated_forge_home, SCOPE) or ""
    assert "a-note" in index and "FORGE" not in index and "Repo rules" not in index
    store.save("another", "Another", "project", "More.")  # rewrites MEMORY.md
    assert "FORGE" not in (store.folder / "MEMORY.md").read_text(encoding="utf-8")
    assert (
        (store.folder / INSTRUCTIONS_FILE).read_text(encoding="utf-8").startswith("# Repo rules")
    )  # untouched


async def test_the_state_of_the_work_belongs_to_one_project_not_to_the_repository(
    isolated_forge_home: Path, original_repo: Path, tmp_path: Path
) -> None:
    """D-668 (office, 2026-11-26): a new project made from the same repository was told to carry on another project's
    work 'on Monday'. The repository's notes stay shared; the state of the work is the project's own."""
    from forge.memory.scope import scope_of
    from forge.toolkit.base import ToolContext
    from forge.tools.memory import MemoryRead, MemoryWrite
    from forge.workspace.create import create_workspace

    first = create_workspace(original_repo, tmp_path / "first", "backend")
    second = create_workspace(original_repo, tmp_path / "second", "backend")
    scope = scope_of(first)
    assert scope == scope_of(second)  # the same repository
    write = MemoryWrite()
    await write.run(
        MemoryWrite.Args(name="project-state", description="Paused", text="Re-index on Monday."),
        ToolContext(workspace=first),
    )
    await write.run(
        MemoryWrite.Args(name="run-command", description="How to run", text="flask run"),
        ToolContext(workspace=first),
    )
    own = combined_index(isolated_forge_home, scope, first.root) or ""
    other = combined_index(isolated_forge_home, scope, second.root) or ""
    assert "carry on from there" in own and "run-command" in own
    assert "carry on from there" not in other and "project-state" not in other and "run-command" in other
    read = MemoryRead()
    assert (
        "Monday"
        in (await read.run(MemoryRead.Args(name="project-state"), ToolContext(workspace=first))).content
    )
    assert not (await read.run(MemoryRead.Args(name="project-state"), ToolContext(workspace=second))).ok


def test_a_shared_state_note_from_before_goes_to_the_project_that_wrote_it(
    isolated_forge_home: Path, tmp_path: Path
) -> None:
    import os
    import time

    from forge.memory.store import STATE_MEMORY, adopt_shared_state

    writer, newcomer = tmp_path / "writer", tmp_path / "newcomer"
    for project in (writer, newcomer):
        (project / ".forge" / "conversations" / "c1").mkdir(parents=True)
        (project / ".forge" / "conversations" / "c1" / "events.jsonl").write_text("{}\n", encoding="utf-8")
    shared = MemoryStore(isolated_forge_home, SCOPE)
    shared.save(STATE_MEMORY, "Paused", "project", "Monday.")
    now = time.time()
    os.utime(shared.folder / f"{STATE_MEMORY}.md", (now - 3600, now - 3600))
    os.utime(writer / ".forge" / "conversations" / "c1" / "events.jsonl", (now - 3590, now - 3590))

    adopt_shared_state(isolated_forge_home, SCOPE, newcomer, [writer, newcomer])
    assert (shared.folder / f"{STATE_MEMORY}.md").exists()  # the newcomer does not take it
    assert "carry on" not in (combined_index(isolated_forge_home, SCOPE, newcomer) or "")
    adopt_shared_state(isolated_forge_home, SCOPE, writer, [writer, newcomer])
    assert not (shared.folder / f"{STATE_MEMORY}.md").exists()
    assert "carry on from there" in (combined_index(isolated_forge_home, SCOPE, writer) or "")

    shared.save(STATE_MEMORY, "Paused", "project", "Old.")  # nobody was at work when this one was saved
    os.utime(shared.folder / f"{STATE_MEMORY}.md", (now - 90_000, now - 90_000))
    adopt_shared_state(isolated_forge_home, SCOPE, newcomer, [newcomer])
    assert (shared.folder / f"{STATE_MEMORY}.md").exists()
