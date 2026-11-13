"""Fast checks after every file change (spec §9.1): does the Python file still compile, will the SVG file display,
is the JSON file valid, do the JavaScript and TypeScript files parse (HW4)?

Python, SVG and JSON run no project code. Node (and the TypeScript compiler it loads from the project's
node_modules, which is workspace code) runs only through the sandboxed command path, `execute`."""

from __future__ import annotations

import asyncio
import json
import re
import shutil
import sys
from pathlib import Path

from forge.toolkit.base import ToolContext
from forge.toolkit.powershell import ps_quote
from forge.toolkit.shell import execute

COMPILE_TIMEOUT_S = 30
NODE_CHECK_TIMEOUT_S = 10
TYPESCRIPT_TIMEOUT_S = 20
MAX_JSON_BYTES = 5_000_000
SVG_NAMESPACE = "http://www.w3.org/2000/svg"
SVG_ROOT = re.compile(r"<svg\b[^>]*>", re.IGNORECASE)
JSON_WITH_COMMENTS_NAMES = ("tsconfig", "jsconfig", ".eslintrc")
TYPESCRIPT_SYNTAX_ERROR = re.compile(r"\((\d+),(\d+)\): error TS1\d{3}: (.*)$")
SHELL_FOOTER = re.compile(r"^\[(exit code|cwd:|timed out).*$", re.MULTILINE)


async def diagnose_file(context: ToolContext, relative: str) -> str | None:
    """A short problem report, or None when the file looks fine, is not a kind we check, or the check
    could not run (a missing tool must never look like a mistake in the file)."""
    workspace = context.workspace
    lowered = relative.lower()
    if lowered.endswith(".svg"):
        return _svg_problem(workspace.path_of(relative))
    if lowered.endswith(".json"):
        return _json_problem(relative, workspace.path_of(relative))
    if lowered.endswith((".js", ".mjs", ".cjs")):
        return await _javascript_problem(context, workspace.path_of(relative))
    if lowered.endswith((".ts", ".tsx")):
        return await _typescript_problem(context, workspace.path_of(relative))
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


def _json_problem(relative: str, target: Path) -> str | None:
    normalized = relative.replace("\\", "/")
    name = normalized.rsplit("/", 1)[-1].lower()
    if (
        name.startswith(JSON_WITH_COMMENTS_NAMES)
        or normalized.startswith(".vscode/")
        or "/.vscode/" in normalized
    ):
        return None  # these files allow comments
    try:
        if target.stat().st_size > MAX_JSON_BYTES:
            return None
        text = target.read_text(encoding="utf-8-sig")
    except (OSError, UnicodeDecodeError):
        return None
    if "//" in text or "/*" in text:
        return None  # may be JSON with comments; telling a comment from a string is not worth a false report
    try:
        json.loads(text)
    except json.JSONDecodeError as error:
        return f"Syntax check FAILED:\n{error.msg} (line {error.lineno}, column {error.colno})"
    return None


async def _node_output(context: ToolContext, command: str, timeout_s: int) -> tuple[bool, str] | None:
    """(passed, output) of a node command run through the sandboxed shell, or None when it could not run."""
    if context.shell is None:
        return None
    try:
        result = await execute(context, command, timeout_s, None)
    except Exception:  # a check that cannot start is not a problem in the file
        return None
    if result.meta.get("timed_out"):
        return None
    return result.ok, SHELL_FOOTER.sub("", result.content).strip()


async def _javascript_problem(context: ToolContext, target: Path) -> str | None:
    if shutil.which("node") is None or not Path(target).exists():
        return None
    outcome = await _node_output(context, f"node --check {ps_quote(str(target))}", NODE_CHECK_TIMEOUT_S)
    if outcome is None or outcome[0] or "SyntaxError" not in outcome[1]:
        return None
    return "Syntax check FAILED:\n" + "\n".join(outcome[1].splitlines()[:6])


def _typescript_launcher(context: ToolContext, target: Path) -> Path | None:
    """node_modules/typescript/bin/tsc of the nearest folder from the file up to the repository root. It is
    a Node script in every TypeScript version (7 started a native compiler from it), so Node runs it."""
    root = context.workspace.repo_dir.resolve()
    folder = target.resolve().parent
    while True:
        candidate = folder / "node_modules" / "typescript" / "bin" / "tsc"
        if candidate.is_file():
            return candidate
        if folder == root or root not in folder.parents:
            return None
        folder = folder.parent


async def _typescript_problem(context: ToolContext, target: Path) -> str | None:
    """Syntax errors of one file by the project's own tsc (D-583). The file is checked alone, without the
    project's settings, so a missing import or a wrong type is not reported: only the errors in the 1000
    range, which are the ones about the text itself ("';' expected")."""
    if shutil.which("node") is None or not Path(target).exists():
        return None
    launcher = _typescript_launcher(context, target)
    if launcher is None:
        return None
    command = (
        f"node {ps_quote(str(launcher))} --noEmit --noResolve --skipLibCheck --jsx preserve --pretty false "
        f"{ps_quote(str(target))}"
    )
    outcome = await _node_output(context, command, TYPESCRIPT_TIMEOUT_S)
    if outcome is None or outcome[0]:
        return None
    problems = [
        f"{match.group(1)}:{match.group(2)} {match.group(3)}"
        for line in outcome[1].splitlines()
        if (match := TYPESCRIPT_SYNTAX_ERROR.search(line))
    ]
    return ("Syntax check FAILED:\n" + "\n".join(problems[:6])) if problems else None


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
