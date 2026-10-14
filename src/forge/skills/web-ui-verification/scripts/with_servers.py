"""Start servers, wait until they answer, run one command, stop the servers (TODO C15, D-376).

A verifier's browser script should hold only the browser logic. This helper owns the servers' lifecycle:

    python with_servers.py --server "api::python -m uvicorn app:app --port {port}::/health" \
                           --server "web::npm run dev -- --port {port}::/" -- python tests/e2e/check_app.py

Each `--server` is `name::command::path`: the name, the command ({port} becomes a free port; the folder is the current one unless `name@folder` is used),
and the path that answers when the server is ready (a 200 to 499 reply counts; empty = a TCP connection is enough). The command after `--` runs with
one environment variable per server: `SERVER_<NAME>_URL` (http://127.0.0.1:<port>) and `SERVER_<NAME>_PORT`. The exit code of that command is this
script's exit code; the servers are always stopped, with their whole process tree. If a server does not come up in time, its output is printed and the exit
code is 3. Standard library only, so it runs in any app's own environment."""

from __future__ import annotations

import argparse
import os
import re
import socket
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request
from pathlib import Path

READY_TIMEOUT_S = 90.0


def free_port() -> int:
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        return int(probe.getsockname()[1])


def parse_server(text: str) -> tuple[str, str, str, str]:
    """(name, folder, command, ready path) from `name[@folder]::command::path`."""
    parts = text.split("::")
    if len(parts) < 2:
        raise SystemExit(f"--server needs name::command[::path], got {text!r}")
    name, _, folder = parts[0].partition("@")
    return name.strip(), folder.strip() or ".", parts[1].strip(), (parts[2].strip() if len(parts) > 2 else "")


def answers(port: int, path: str) -> bool:
    if not path:
        try:
            with socket.create_connection(("127.0.0.1", port), timeout=1):
                return True
        except OSError:
            return False
    try:
        with urllib.request.urlopen(f"http://127.0.0.1:{port}{path}", timeout=2):
            return True
    except urllib.error.HTTPError as error:
        return error.code < 500
    except (OSError, ValueError):
        return False


def stop(process: subprocess.Popen[bytes]) -> None:
    if process.poll() is not None:
        return
    if os.name == "nt":  # the whole tree: npm and uvicorn start children
        subprocess.run(["taskkill", "/PID", str(process.pid), "/T", "/F"], capture_output=True, check=False)
    else:
        process.terminate()
    try:
        process.wait(timeout=10)
    except subprocess.TimeoutExpired:
        process.kill()


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("--server", action="append", default=[], help="name[@folder]::command::ready-path")
    parser.add_argument("--timeout", type=float, default=READY_TIMEOUT_S)
    parser.add_argument("command", nargs=argparse.REMAINDER)
    args = parser.parse_args(argv)
    command = [c for c in args.command if c != "--"] if args.command[:1] == ["--"] else args.command
    if not command:
        raise SystemExit("Give the command to run after --")
    environment = dict(os.environ)
    started: list[tuple[str, subprocess.Popen[bytes], Path, int, str]] = []
    code = 0
    try:
        for text in args.server:
            name, folder, line, path = parse_server(text)
            port = free_port()
            descriptor, log_name = tempfile.mkstemp(prefix=f"server-{name}-", suffix=".log")
            os.close(descriptor)  # Windows cannot reopen a file that is still held open here
            log = Path(log_name)
            line = line.replace("{port}", str(port))
            with log.open("wb") as sink:
                process = subprocess.Popen(
                    line,
                    cwd=folder,
                    shell=True,
                    stdout=sink,
                    stderr=subprocess.STDOUT,
                    env={**environment, "PORT": str(port)},
                    creationflags=getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0),
                )
            started.append((name, process, log, port, path))
            key = re.sub(r"\W", "_", name).upper()
            environment[f"SERVER_{key}_URL"] = f"http://127.0.0.1:{port}"
            environment[f"SERVER_{key}_PORT"] = str(port)
        deadline = time.monotonic() + args.timeout
        for name, process, log, port, path in started:
            while not answers(port, path):
                if process.poll() is not None or time.monotonic() > deadline:
                    why = (
                        "stopped"
                        if process.poll() is not None
                        else f"did not answer within {args.timeout:.0f} s"
                    )
                    print(
                        f"Server {name!r} {why}. Its output:\n{log.read_text(encoding='utf-8', errors='replace')[-2000:]}",
                        file=sys.stderr,
                    )
                    return 3
                time.sleep(0.3)
        code = subprocess.run(command, env=environment, check=False).returncode
    finally:
        for _, process, log, _, _ in started:
            stop(process)
            log.unlink(missing_ok=True)
    return code


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
