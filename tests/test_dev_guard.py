"""The copy's own settings that point at the shared development database are held back (DV10, D-613)."""

from __future__ import annotations

import asyncio
import threading
from pathlib import Path

import httpx2
import psycopg
import pytest

from forge.config import PostgresConfig, Secrets
from forge.db.dev_guard import Refuser, dev_settings
from forge.db.session import DbSession
from forge.engine.session_host import SessionHost
from forge.protocol.events import EventBus
from forge.safety.redact import Redactor
from forge.workspace.create import create_workspace
from tests.helpers import mocked_router

DEV_URL = (
    "postgresql://dev_user:dev-pass-123@localhost:9006/wisdom_dev?sslmode=require"  # check_secrets: fake
)


APP_URL = "postgresql://app:app-pw@localhost:9006/wisdom_dev"  # check_secrets: fake
SAMPLE_URL = "postgresql://x:y@localhost:9006/wisdom_dev"  # check_secrets: fake


def _write(folder: Path, name: str, text: str) -> None:
    folder.mkdir(parents=True, exist_ok=True)
    (folder / name).write_text(text, encoding="utf-8")


def test_settings_holding_the_development_address_are_found_by_value_not_by_name(tmp_path: Path) -> None:
    app = tmp_path / "repo" / "backend"
    _write(
        tmp_path / "repo",
        ".env",
        "DATABASE_URL=postgresql+psycopg2://app:app-pw@127.0.0.1:9006/wisdom_dev\n"  # check_secrets: fake
        "CACHE_URL=redis://localhost:9006/0\n"
        "OTHER_DB=postgresql://app:pw@localhost:9006/another_db\n"  # check_secrets: fake
        "LOCAL_DB=postgresql://app:pw@localhost:5432/wisdom_dev\n"  # check_secrets: fake
        "API_HOST=localhost\n",
    )
    _write(
        app, "local.env", "PG_HOST=localhost\nPG_PORT=9006\nPG_NAME=wisdom_dev\nPG_USER=app\nAPP_PORT=8000\n"
    )
    _write(app, ".env.example", f"DATABASE_URL={SAMPLE_URL}\n")
    _write(app, "notes.txt", f"DATABASE_URL={SAMPLE_URL}\n")

    held = dev_settings([tmp_path / "repo", app], DEV_URL)
    assert held.kinds == {"DATABASE_URL": "url", "PG_HOST": "host", "PG_PORT": "port"}
    assert sorted(held.files) == [".env", "local.env"]
    values = held.values(41234)
    assert values["PG_HOST"] == "127.0.0.1" and values["PG_PORT"] == "41234"
    # scheme, login and database stay, so the driver parses it; only the address changes
    assert values["DATABASE_URL"] == (
        "postgresql+psycopg2://app:app-pw@127.0.0.1:41234/wisdom_dev?sslmode=disable"  # check_secrets: fake
    )

    # a host called localhost with no matching port and database says nothing
    _write(tmp_path / "other", ".env", "DB_HOST=localhost\nDB_PORT=5432\nDB_NAME=shop\n")
    assert dev_settings([tmp_path / "other"], DEV_URL).kinds == {}
    assert dev_settings([tmp_path / "missing"], DEV_URL).kinds == {}


def test_a_connection_with_a_held_back_setting_is_refused_with_what_to_do() -> None:
    """psycopg stands in for the copied application; no database is needed: the listener never passes it on."""
    loop = asyncio.new_event_loop()
    thread = threading.Thread(target=loop.run_forever, daemon=True)
    thread.start()
    refuser = Refuser(["DATABASE_URL", "PG_PORT"])
    try:
        port = asyncio.run_coroutine_threadsafe(refuser.start(), loop).result(timeout=10)
        for options in ("sslmode=disable", "sslmode=prefer"):
            with pytest.raises(psycopg.OperationalError) as refused:
                psycopg.connect(
                    f"host=127.0.0.1 port={port} dbname=wisdom_dev user=app {options}", connect_timeout=10
                )
            text = str(refused.value)
            assert (
                "DATABASE_URL, PG_PORT" in text
                and "use_scratch_database" in text
                and "use_dev_database" in text
            )
        assert refuser.refused == 2
    finally:
        asyncio.run_coroutine_threadsafe(refuser.close(), loop).result(timeout=10)
        loop.call_soon_threadsafe(loop.stop)
        thread.join(timeout=5)


async def test_a_session_holds_the_settings_back_until_the_application_is_pointed_somewhere(
    original_repo: Path, tmp_path: Path
) -> None:
    workspace = create_workspace(original_repo, tmp_path / "ws", "backend")
    _write(
        workspace.app_dir,
        ".env",
        f"APP_DATABASE_URL={APP_URL}\nAPP_PORT=8000\n",
    )
    secrets = Secrets({"DEV_PG_URL": DEV_URL}, None)
    host = SessionHost(
        mocked_router(lambda request: httpx2.Response(500)),
        EventBus(redactor=Redactor()),
        workspace=workspace,
        secrets=secrets,
    )
    try:
        assert host.db is not None and host.agent is not None and host.agent.context.shell is not None
        await host._hold_back_dev_settings(host.db)
        await host._hold_back_dev_settings(host.db)  # a second preparation starts no second listener
        db, shell = host.db, host.agent.context.shell
        shell.extra_env = db.command_environment()
        port = db.dev_refuser.local_port  # type: ignore[union-attr]
        assert (
            shell.extra_env
            == {
                "APP_DATABASE_URL": f"postgresql://app:app-pw@127.0.0.1:{port}/wisdom_dev?sslmode=disable"  # check_secrets: fake
            }
        )
        assert shell.environment()["APP_DATABASE_URL"].endswith(
            f"@127.0.0.1:{port}/wisdom_dev?sslmode=disable"
        )
        assert db.still_held_back() == ["APP_DATABASE_URL"]
        notices = [
            e.payload for e in host.bus.events_since(0) if e.payload.get("kind") == "dev_settings_held"
        ]
        assert len(notices) == 1 and "APP_DATABASE_URL" in notices[0]["text"]
        assert "app-pw" not in notices[0]["text"] and "9006" not in notices[0]["text"]  # names, never values

        db.reports = {"dev": object()}  # type: ignore[dict-item]  # only so the status line is written
        db.reports["dev"] = type("Report", (), {"line": lambda self: "dev: reachable"})()  # type: ignore[assignment]
        assert "HELD BACK" in db.status_line() and "APP_DATABASE_URL" in db.status_line()

        # use_scratch_database (or use_dev_database) for that setting replaces the held-back value
        db.set_app_variables({"APP_DATABASE_URL": "url"})
        assert db.still_held_back() == [] and "HELD BACK" not in db.status_line()
    finally:
        await host.close()


def test_nothing_is_held_back_without_a_development_database(original_repo: Path, tmp_path: Path) -> None:
    workspace = create_workspace(original_repo, tmp_path / "ws", "backend")
    _write(workspace.app_dir, ".env", f"APP_DATABASE_URL={APP_URL}\n")
    db = DbSession(PostgresConfig(), Secrets({"LOCAL_PG_URL": DEV_URL}, None), workspace, tmp_path, [])
    assert (
        db.find_dev_settings().kinds == {} and db.command_environment() == {} and db.still_held_back() == []
    )
