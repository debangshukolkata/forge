"""Shell tools (spec §9.3): run_command and python_run, using the app's own interpreter."""

from __future__ import annotations

import os
import re
from pathlib import Path

from pydantic import Field

from forge.config import SandboxMode, env_file_path, forge_home, load_secrets
from forge.net import (
    installed_node_version,
    looks_like_certificate_error,
    node_supports_system_ca,
    system_certificates_wanted,
    windows_certificate_bundle,
)
from forge.safety.paths import is_within, real_path
from forge.safety.sandbox import SandboxUnavailableError, has_low_label, label_low
from forge.safety.sandbox import is_supported as sandbox_supported
from forge.safety.shell_classifier import ShellScope
from forge.toolkit.app_keys import is_debcrafts_own, secret_environment
from forge.toolkit.base import Tool, ToolArgs, ToolContext, ToolResult
from forge.toolkit.powershell import ps_quote, run_powershell
from forge.toolkit.private_env import without_private, without_store_aliases
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
        self.app_env: dict[str, str] = {}  # AZURE_OPENAI_* of the model the user granted to the app (D-466)
        self.ca_bundle: Path | None = None  # the Windows certificates as one PEM file for Node tools (D-402)
        self.ca_checked = False

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
                    # (DebCraft's file tools never edit it), so it is checked to be inside the workspace instead.
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

    def prepare_ca_bundle(self, force: bool = False) -> bool:
        """Makes the Windows certificate bundle for Node when the installed Node cannot read the store itself (before 22.15), or when a command has just failed on a
        certificate (`force`). Returns whether a bundle is in use (D-402)."""
        if self.ca_bundle is not None:
            return True
        if self.ca_checked and not force:
            return False
        self.ca_checked = True
        version = installed_node_version()
        if not force and (version is None or node_supports_system_ca(version)):
            return False
        self.ca_bundle = windows_certificate_bundle(self.sandbox_dir / "certs" / "windows-roots.pem")
        return self.ca_bundle is not None

    def environment(self) -> dict[str, str]:
        env = self.workspace.info.python_env
        variables = without_store_aliases(
            without_private(env.command_env() if env else dict(os.environ))
        )  # D-202, D-444
        variables.setdefault("PYTHONDONTWRITEBYTECODE", "1")
        variables.setdefault("PYTHONUTF8", "1")
        # npm uses its cache for packages it already has and goes to the network only for new ones; the audit and funding
        # requests add seconds to every install and nothing the build needs (S6).
        variables.setdefault("npm_config_prefer_offline", "true")
        variables.setdefault("npm_config_audit", "false")
        variables.setdefault("npm_config_fund", "false")
        # Behind company HTTPS inspection node tools (npx shadcn, node fetch) fail with "unable to get local issuer certificate" because
        # Node ignores the Windows store; Python already uses it (forge.net). Older Node versions ignore this variable (D-363).
        if system_certificates_wanted():
            variables.setdefault("NODE_USE_SYSTEM_CA", "1")
            self.prepare_ca_bundle()
            if self.ca_bundle is not None:
                variables.setdefault("NODE_EXTRA_CA_CERTS", str(self.ca_bundle))
        variables.setdefault(
            "PYTHONUNBUFFERED", "1"
        )  # a server's "Serving on ..." line must reach DebCraft at once, not when a buffer fills (S6)
        if self.sandbox_active:
            # Sandboxed processes can't write to the user's %TEMP% or pip cache; give them their own.
            variables["TEMP"] = variables["TMP"] = str(self.scratch_dir)
            variables["PIP_CACHE_DIR"] = str(self.sandbox_dir / "pip-cache")
            # npm, yarn and pnpm default to caches under the user's profile, which low integrity can't write:
            # npm install / npm create failed with EPERM and the model handed the step to the user (D-223).
            variables["npm_config_cache"] = str(self.sandbox_dir / "npm-cache")
            variables["npm_config_devdir"] = str(self.sandbox_dir / "node-gyp")
            variables["npm_config_update_notifier"] = "false"
            variables["YARN_CACHE_FOLDER"] = str(self.sandbox_dir / "yarn-cache")
            variables["npm_config_store_dir"] = str(self.sandbox_dir / "pnpm-store")
        if self.workspace.mode_b:  # the host stand-ins load for any pytest the model runs (D-159)
            existing = variables.get("PYTEST_ADDOPTS", "")
            if "harness_conftest" not in existing:
                variables["PYTEST_ADDOPTS"] = f"{existing} -p harness_conftest".strip()
        # Every pytest run the model starts goes without pytest's cache plugin, as DebCraft's own gate commands already do: on the office laptop plain `pytest` printed [100%] and then hung for 2 to 10 minutes
        # (four runs, 16 of 30 minutes of one job, D-458) while `-p no:cacheprovider` finished in under two seconds. DebCraft never needs `--lf`/`--ff`.
        existing = variables.get("PYTEST_ADDOPTS", "")
        if "cacheprovider" not in existing:
            variables["PYTEST_ADDOPTS"] = f"{existing} -p no:cacheprovider".strip()
        libraries = libraries_folder(self.workspace)
        if libraries.is_dir():
            variables["PYTHONPATH"] = os.pathsep.join(
                part for part in (str(libraries), variables.get("PYTHONPATH", "")) if part
            )
        variables.update(self.extra_env)
        variables.update(self.app_env)  # the model the user let the app use for testing (D-466)
        # What the user let this project's commands use from DebCraft's .env, read now: a value the user has
        # just added or replaced is there for the next command, without a restart (D-570).
        variables.update(secret_environment(self.workspace, load_secrets(forge_home())))
        return variables

    def scope(self) -> ShellScope:
        env = self.workspace.info.python_env
        readable = [Path(env.venv)] if env else []
        readable += self.workspace.read_grants.roots()  # skills and what the user granted (D-208)
        return ShellScope(
            workspace_root=self.workspace.root,
            original_repo=Path(self.workspace.info.repo_path) if self.workspace.info.repo_path else None,
            strict=self.workspace.mode_b,
            own_folders=self.workspace.own_folders() if self.workspace.mode_b else None,
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


def certificate_advice(shell: ShellSession) -> str:
    """What the model does after a certificate failure: Forge switches to the Windows certificate bundle itself, so the retry usually works (D-402)."""
    already = shell.ca_bundle is not None
    if not already:
        shell.prepare_ca_bundle(force=True)
        if shell.ca_bundle is not None:
            return (
                "[Certificate error: this network inspects HTTPS with a company certificate that this tool did not trust. DebCraft has now exported the certificates "
                "Windows trusts and passes them to every command (NODE_EXTRA_CA_CERTS): run the same command again. Do not switch certificate checking off.]"
            )
    return (
        "[Certificate error that DebCraft cannot fix by itself: "
        + (
            "the Windows certificate bundle is already in use, so the company root certificate is probably not in the Windows store. "
            if already
            else ""
        )
        + "Tell the user: the company's root certificate must be installed in Windows or exported as a PEM file and named in NODE_EXTRA_CA_CERTS. "
        "Do not set NODE_TLS_REJECT_UNAUTHORIZED=0 or any 'strict-ssl false' option.]"
    )


_PYTEST_SUMMARY = re.compile(r"\b\d+ (?:passed|failed|errors?|skipped|deselected)\b")


def hung_after_last_test(output: str) -> bool:
    """A pytest progress line reached 100% and no summary line followed: the run hangs in its teardown (office laptop, 2026-10-16: the same command was run four times and lost two minutes each time)."""
    return "[100%]" in output and not _PYTEST_SUMMARY.search(output)


def withheld_names_note(command: str, shell: ShellSession) -> str:
    """What to tell the model when a command looks for a name that is in DebCraft's .env but not in the
    command's environment. On the office laptop it ran `os.getenv('DEVELOPMENT_INSTANCE_TOKEN')`, saw "missing",
    decided the file was not loaded and sent the user to restart DebCraft and to copy values elsewhere, four
    times (D-570). The command cannot see the name by design (D-202); the result has to say so."""
    names = [
        name
        for name in load_secrets(forge_home()).names()
        if re.search(rf"(?<![A-Za-z0-9_]){re.escape(name)}(?![A-Za-z0-9_])", command)
    ]
    if not names:
        return ""
    given = shell.environment()
    own = [name for name in names if name not in given and is_debcrafts_own(name)]
    held = [name for name in names if name not in given and name not in own]
    parts: list[str] = []
    if held:
        listed = ", ".join(f'"{name}"' for name in held)
        parts.append(
            f"About {', '.join(held)}: set in DebCraft's .env file ({env_file_path(forge_home())}). Nothing is "
            "missing and nothing needs a restart: DebCraft reads that file again on every call. A command does "
            "not inherit DebCraft's variables, which is why a check with os.environ or $env: shows them as "
            f"missing. To hand them to this project's commands, call request_app_secret with names=[{listed}]: "
            "the user confirms with one click and edits nothing. For a call to the application's API on "
            "localhost use http_request with `token_env`. Do not ask the user to restart DebCraft, to set the "
            "variables somewhere else or to copy the file."
        )
    if own:
        parts.append(
            f"{', '.join(own)}: DebCraft's own settings, never handed to a command (for an app that calls an "
            "Azure OpenAI model use request_app_keys)."
        )
    return f"[{' '.join(parts)}]" if parts else ""


PIP_INSTALL = re.compile(r"\bpip3?(?:\.exe)?\s+install\b|-m\s+pip\s+install\b", re.IGNORECASE)
PIP_TARGET = re.compile(r"(?:--target(?:=|\s+)|\s-t\s+)(?P<path>\"[^\"]+\"|'[^']+'|\S+)", re.IGNORECASE)
LIBRARIES_FOLDER = "libs"


def libraries_folder(workspace: Workspace) -> Path:
    """Where libraries installed to run the application go: outside the repository copy, so neither the index nor
    the delivery sees them (KP8). `PYTHONPATH` carries it into every command."""
    return workspace.forge_dir / LIBRARIES_FOLDER


def install_into_copy(workspace: Workspace, command: str, start_dir: Path) -> str | None:
    """Refuses `pip install --target <folder inside the repository copy>`: on the office laptop that wrote 2,900
    library files into the copy, which the index parsed on every call and the delivery then held (KP8)."""
    if not PIP_INSTALL.search(command):
        return None
    for found in PIP_TARGET.finditer(command):
        target = Path(found.group("path").strip("\"'"))
        target = target if target.is_absolute() else start_dir / target
        if is_within(real_path(target), real_path(workspace.repo_dir)):
            libs = libraries_folder(workspace)
            return (
                f"Not run: `--target` would put the libraries inside the repository copy ({found.group('path')}), "
                "and everything in the copy is delivered. Install them for the project's virtual environment with "
                f'`python -m pip install <package>`, or into `--target "{libs}"`: that folder is on PYTHONPATH '
                "in every command, so imports find them there."
            )
    return None


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
    refused = install_into_copy(context.workspace, command, start_dir)
    if refused:
        return ToolResult(ok=False, content=refused)
    sandboxed = shell.prepare_sandbox()

    async def report(progress: dict[str, object]) -> None:
        await context.emit("tool_progress", {"source": "command", **progress})

    try:
        outcome = await run_powershell(
            command, start_dir, shell.environment(), timeout_s, shell.scratch_dir, sandboxed, report
        )
    except SandboxUnavailableError as error:
        shell.disable_sandbox(str(error))
        outcome = await run_powershell(
            command, start_dir, shell.environment(), timeout_s, shell.scratch_dir, on_progress=report
        )
    shell.cwd = outcome.cwd
    passed = not outcome.timed_out and outcome.exit_code == 0
    if passed and "playwright" in command.lower():
        context.last_browser_step = context.step  # a Playwright script ran and passed (D-167)
    if is_test_command(command):
        context.baseline_checked = True  # any run, green or red, tells the model where it stands (D-408)
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
        lines.append(
            f"[timed out after {timeout_s}s; the process and its children were stopped. If it needs "
            "longer, run it with start_background and follow it with monitor]"
        )
        if outcome.waiting_for_input:
            lines.append(
                "[it looked like it was waiting for input; pass answers as arguments or flags instead]"
            )
        if hung_after_last_test(outcome.output):
            lines.append(
                "[the tests reached 100% but the run never printed its summary: something in the teardown hangs (a fixture that stops a server or closes a browser, a thread that never ends). "
                "Running the same command again will hang the same way: find what the tests start and make it stop (daemon threads, a timeout on the server shutdown, close the browser in a finalizer), "
                "or run the checks that matter without that fixture]"
            )
    else:
        lines.append(f"[exit code {outcome.exit_code}]")
    lines.append(withheld_names_note(command, shell))
    lines.append(f"[cwd: {shell.display(outcome.cwd)}]")
    if not passed and looks_like_certificate_error(outcome.output):
        lines.append(certificate_advice(shell))
    text, full_path = context.cap_output("\n".join(line for line in lines if line), "shell")
    return ToolResult(
        ok=not outcome.timed_out and outcome.exit_code == 0,
        content=text,
        meta={"exit_code": outcome.exit_code, "timed_out": outcome.timed_out},
        full_output_path=full_path,
    )
