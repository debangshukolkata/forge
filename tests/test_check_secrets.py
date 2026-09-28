"""The leak scanner itself (D-016) and a scan of the real repo."""

from __future__ import annotations

import importlib.util
from pathlib import Path
from types import ModuleType

from tests.conftest import REPO_ROOT


def load_scanner() -> ModuleType:
    spec = importlib.util.spec_from_file_location("check_secrets", REPO_ROOT / "scripts" / "check_secrets.py")
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_finds_env_value_without_printing_it(tmp_path: Path) -> None:
    scanner = load_scanner()
    env_file = tmp_path / ".env"
    env_file.write_text("MY_API_KEY=canary-0123456789abcdef\nDEBUG=true\n", encoding="utf-8")
    leaked = tmp_path / "log.txt"
    leaked.write_text("request sent with canary-0123456789abcdef\n", encoding="utf-8")

    findings = scanner.find_leaks([tmp_path], env_file)

    assert findings == [f"{leaked}:1: value of MY_API_KEY"]
    assert "canary" not in findings[0]


def test_finds_password_inside_connection_url(tmp_path: Path) -> None:
    scanner = load_scanner()
    env_file = tmp_path / ".env"
    url = "postgresql://u:" + "hunter2hunter2" + "@db:5432/x"
    env_file.write_text(f"DEV_PG_URL={url}\n", encoding="utf-8")
    (tmp_path / "notes.md").write_text("the password is hunter2hunter2\n", encoding="utf-8")

    findings = scanner.find_leaks([tmp_path], env_file)

    assert any("DEV_PG_URL (password)" in finding for finding in findings)


def test_detects_jwt_shape(tmp_path: Path) -> None:
    scanner = load_scanner()
    # Assembled at runtime so this source file does not itself contain a JWT-shaped string.
    token = ".".join(["eyJhbGciOiJIUzI1NiJ9", "eyJzdWIiOiJ1c2VyMTIzNCJ9", "c2lnbmF0dXJlLXZhbHVlLXg"])
    (tmp_path / "a.txt").write_text(token, encoding="utf-8")

    assert scanner.find_leaks([tmp_path], tmp_path / ".env") == [f"{tmp_path / 'a.txt'}:1: jwt"]


def test_placeholder_passwords_are_ignored(tmp_path: Path) -> None:
    scanner = load_scanner()
    (tmp_path / "example.txt").write_text("postgresql://postgres:<password>@localhost/db\n", encoding="utf-8")

    assert scanner.find_leaks([tmp_path], tmp_path / ".env") == []


def test_repository_has_no_leaked_secrets() -> None:
    scanner = load_scanner()

    assert scanner.find_leaks([REPO_ROOT], REPO_ROOT / ".env") == []
