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
