"""Shell tools (spec §9.3): run_command and python_run, using the app's own interpreter."""

from __future__ import annotations

import os
from pathlib import Path

from pydantic import Field

from forge.config import SandboxMode
from forge.safety.paths import is_within, real_path
from forge.safety.sandbox import SandboxUnavailableError, has_low_label, label_low
from forge.safety.sandbox import is_supported as sandbox_supported
from forge.safety.shell_classifier import ShellScope
from forge.toolkit.base import Tool, ToolArgs, ToolContext, ToolResult
from forge.toolkit.powershell import ps_quote, run_powershell
from forge.workspace.stub_packages import ensure_shared_stub_packages
from forge.workspace.workspace import Workspace

DEFAULT_TIMEOUT_S = 120
MAX_TIMEOUT_S = 600


TEST_MARKERS = ("pytest", "unittest", "manage.py test")


def is_test_command(command: str) -> bool:
    lowered = command.lower()
    return any(marker in lowered for marker in TEST_MARKERS)


def looks_like_write(command: str) -> bool:
    """Shell commands that change files count as edits for the evidence rule (e.g. a formatter)."""
    lowered = command.lower()
    return any(
        word in lowered
        for word in (
            "set-content",
            "out-file",
            "add-content",
            " > ",
            "ruff format",
            "black ",
            "move-item",
            "copy-item",
            "remove-item",
            "new-item",
        )
    )


class ShellSession:
    """What persists between commands: the working directory (and nothing else, see D-042), plus
    whether commands run in the low-integrity sandbox (D-050)."""

    def __init__(self, workspace: Workspace, sandbox: SandboxMode = "low_integrity") -> None:
        self.workspace = workspace
        self.cwd = workspace.app_dir
        self.sandbox_wanted = sandbox == "low_integrity" and sandbox_supported()
        self.sandbox_active: bool | None = None  # None until the first command prepares it
        self.pending_notice: str | None = None  # told to the model and the user once
        self.extra_env: dict[str, str] = {}  # e.g. PGOPTIONS for the scratch schema (M7)

    @property
    def python(self) -> str | None:
        env = self.workspace.info.python_env
        return env.python if env else None

    @property
    def scratch_dir(self) -> Path:
        return self.workspace.forge_dir / "tmp"

    @property
    def sandbox_dir(self) -> Path:
        return self.workspace.forge_dir / "sandbox"

    def prepare_sandbox(self) -> bool:
        """Labels the folders sandboxed commands may write to. Only repo/ and two scratch folders:
        output/, checkpoints, baseline and permissions.json stay out of reach."""
        if self.sandbox_active is not None:
            return self.sandbox_active
        if not self.sandbox_wanted:
            self.sandbox_active = False
            return False
        marker = self.sandbox_dir / "labelled"
        try:
            # The marker alone isn't trusted: before D-100 labelling could fail silently.
            if not marker.exists() or not has_low_label(self.workspace.repo_dir):
                for folder in (self.workspace.repo_dir, self.scratch_dir, self.sandbox_dir):
                    label_low(self.workspace.jail.check(folder))
                if self.workspace.mode_b:
                    label_low(self.workspace.jail.check(self.workspace.harness_dir))
                    venv = self.workspace.root / ".venv"
                    # Mode B's own venv: pip installs into it run sandboxed. It stays outside the write jail
                    # (Forge's file tools never edit it), so it is checked to be inside the workspace instead.
                    if venv.is_dir() and is_within(real_path(venv), real_path(self.workspace.root)):
                        label_low(venv)
                self.workspace.jail.check(marker).write_text(
                    "low integrity labels applied\n", encoding="utf-8"
                )
            self.sandbox_active = True
        except SandboxUnavailableError as error:
            self.disable_sandbox(str(error))
        return bool(self.sandbox_active)

    def disable_sandbox(self, reason: str) -> None:
        self.sandbox_active = False
        self.pending_notice = f"Sandbox unavailable, commands now run without it: {reason}"

    def environment(self) -> dict[str, str]:
        env = self.workspace.info.python_env
        variables = env.command_env() if env else dict(os.environ)
        variables.setdefault("PYTHONDONTWRITEBYTECODE", "1")
        variables.setdefault("PYTHONUTF8", "1")
        if self.sandbox_active:
            # Sandboxed processes can't write to the user's %TEMP% or pip cache; give them their own.
            variables["TEMP"] = variables["TMP"] = str(self.scratch_dir)
            variables["PIP_CACHE_DIR"] = str(self.sandbox_dir / "pip-cache")
        if self.workspace.mode_b:  # the host stand-ins load for any pytest the model runs (D-159)
            existing = variables.get("PYTEST_ADDOPTS", "")
            if "harness_conftest" not in existing:
                variables["PYTEST_ADDOPTS"] = f"{existing} -p harness_conftest".strip()
        variables.update(self.extra_env)
        return variables

    def scope(self) -> ShellScope:
        env = self.workspace.info.python_env
        readable = [Path(env.venv)] if env else []
        return ShellScope(
            workspace_root=self.workspace.root,
            original_repo=Path(self.workspace.info.repo_path) if self.workspace.info.repo_path else None,
            strict=self.workspace.mode_b,
            cwd=self.cwd,
            readable_roots=readable,
        )

    def resolve_cwd(self, relative: str | None) -> Path:
        return self.workspace.path_of(relative) if relative else self.cwd

    def display(self, path: Path) -> str:
        return (
            real_path(path).relative_to(real_path(self.workspace.root)).as_posix()
            if is_within(real_path(path), real_path(self.workspace.root))
            else str(path)
        )


