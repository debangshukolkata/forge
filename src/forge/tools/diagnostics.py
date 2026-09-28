"""Fast checks after every file change (spec §9.1): does the Python file still compile?"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

from forge.workspace.workspace import Workspace

COMPILE_TIMEOUT_S = 30


async def diagnose_file(workspace: Workspace, relative: str) -> str | None:
    """A short problem report, or None when the file looks fine (or isn't Python)."""
    if not relative.endswith(".py"):
        return None
    env = workspace.info.python_env
    python = env.python if env else sys.executable
    target = workspace.path_of(relative)
    if not Path(target).exists():
        return None
    # compile() in a subprocess: checks syntax with the app's own Python version, writes no .pyc.
    code = "import sys; compile(open(sys.argv[1], 'rb').read(), sys.argv[1], 'exec')"
    process = await asyncio.create_subprocess_exec(
        python,
        "-c",
        code,
        str(target),
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.STDOUT,
    )
    try:
        output, _ = await asyncio.wait_for(process.communicate(), COMPILE_TIMEOUT_S)
    except TimeoutError:
        process.kill()
        return "Syntax check timed out."
    if process.returncode == 0:
        return None
    lines = output.decode("utf-8", errors="replace").strip().splitlines()
    return "Syntax check FAILED:\n" + "\n".join(lines[-6:])
