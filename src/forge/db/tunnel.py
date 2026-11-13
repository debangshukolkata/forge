"""The tunnel to the development database, started by DebCraft itself (D-605).

The development database is only reachable while a tunnel is open (for the user: `gcloud compute start-iap-tunnel ...`
in a window, after `gcloud auth login`). The user describes the tunnel once in `<DebCraft Home>/tunnels.yaml`; the model
cannot change that file, so it can only start the command the user wrote:

    tunnels:
      dev:                       # the database target it opens the way to ("dev")
        command: [gcloud, compute, start-iap-tunnel, wnxtdb18, "4572", --local-host-port=localhost:9006,
                  --zone=asia-south1-b, --project=my-project]
        port: 9006               # DebCraft waits until this local port accepts connections

`ensure_tunnel` is called before every connection to that target: when the port already answers nothing is done;
otherwise the command is started in the background (no window), its output goes to a log file in DebCraft Home, and it
is stopped when DebCraft ends. A tunnel that does not come up says why; an expired Google login is reported as such, so
the user is asked to run `gcloud auth login`. The command runs without DebCraft's own secrets in its environment."""

from __future__ import annotations

import atexit
import os
import shutil
import socket
import subprocess
import sys
import threading
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

from forge.config import forge_home
from forge.errors import ConfigError

TUNNELS_FILE = "tunnels.yaml"
START_WAIT_SECONDS = 45
LOG_NAME = "tunnel_{name}.log"
_SECRET_WORDS = ("KEY", "TOKEN", "PASSWORD", "SECRET", "_PG_URL", "AZURE_", "TAVILY", "GEMINI")
LOGIN_HINTS = ("reauthentication", "gcloud auth login", "invalid_grant", "credentials", "not logged in")


@dataclass(frozen=True)
class TunnelSpec:
    name: str
    command: tuple[str, ...]
    port: int


class TunnelError(Exception):
    """The tunnel could not be opened; the text says why and what the user can do."""


def load_tunnels(home: Path | None = None) -> dict[str, TunnelSpec]:
    path = (home or forge_home()) / TUNNELS_FILE
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return {}
    try:
        data = yaml.safe_load(text) or {}
    except yaml.YAMLError as error:
        raise ConfigError(f"{TUNNELS_FILE} is not valid YAML: {error}") from error
    tunnels = data.get("tunnels") if isinstance(data, dict) else None
    if not isinstance(tunnels, dict):
        raise ConfigError(f"{TUNNELS_FILE} needs a `tunnels:` section.")
    result: dict[str, TunnelSpec] = {}
    for name, raw in tunnels.items():
        command = raw.get("command") if isinstance(raw, dict) else None
        port = raw.get("port") if isinstance(raw, dict) else None
        if not (
            isinstance(command, list) and command and all(isinstance(part, str | int) for part in command)
        ):
            raise ConfigError(f"{TUNNELS_FILE}, tunnel {name!r}: `command` is a list, the program first.")
        if not isinstance(port, int) or not 0 < port < 65536:
            raise ConfigError(f"{TUNNELS_FILE}, tunnel {name!r}: `port` is the local port the tunnel opens.")
        result[str(name)] = TunnelSpec(str(name), tuple(str(part) for part in command), port)
    return result


def port_open(port: int) -> bool:
    try:
        with socket.create_connection(("127.0.0.1", port), timeout=1):
            return True
    except OSError:
        return False


def _environment() -> dict[str, str]:
    return {
        key: value
        for key, value in os.environ.items()
        if not any(word in key.upper() for word in _SECRET_WORDS)
    }


def _stop(process: subprocess.Popen[Any]) -> None:
    if process.poll() is not None:
        return
    if sys.platform == "win32":  # gcloud.cmd starts python as a child: stop the whole tree
        subprocess.run(
            ["taskkill", "/T", "/F", "/PID", str(process.pid)], capture_output=True, check=False, timeout=15
        )
    else:
        process.terminate()


_running: dict[str, subprocess.Popen[Any]] = {}
_lock = threading.Lock()


@atexit.register
def stop_all() -> None:
    for process in list(_running.values()):
        _stop(process)
    _running.clear()


def _log_tail(log: Path) -> str:
    try:
        lines = [line.strip() for line in log.read_text(encoding="utf-8", errors="replace").splitlines()]
    except OSError:
        return ""
    return " | ".join(line for line in lines if line)[-400:]


def ensure_tunnel(target_name: str, home: Path | None = None) -> str:
    """Makes sure the tunnel for this database target is open. Returns "" when none is described or it was already
    open, else a short note ("tunnel started"). Raises TunnelError with the reason when it cannot be opened."""
    specs = load_tunnels(home)
    spec = specs.get(target_name)
    if spec is None or port_open(spec.port):
        return ""
    with _lock:
        if port_open(spec.port):
            return ""
        old = _running.pop(spec.name, None)
        if old is not None:
            _stop(old)
        program = shutil.which(spec.command[0])
        if program is None:
            raise TunnelError(f"The tunnel program {spec.command[0]!r} is not on the PATH ({TUNNELS_FILE}).")
        folder = home or forge_home()
        log = folder / LOG_NAME.format(name=spec.name)
        folder.mkdir(parents=True, exist_ok=True)
        flags = subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0  # type: ignore[attr-defined,unused-ignore]
        with log.open("wb") as sink:
            process = subprocess.Popen(
                [program, *spec.command[1:]],
                stdin=subprocess.DEVNULL,
                stdout=sink,
                stderr=subprocess.STDOUT,
                env=_environment(),
                creationflags=flags,
            )
        _running[spec.name] = process
        deadline = time.monotonic() + START_WAIT_SECONDS
        while time.monotonic() < deadline:
            if port_open(spec.port):
                return f"The tunnel to {spec.name} was not open; DebCraft started it (port {spec.port})."
            if process.poll() is not None:
                break
            time.sleep(0.5)
        tail = _log_tail(log)
        _stop(process)
        _running.pop(spec.name, None)
        needs_login = any(hint in tail.lower() for hint in LOGIN_HINTS)
        advice = (
            " The Google login looks expired: the user has to run `gcloud auth login`, then try again."
            if needs_login
            else ""
        )
        raise TunnelError(
            f"The tunnel to {spec.name} did not open within {START_WAIT_SECONDS} s. Output: {tail or 'none'}.{advice}"
        )
