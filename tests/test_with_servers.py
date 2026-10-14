"""D-376: the verifier's server-lifecycle helper starts servers, waits for them, runs a command and stops them."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

SCRIPT = (
    Path(__file__).resolve().parents[1]
    / "src"
    / "forge"
    / "skills"
    / "web-ui-verification"
    / "scripts"
    / "with_servers.py"
)
PY = f'"{sys.executable}"'


def run(*arguments: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(SCRIPT), *arguments], capture_output=True, text=True, timeout=120
    )


def test_two_servers_start_answer_and_are_stopped(tmp_path: Path) -> None:
    (tmp_path / "a").mkdir()
    (tmp_path / "b").mkdir()
    (tmp_path / "a" / "index.html").write_text("alpha", encoding="utf-8")
    (tmp_path / "b" / "index.html").write_text("bravo", encoding="utf-8")
    check = (
        "import os, urllib.request as u;"
        "a=u.urlopen(os.environ['SERVER_A_URL']+'/index.html').read().decode();"
        "b=u.urlopen(os.environ['SERVER_B_URL']+'/index.html').read().decode();"
        "print(a, b, os.environ['SERVER_A_PORT'] != os.environ['SERVER_B_PORT'])"
    )
    done = run(
        "--server", f"a@{tmp_path / 'a'}::{PY} -m http.server {{port}}::/index.html",
        "--server", f"b@{tmp_path / 'b'}::{PY} -m http.server {{port}}::/index.html",
        "--", sys.executable, "-c", check,
    )  # fmt: skip
    assert done.returncode == 0, done.stderr
    assert "alpha bravo True" in done.stdout


def test_the_commands_exit_code_is_returned() -> None:
    done = run(
        "--server", f"s::{PY} -m http.server {{port}}", "--", sys.executable, "-c", "import sys; sys.exit(7)"
    )
    assert done.returncode == 7


def test_a_server_that_stops_at_once_is_reported_with_its_output() -> None:
    done = run(
        "--server",
        f"dead::{PY} -c \"print('boom on start'); raise SystemExit(1)\"::/",
        "--timeout",
        "20",
        "--",
        sys.executable,
        "-c",
        "print('never')",
    )
    assert done.returncode == 3
    assert "Server 'dead' stopped" in done.stderr and "boom on start" in done.stderr
    assert "never" not in done.stdout
