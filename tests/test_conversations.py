"""Conversations of a project: index, migration, paths (D-582; no model involved)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from forge.errors import ConversationError
from forge.workspace.conversations import ConversationStore
from forge.workspace.create import create_workspace


@pytest.fixture
def workspace(original_repo: Path, tmp_path: Path):  # type: ignore[no-untyped-def]
    return create_workspace(original_repo, tmp_path / "ws", "backend", max_file_mb=1)


def _old_log(workspace, text: str = "fix the token limit") -> bytes:  # type: ignore[no-untyped-def]
    log = workspace.forge_dir / "transcripts" / "events.jsonl"
    log.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        json.dumps({"seq": 1, "type": "status_changed", "payload": {"state": "idle"}}),
        json.dumps({"seq": 2, "type": "user_message", "payload": {"text": text}}),
    ]
    log.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return log.read_bytes()


def test_a_project_without_an_index_is_migrated_by_copy(workspace) -> None:  # type: ignore[no-untyped-def]
    old = _old_log(workspace)
    (workspace.forge_dir / "state.json").write_text('{"cadence": "autonomous"}', encoding="utf-8")
    store = ConversationStore(workspace)

    conversation = store.active()
    assert conversation.id == "c1" and conversation.title == "fix the token limit"
    assert store.events_path("c1").read_bytes() == old  # byte for byte
    assert (workspace.forge_dir / "transcripts" / "events.jsonl").read_bytes() == old  # the backup stays
    assert (workspace.forge_dir / "state.json").is_file()
    assert store.state_path("c1").is_file() and store.index_path.is_file()


def test_a_killed_migration_starts_again_cleanly(workspace) -> None:  # type: ignore[no-untyped-def]
    old = _old_log(workspace)
    store = ConversationStore(workspace)
    half = store.events_path("c1")
    half.parent.mkdir(parents=True)
    half.write_bytes(old[:20])  # copy interrupted, no index written
    assert not store.index_path.exists()

    assert store.active().id == "c1"
    assert half.read_bytes() == old


def test_a_project_with_no_log_gets_an_empty_first_conversation(workspace) -> None:  # type: ignore[no-untyped-def]
    store = ConversationStore(workspace)
    assert [c.id for c in store.list()] == ["c1"] and store.active().title == ""


def test_create_activates_the_new_one_and_ids_are_not_reused(workspace) -> None:  # type: ignore[no-untyped-def]
    store = ConversationStore(workspace)
    first = store.active()
    second = store.create("Add retry to the tools")
    third = store.create()

    assert (first.id, second.id, third.id) == ("c1", "c2", "c3")
    assert store.active().id == "c3" and store.folder("c2").is_dir()
    assert store.get("c2").title == "Add retry to the tools"
    assert [c.id for c in store.list()] == ["c1", "c2", "c3"]


def test_the_cadence_is_copied_to_a_new_conversation_but_not_the_tasks(workspace) -> None:  # type: ignore[no-untyped-def]
    store = ConversationStore(workspace)
    store.state_path("c1").parent.mkdir(parents=True, exist_ok=True)
    store.state_path("c1").write_text('{"cadence": "autonomous", "tasks": [{"id": "T1"}]}', encoding="utf-8")
    new = store.create()
    copied = json.loads(store.state_path(new.id).read_text(encoding="utf-8"))
    assert copied == {"cadence": "autonomous"}


def test_activate_rename_touch_and_the_title_of_the_first_message(workspace) -> None:  # type: ignore[no-untyped-def]
    store = ConversationStore(workspace)
    store.create()
    store.activate("c1")
    assert store.active().id == "c1"
    store.set_title_if_empty("c2", "  a very   long " + "x" * 100)
    title = store.get("c2").title
    assert len(title) <= 60 and title.startswith("a very long") and title.endswith("…")
    store.set_title_if_empty("c2", "another")  # a set title is never overwritten
    assert store.get("c2").title == title
    store.rename("c2", "Mine")
    assert store.get("c2").title == "Mine"
    store.touch("c2")
    assert store.get("c2").updated >= store.get("c2").created


@pytest.mark.parametrize("bad", ["../x", "c0", "c", "c1/../c2", "C1", "c1234567", "", "c1 "])
def test_a_bad_conversation_id_is_refused_before_a_path_is_built(workspace, bad: str) -> None:  # type: ignore[no-untyped-def]
    store = ConversationStore(workspace)
    for call in (store.events_path, store.history_path, store.state_path, store.get, store.activate):
        with pytest.raises(ConversationError):
            call(bad)


def test_an_unknown_but_valid_id_raises(workspace) -> None:  # type: ignore[no-untyped-def]
    with pytest.raises(ConversationError):
        ConversationStore(workspace).activate("c9")


def test_a_damaged_index_is_migrated_again_without_losing_the_log(workspace) -> None:  # type: ignore[no-untyped-def]
    old = _old_log(workspace)
    store = ConversationStore(workspace)
    store.active()
    store.index_path.write_text("{not json", encoding="utf-8")
    assert ConversationStore(workspace).active().id == "c1"
    assert store.events_path("c1").read_bytes() == old


def test_readers_find_the_active_conversation_without_changing_anything(workspace) -> None:  # type: ignore[no-untyped-def]
    from forge.workspace.conversations import conversation_file

    root = workspace.root
    assert conversation_file(root, "events.jsonl") == root / ".forge" / "transcripts" / "events.jsonl"
    assert conversation_file(root, "state.json") == root / ".forge" / "state.json"
    assert not (root / ".forge" / "conversations").exists()  # reading migrated nothing

    store = ConversationStore(workspace)
    store.create()
    assert (
        conversation_file(root, "events.jsonl") == root / ".forge" / "conversations" / "c2" / "events.jsonl"
    )
    assert conversation_file(root, "events.jsonl", "c1").parent.name == "c1"
    bad = conversation_file(root, "state.json", "../x")  # an invalid id is never made into a path
    assert bad == root / ".forge" / "state.json" or "x" not in bad.parts
