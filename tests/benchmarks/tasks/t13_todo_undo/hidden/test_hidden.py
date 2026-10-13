from __future__ import annotations

import json
from pathlib import Path

import pytest

from cli import main
from store import TaskStore


def titles(store: TaskStore) -> list[str]:
    return [t.title for t in store.list()]


def test_undo_and_redo_an_add() -> None:
    store = TaskStore()
    store.add("a")
    store.add("b")
    assert store.undo() is True
    assert titles(store) == ["a"]
    assert store.redo() is True
    assert titles(store) == ["a", "b"]


def test_nothing_to_undo_or_redo_returns_false_and_changes_nothing() -> None:
    store = TaskStore()
    assert store.undo() is False and store.redo() is False
    store.add("a")
    assert store.redo() is False
    assert titles(store) == ["a"]


def test_undo_restores_the_id_counter() -> None:
    store = TaskStore()
    store.add("a")
    store.add("b")
    store.undo()
    assert store.add("c").id == 2  # the id of the undone task is reused


def test_redo_brings_back_the_same_ids() -> None:
    store = TaskStore()
    store.add("a")
    store.add("b")
    store.undo()
    store.redo()
    assert [(t.id, t.title) for t in store.list()] == [(1, "a"), (2, "b")]
    assert store.add("c").id == 3


def test_complete_and_remove_can_be_undone() -> None:
    store = TaskStore()
    store.add("a")
    store.add("b")
    store.complete(1)
    store.remove(2)
    assert [t.id for t in store.list()] == [1]
    store.undo()
    assert [t.id for t in store.list()] == [1, 2]
    store.undo()
    assert [t.done for t in store.list()] == [False, False]


def test_many_undos_walk_back_to_empty() -> None:
    store = TaskStore()
    for name in "abc":
        store.add(name)
    while store.undo():
        pass
    assert store.list() == []
    assert store.add("x").id == 1


def test_a_new_step_clears_redo() -> None:
    store = TaskStore()
    store.add("a")
    store.add("b")
    store.undo()
    store.add("c")
    assert store.redo() is False
    assert titles(store) == ["a", "c"]


def test_failed_calls_are_not_steps() -> None:
    store = TaskStore()
    store.add("a")
    with pytest.raises(ValueError):
        store.add("  ")
    with pytest.raises(KeyError):
        store.complete(9)
    with pytest.raises(KeyError):
        store.remove(9)
    assert store.undo() is True  # reverts the add, not a failed call
    assert store.undo() is False


def test_completing_a_done_task_is_not_a_step() -> None:
    store = TaskStore()
    store.add("a")
    store.complete(1)
    store.complete(1)
    store.undo()  # reverts the first complete
    assert store.list()[0].done is False
    store.undo()  # reverts the add
    assert store.list() == []


def test_a_failed_call_does_not_clear_redo() -> None:
    store = TaskStore()
    store.add("a")
    store.undo()
    with pytest.raises(KeyError):
        store.complete(5)
    assert store.redo() is True


def test_history_is_limited_to_20_steps() -> None:
    store = TaskStore()
    for i in range(25):
        store.add(f"t{i}")
    undone = 0
    while store.undo():
        undone += 1
    assert undone == 20
    assert len(store.list()) == 5


def test_history_survives_a_restart(tmp_path: Path) -> None:
    path = tmp_path / "t.json"
    store = TaskStore(path)
    store.add("a")
    store.add("b")
    store.complete(1)
    store.undo()
    again = TaskStore(path)
    assert [t.done for t in again.list()] == [False, False]
    assert again.redo() is True and again.list()[0].done is True
    assert again.undo() and again.undo() and again.undo()
    assert again.list() == []
    assert again.undo() is False


def test_the_file_format_keeps_its_old_keys_and_adds_history(tmp_path: Path) -> None:
    path = tmp_path / "t.json"
    store = TaskStore(path)
    store.add("a")
    data = json.loads(path.read_text(encoding="utf-8"))
    assert data["next_id"] == 2
    assert data["tasks"] == [{"id": 1, "title": "a", "done": False}]
    assert set(data["history"]) == {"undo", "redo"} and len(data["history"]["undo"]) == 1


def test_an_old_file_without_history_loads(tmp_path: Path) -> None:
    path = tmp_path / "old.json"
    path.write_text(json.dumps({"next_id": 3, "tasks": [{"id": 1, "title": "x", "done": True}, {"id": 2, "title": "y", "done": False}]}), encoding="utf-8")
    store = TaskStore(path)
    assert [t.title for t in store.list()] == ["x", "y"]
    assert store.undo() is False and store.redo() is False
    assert store.add("z").id == 3
    assert store.undo() is True and titles(store) == ["x", "y"]


def test_a_history_larger_than_the_limit_in_a_file_is_trimmed(tmp_path: Path) -> None:
    path = tmp_path / "t.json"
    store = TaskStore(path)
    for i in range(10):
        store.add(f"t{i}")
    data = json.loads(path.read_text(encoding="utf-8"))
    data["history"]["undo"] = data["history"]["undo"] * 5
    path.write_text(json.dumps(data), encoding="utf-8")
    again = TaskStore(path)
    count = 0
    while again.undo():
        count += 1
    assert count <= 20


def test_cli_undo_and_redo(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    path = tmp_path / "t.json"
    assert main(["undo"], path) == 0
    assert capsys.readouterr().out.strip() == "Nothing to undo."
    main(["add", "milk"], path)
    main(["add", "eggs"], path)
    capsys.readouterr()
    assert main(["undo"], path) == 0
    assert capsys.readouterr().out.strip() == "Undone."
    main(["list", "--all"], path)
    assert capsys.readouterr().out.strip() == "1 [ ] milk"
    assert main(["redo"], path) == 0
    assert capsys.readouterr().out.strip() == "Redone."
    assert main(["redo"], path) == 0
    assert capsys.readouterr().out.strip() == "Nothing to redo."
    main(["list"], path)
    assert capsys.readouterr().out.strip().splitlines() == ["1 [ ] milk", "2 [ ] eggs"]
