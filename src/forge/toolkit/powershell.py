"""Runs one PowerShell command in a fresh process (DECISIONS D-042).

Forge carries the working directory between commands (like Claude Code); nothing else persists.
The command is wrapped in a generated script that forces UTF-8 output, records the final working
directory and preserves exit codes. It is passed with -EncodedCommand: no quoting problems, and
PowerShell's execution policy (which may block .ps1 files on corporate laptops) does not apply.
"""

from __future__ import annotations

import asyncio
import base64
import codecs
import contextlib
import os
import re
import shutil
import sys
import uuid
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import psutil

from forge.safety.sandbox import SandboxedProcess, spawn_low_integrity
from forge.toolkit.progress import ProgressTracker

# CreateProcess limits a command line to 32,767 characters; base64 of UTF-16 needs ~2.7x the script.
MAX_SCRIPT_CHARS = 11_000
_INPUT_PROMPTS = re.compile(
    r"(\(y/n\)|\[y/n\]|\[Y\] Yes|password:|passphrase|press any key|continue\?|are you sure)", re.IGNORECASE
)


@dataclass
class CommandOutcome:
    exit_code: int | None  # None when killed on timeout
    output: str
    timed_out: bool
    cwd: Path
    waiting_for_input: bool = False


def powershell_executable() -> str:
    for name in ("pwsh", "powershell"):
        found = shutil.which(name)
        if found:
            return found
    return "powershell"


def ps_quote(text: str) -> str:
    return "'" + text.replace("'", "''") + "'"


def build_script(command: str, cwd: Path, cwd_file: Path | None) -> str:
    record_cwd = (
        f"[System.IO.File]::WriteAllText({ps_quote(str(cwd_file))}, (Get-Location).ProviderPath)"
        if cwd_file
        else ""
    )
    return f"""$ErrorActionPreference = 'Continue'
$ProgressPreference = 'SilentlyContinue'
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
$OutputEncoding = [System.Text.Encoding]::UTF8
Set-Location -LiteralPath {ps_quote(str(cwd))}
$global:LASTEXITCODE = 0
$forgeFailed = $false
try {{
{command}
    if (-not $?) {{ $forgeFailed = $true }}
}} catch {{
    Write-Output ($_ | Out-String)
    $forgeFailed = $true
}} finally {{
    {record_cwd}
}}
if ($LASTEXITCODE -ne 0) {{ exit $LASTEXITCODE }}
if ($forgeFailed) {{ exit 1 }}
exit 0
"""


def encoded_arguments(script: str) -> list[str]:
    encoded = base64.b64encode(script.encode("utf-16-le")).decode("ascii")
    return [powershell_executable(), "-NoProfile", "-NonInteractive", "-EncodedCommand", encoded]


async def start_process(
    script: str, cwd: Path, env: dict[str, str], sandboxed: bool = False
) -> asyncio.subprocess.Process | SandboxedProcess:
    """Starts PowerShell for script. sandboxed: at low integrity (D-050); raises SandboxUnavailableError
    if that isn't possible, so the caller can fall back and warn."""
    if sandboxed:
        return await spawn_low_integrity(encoded_arguments(script), cwd, env)
    flags = 0x00000200 if sys.platform == "win32" else 0  # CREATE_NEW_PROCESS_GROUP
    return await asyncio.create_subprocess_exec(
        *encoded_arguments(script),
        cwd=str(cwd),
        env=env,
        stdin=asyncio.subprocess.DEVNULL,  # a command waiting for input fails instead of hanging
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.STDOUT,
        creationflags=flags,
    )


def kill_tree(pid: int) -> None:
    try:
        parent = psutil.Process(pid)
    except psutil.NoSuchProcess:
        return
    processes = [*parent.children(recursive=True), parent]
    for process in processes:
        with contextlib.suppress(psutil.NoSuchProcess):
            process.kill()
    psutil.wait_procs(processes, timeout=5)


async def run_powershell(
    command: str,
    cwd: Path,
    env: dict[str, str],
    timeout_s: float,
    scratch_dir: Path,
    sandboxed: bool = False,
    on_progress: Callable[[dict[str, Any]], Awaitable[None]] | None = None,
) -> CommandOutcome:
    scratch_dir.mkdir(parents=True, exist_ok=True)
    cwd_file = scratch_dir / f"cwd-{uuid.uuid4().hex}.txt"
    script = build_script(command, cwd, cwd_file)
    if len(script) > MAX_SCRIPT_CHARS:
        return CommandOutcome(
            None,
            "Command too long for one shell call. Write long content with "
            "write_file and run it as a script instead.",
            False,
            cwd,
        )
    process = await start_process(script, cwd, env, sandboxed)
    chunks: list[bytes] = []
    tracker = ProgressTracker(on_progress) if on_progress is not None else None
    decoder = codecs.getincrementaldecoder("utf-8")(errors="replace")

    async def collect() -> None:
        assert process.stdout is not None
        while block := await process.stdout.read(65536):
            chunks.append(block)
            if tracker is not None:
                tracker.feed(decoder.decode(block))

    reader = asyncio.create_task(collect())
    ticker = asyncio.create_task(tracker.run()) if tracker is not None else None
    timed_out = False
    try:
        await asyncio.wait_for(process.wait(), timeout_s)
    except TimeoutError:
        timed_out = True
        kill_tree(process.pid)
    except asyncio.CancelledError:  # the user interrupted: never leave the command running
        kill_tree(process.pid)
        raise
    finally:
        if ticker is not None:
            ticker.cancel()
        try:
            await asyncio.wait_for(reader, 5)
        except (TimeoutError, asyncio.CancelledError):
            reader.cancel()
    output = b"".join(chunks).decode("utf-8", errors="replace").replace("\r\n", "\n")
    new_cwd = cwd
    if cwd_file.exists():
        recorded = cwd_file.read_text(encoding="utf-8").strip()
        new_cwd = Path(recorded) if recorded and os.path.isdir(recorded) else cwd
        cwd_file.unlink()
    last_lines = "\n".join(output.strip().splitlines()[-3:])
    return CommandOutcome(
        exit_code=None if timed_out else process.returncode,
        output=output,
        timed_out=timed_out,
        cwd=new_cwd,
        waiting_for_input=timed_out and bool(_INPUT_PROMPTS.search(last_lines)),
    )
