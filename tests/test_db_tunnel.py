"""D-605: DebCraft opens the tunnel to the development database itself (a stand-in program plays gcloud)."""

from __future__ import annotations

import socket
import sys
from pathlib import Path

import psycopg
import pytest
import yaml

from forge.db import tunnel
from forge.db.connection import DbTarget, connect
from forge.db.tunnel import TunnelError, ensure_tunnel, load_tunnels, port_open, stop_all
from forge.errors import ConfigError

SERVER = "import socket,sys,time\ns=socket.socket();s.bind(('127.0.0.1',int(sys.argv[1])));s.listen(5);time.sleep(60)\n"
FAILS = "import sys\nprint('Reauthentication failed. Please run: gcloud auth login')\nsys.exit(1)\n"


def free_port() -> int:
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        return int(probe.getsockname()[1])


def describe(home: Path, script: str, port: int, args: list[str] | None = None) -> None:
    program = home / "fake_tunnel.py"
    program.write_text(script, encoding="utf-8")
    command = [sys.executable, str(program), *(args if args is not None else [str(port)])]
    (home / "tunnels.yaml").write_text(
        yaml.safe_dump({"tunnels": {"dev": {"command": command, "port": port}}}), encoding="utf-8"
    )


@pytest.fixture(autouse=True)
def stopped():  # type: ignore[no-untyped-def]
    yield
    stop_all()


def test_no_file_means_nothing_is_done(isolated_forge_home: Path) -> None:
    assert ensure_tunnel("dev") == "" and load_tunnels() == {}


def test_a_bad_file_says_what_is_wrong(isolated_forge_home: Path) -> None:
    (isolated_forge_home / "tunnels.yaml").write_text(
        "tunnels:\n  dev: {command: [], port: 9}\n", encoding="utf-8"
    )
    with pytest.raises(ConfigError, match="command"):
        load_tunnels()


def test_the_tunnel_is_started_when_the_port_is_closed_and_left_alone_when_open(
    isolated_forge_home: Path,
) -> None:
    port = free_port()
    describe(isolated_forge_home, SERVER, port)
    assert not port_open(port)
    assert "started it" in ensure_tunnel("dev") and port_open(port)
    assert ensure_tunnel("dev") == ""  # already open: nothing is done
    assert ensure_tunnel("local") == ""  # no tunnel described for another target
    stop_all()


def test_an_expired_google_login_is_named_and_asks_for_gcloud_auth_login(
    isolated_forge_home: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(tunnel, "START_WAIT_SECONDS", 10)
    describe(isolated_forge_home, FAILS, free_port(), args=[])
    with pytest.raises(TunnelError, match="gcloud auth login"):
        ensure_tunnel("dev")


def test_a_connection_to_the_dev_target_opens_the_tunnel_first_and_reports_a_failure_as_a_connection_error(
    isolated_forge_home: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(tunnel, "START_WAIT_SECONDS", 10)
    describe(isolated_forge_home, FAILS, free_port(), args=[])

    class Secrets:
        def get(self, name: str) -> str:
            return "postgresql://u:p@127.0.0.1:1/db"  # check_secrets: fake

    with pytest.raises(psycopg.OperationalError, match="tunnel to dev"):
        connect(DbTarget("dev", "DEV_PG_URL"), Secrets())  # type: ignore[arg-type]


def test_the_tunnel_command_does_not_get_debcrafts_secrets(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("AZURE_OPENAI_API_KEY", "x")  # check_secrets: fake
    monkeypatch.setenv("DEV_PG_URL", "postgresql://u:p@h/db")  # check_secrets: fake
    monkeypatch.setenv("CLOUDSDK_CONFIG", "keep")
    environment = tunnel._environment()
    assert "AZURE_OPENAI_API_KEY" not in environment and "DEV_PG_URL" not in environment
    assert environment.get("CLOUDSDK_CONFIG") == "keep"
