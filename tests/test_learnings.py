from __future__ import annotations

from pathlib import Path

import pytest

from forge.memory.scope import project_dir
from forge.memory.store import MemoryStore
from forge.modeb.profile import ProfileStore
from forge.web.learnings import LearningsError, delete_learnings, list_learnings


def _setup(home: Path, tmp_path: Path) -> list[dict[str, str | None]]:
    profile = ProfileStore(home).create("acme")
    root = tmp_path / "ws"
    (root / ".forge").mkdir(parents=True)
    (root / ".forge" / "workspace.json").write_text("{}", encoding="utf-8")
    (root / ".forge" / "host_profile_ref.json").write_text('{"profile": "acme"}', encoding="utf-8")
    store = MemoryStore(home, "profile:acme")
    store.save("uses-pytest", "Uses pytest", "project", "Run pytest.")
    store.save("other-note", "Other", "project", "Something else.")
    MemoryStore(home).save("likes-short", "Short replies", "user", "Keep it short.")
    MemoryStore(home, "repo:gone-1234567890").save("orphan", "Left behind", "project", "From a deleted one.")
    (profile.root / "FORGE.md").write_text("# Rules\n", encoding="utf-8")
    assert project_dir(home, "profile:acme").is_dir()
    return [{"path": str(root), "name": "Acme", "repo": "standalone (Mode B)", "app_folder": None}]


def test_groups_by_project_with_user_and_leftover(tmp_path: Path) -> None:
    home = tmp_path / "home"
    recent = _setup(home, tmp_path)
    groups = {g["title"]: g for g in list_learnings(home, recent)}
    assert set(groups) == {"Your preferences", "Acme", "No project (left behind)"}
    assert {i["title"] for i in groups["Acme"]["items"]} == {
        "Host profile",
        "FORGE.md",
        "uses-pytest",
        "other-note",
    }


def test_delete_only_what_was_picked(tmp_path: Path) -> None:
    home = tmp_path / "home"
    recent = _setup(home, tmp_path)
    acme = next(g for g in list_learnings(home, recent) if g["title"] == "Acme")
    assert delete_learnings(home, recent, {acme["id"]: ["note:uses-pytest", "instructions"]}) == 2
    left = next(g for g in list_learnings(home, recent) if g["title"] == "Acme")
    assert [i["title"] for i in left["items"]] == ["Host profile", "other-note"]
    assert MemoryStore(home).get("likes-short") is not None


def test_unknown_group_is_refused(tmp_path: Path) -> None:
    home = tmp_path / "home"
    recent = _setup(home, tmp_path)
    with pytest.raises(LearningsError):
        delete_learnings(home, recent, {"..": ["note:x"]})


def test_forgetting_the_host_profile_removes_its_folder(tmp_path: Path) -> None:
    home = tmp_path / "home"
    recent = _setup(home, tmp_path)
    acme = next(g for g in list_learnings(home, recent) if g["title"] == "Acme")
    assert delete_learnings(home, recent, {acme["id"]: ["profile"]}) == 1
    assert not (home / "profiles" / "acme").exists()
    left = next(g for g in list_learnings(home, recent) if g["title"] == "Acme")
    assert {i["title"] for i in left["items"]} == {"uses-pytest", "other-note"}
