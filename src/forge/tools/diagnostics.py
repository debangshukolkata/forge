"""Fast checks after every file change (spec §9.1): does the Python file still compile, will the SVG file display?"""

from __future__ import annotations

import asyncio
import re
import sys
from pathlib import Path

from forge.workspace.workspace import Workspace

COMPILE_TIMEOUT_S = 30
SVG_NAMESPACE = "http://www.w3.org/2000/svg"
SVG_ROOT = re.compile(r"<svg\b[^>]*>", re.IGNORECASE)


async def diagnose_file(workspace: Workspace, relative: str) -> str | None:
    """A short problem report, or None when the file looks fine (or isn't Python or SVG)."""
    if relative.lower().endswith(".svg"):
        return _svg_problem(workspace.path_of(relative))
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


def _svg_problem(target: Path) -> str | None:
    """An SVG file without the SVG namespace shows inline but not in <img> or a CSS background: the browser
    draws nothing and the audit only says "broken image" (Stillwater design run 2026-10-29, D-540)."""
    try:
        text = target.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return None
    root = SVG_ROOT.search(text)
    if root is None or SVG_NAMESPACE in root.group(0):
        return None
    return (
        f'SVG check FAILED: the <svg> tag has no xmlns="{SVG_NAMESPACE}". Without it the file shows nothing when '
        "used as <img src> or a CSS background. Add the attribute to the <svg> tag."
    )