class RunCommand(Tool):
    name = "run_command"
    output_kind = "shell"
    description = (
        "Run a PowerShell command (Windows) in the workspace, e.g. tests or a linter. Each call is a fresh "
        "shell: only the working directory carries over. The app's venv is active and imports resolve to "
        "the workspace copy. Stdin is closed, so interactive prompts fail. Prefer the file tools for "
        "reading and editing files, and python_run for Python."
    )

    class Args(ToolArgs):
        command: str
        timeout_s: int = Field(default=DEFAULT_TIMEOUT_S, ge=1, le=MAX_TIMEOUT_S)
        cwd: str | None = Field(default=None, description="Folder relative to the repository root.")

    def summary(self, args: RunCommand.Args) -> str:
        return args.command

    def command(self, args: RunCommand.Args, context: ToolContext) -> str:
        return args.command

    async def run(self, args: RunCommand.Args, context: ToolContext) -> ToolResult:
        assert context.shell is not None
        return await execute(context, args.command, args.timeout_s, args.cwd)


class PythonRun(Tool):
    name = "python_run"
    output_kind = "shell"
    description = (
        "Run the app's own Python interpreter with arguments, e.g. '-m pytest -q tests/test_x.py'. "
        "Imports resolve to the workspace copy."
    )

    class Args(ToolArgs):
        args: str = Field(description="Arguments after 'python', e.g. -m pytest -q")
        timeout_s: int = Field(default=DEFAULT_TIMEOUT_S, ge=1, le=MAX_TIMEOUT_S)
        cwd: str | None = Field(default=None, description="Folder relative to the repository root.")

    def summary(self, args: PythonRun.Args) -> str:
        return f"python {args.args}"

    def command(self, args: PythonRun.Args, context: ToolContext) -> str:
        python = context.shell.python if context.shell else None
        return f"& {ps_quote(python)} {args.args}" if python else f"python {args.args}"

    async def run(self, args: PythonRun.Args, context: ToolContext) -> ToolResult:
        return await execute(context, self.command(args, context), args.timeout_s, args.cwd)


async def execute(context: ToolContext, command: str, timeout_s: int, cwd: str | None) -> ToolResult:
    shell = context.shell
    assert shell is not None
    if context.workspace.mode_b:  # stub packages must not hide the new code (D-159)
        ensure_shared_stub_packages(context.workspace)
    start_dir = shell.resolve_cwd(cwd)
    if not start_dir.is_dir():
        # A folder that doesn't exist made the sandbox launch fail, which looked like "sandbox unavailable"
        # and switched the sandbox off for the rest of the session (found in the first Mode B build).
        return ToolResult(
            ok=False,
            content=f"No such folder: {cwd!r} (cwd is relative to the repository root; in Mode B that is "
            f"project/ itself, so don't prefix it). Leave cwd out to stay in {shell.display(shell.cwd)}.",
        )
    sandboxed = shell.prepare_sandbox()
    try:
        outcome = await run_powershell(
            command, start_dir, shell.environment(), timeout_s, shell.scratch_dir, sandboxed
        )
    except SandboxUnavailableError as error:
        shell.disable_sandbox(str(error))
        outcome = await run_powershell(command, start_dir, shell.environment(), timeout_s, shell.scratch_dir)
    shell.cwd = outcome.cwd
    passed = not outcome.timed_out and outcome.exit_code == 0
    if passed and is_test_command(command):
        context.last_verified_step = context.step  # evidence for task_update (spec §8)
    elif looks_like_write(command):
        context.last_edit_step = context.step
    lines = [outcome.output.rstrip()]
    if shell.pending_notice:
        await context.emit("notice", {"kind": "sandbox", "text": shell.pending_notice})
        lines.insert(0, f"[{shell.pending_notice}]")
        shell.pending_notice = None
    if outcome.timed_out:
        lines.append(f"[timed out after {timeout_s}s; the process and its children were stopped]")
        if outcome.waiting_for_input:
            lines.append(
                "[it looked like it was waiting for input; pass answers as arguments or flags instead]"
            )
    else:
        lines.append(f"[exit code {outcome.exit_code}]")
    lines.append(f"[cwd: {shell.display(outcome.cwd)}]")
    text, full_path = context.cap_output("\n".join(line for line in lines if line), "shell")
    return ToolResult(
        ok=not outcome.timed_out and outcome.exit_code == 0,
        content=text,
        meta={"exit_code": outcome.exit_code, "timed_out": outcome.timed_out},
        full_output_path=full_path,
    )
