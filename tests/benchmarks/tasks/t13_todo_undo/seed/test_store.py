from __future__ import annotations

from pathlib import Path

import pytest

from cli import main
from store import TaskStore


def test_add_complete_remove() -> None:
    store = TaskStore()
    first = store.add("  write report ")
    second = store.add("call Ana")
    assert (first.id, second.id, first.title) == (1, 2, "write report")
    store.complete(1)
    assert [t.done for t in store.list()] == [True, False]
    assert [t.id for t in store.list(include_done=False)] == [2]
    store.remove(2)
    assert [t.id for t in store.list()] == [1]


def test_bad_input() -> None:
    store = TaskStore()
    with pytest.raises(ValueError):
        store.add("   ")
    with pytest.raises(KeyError):
        store.complete(7)


def test_file_round_trip(tmp_path: Path) -> None:
    path = tmp_path / "t.json"
    store = TaskStore(path)
    store.add("a")
    store.add("b")
    store.complete(1)
    again = TaskStore(path)
    assert [(t.id, t.title, t.done) for t in again.list()] == [(1, "a", True), (2, "b", False)]
    assert again.add("c").id == 3


def test_cli(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    path = tmp_path / "t.json"
    assert main(["add", "milk"], path) == 0
    assert main(["done", "1"], path) == 0
    assert main(["done", "9"], path) == 1
    assert main(["list", "--all"], path) == 0
    out = capsys.readouterr().out
    assert "Added 1: milk" in out and "1 [x] milk" in out
