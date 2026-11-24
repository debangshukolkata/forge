"""D-646: the tidy DebCraft Home: found in both places, moved once, never overwritten, nothing lost half way."""

from __future__ import annotations

import os
import time
from pathlib import Path

import pytest

from forge import home_layout
from forge.home_layout import README, data_path, tidy
from forge.toolkit.app_logins import TokenStore
from forge.web.accounts import AccountStore
from tests.test_app_logins import jwt


def old_home(tmp_path: Path) -> Path:
    home = tmp_path / "home"
    (home / "profiles" / "acme").mkdir(parents=True)
    (home / "profiles" / "acme" / "profile.json").write_text("{}", encoding="utf-8")
    (home / "learning").mkdir()
    for name in (".env", "app.env", "app_logins.yaml", "tunnels.yaml", "config.yaml", "settings.json"):
        (home / name).write_text("mine", encoding="utf-8")
    for name in ("account.json", "tokens.json", "environment.json", "tunnel_dev.log"):
        (home / name).write_text("{}", encoding="utf-8")
    return home


def test_the_users_files_stay_and_debcrafts_own_move(tmp_path: Path) -> None:
    home = old_home(tmp_path)
    moved = tidy(home)
    assert {
        "account.json",
        "tokens.json",
        "environment.json",
        "profiles",
        "learning",
        "tunnel_dev.log",
    } == set(moved)
    assert {p.name for p in home.iterdir()} == {
        ".env", "app.env", "app_logins.yaml", "tunnels.yaml", "config.yaml", "settings.json", "data", "logs", README,
    }  # fmt: skip
    assert (home / "data" / "profiles" / "acme" / "profile.json").is_file()
    assert (home / "data" / "old" / "learning").is_dir() and (home / "logs" / "tunnel_dev.log").is_file()
    assert tidy(home) == []  # a second start has nothing to do


def test_everything_is_found_before_and_after_the_move(tmp_path: Path) -> None:
    home = old_home(tmp_path)
    (home / "tokens.json").unlink()
    (home / "account.json").unlink()
    assert data_path(home, "environment.json") == home / "environment.json"
    assert data_path(home, "tokens.json") == home / "data" / "tokens.json"  # a new one goes to the new place
    token = jwt(exp=time.time() + 900)
    (home / "tokens.json").write_text("{}", encoding="utf-8")
    store = TokenStore(home)
    store.put("DEV_TOKEN", token)
    assert (home / "tokens.json").read_text(encoding="utf-8").count(token) == 1
    tidy(home)
    assert store.get("DEV_TOKEN") == token and TokenStore(home).get("DEV_TOKEN") == token
    assert not (home / "tokens.json").exists()


def test_a_file_in_use_stays_usable_and_moves_later(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    home = old_home(tmp_path)
    rename = os.rename

    def locked(old: Path, new: Path) -> None:
        if Path(old).name == "environment.json":
            raise PermissionError("in use")
        rename(old, new)

    monkeypatch.setattr(home_layout.os, "rename", locked)
    assert "environment.json" not in tidy(home)
    assert data_path(home, "environment.json") == home / "environment.json"
    assert data_path(home, "account.json") == home / "data" / "account.json"
    monkeypatch.setattr(home_layout.os, "rename", rename)
    assert tidy(home) == ["environment.json"]


def test_nothing_is_overwritten_and_an_old_copy_never_comes_back(tmp_path: Path) -> None:
    home = old_home(tmp_path)
    tidy(home)
    (home / "account.json").write_text("from an older version", encoding="utf-8")
    assert tidy(home) == []
    assert (home / "data" / "account.json").read_text(encoding="utf-8") == "{}"
    (home / "data" / "account.json").unlink()  # the user resets the password
    assert data_path(home, "account.json") == home / "data" / "account.json"
    assert not AccountStore(home).configured


def test_a_readme_of_the_users_own_is_left_alone(tmp_path: Path) -> None:
    home = old_home(tmp_path)
    (home / README).write_text("my notes", encoding="utf-8")
    tidy(home)
    assert (home / README).read_text(encoding="utf-8") == "my notes"
    assert tidy(tmp_path / "missing") == []


def test_a_fresh_home_can_be_written_to(tmp_path: Path) -> None:
    """Every state file is saved although `data` does not exist yet (the full test run of 2026-11-24 found two that failed)."""
    from forge.environment import store
    from forge.workspace.read_grants import ReadGrants

    home = tmp_path / "fresh"
    store.save_answer(home, "tesseract", True)
    TokenStore(home).put("DEV_TOKEN", jwt(exp=time.time() + 900))
    (tmp_path / "readable").mkdir()
    ReadGrants.for_workspace(tmp_path, home).grant(str(tmp_path / "readable"))
    assert {"environment.json", "tokens.json", "read_grants"} <= {p.name for p in (home / "data").iterdir()}
