"""Classifies a PowerShell command before it runs (spec §14.3). Conservative by design:

- blocked : never runs (e.g. Set-ExecutionPolicy, registry edits, git push, iex, writes into the
            original repository, -EncodedCommand);
- ask     : needs the user's approval. `always_ask` marks reasons that even auto mode must ask for
            (pip installs, network access, paths outside the workspace, nested shells);
- safe    : read-only or a known test/lint/run command inside the workspace.

Anything the classifier does not recognise is "ask". It is a guard rail, not a sandbox: see R2.
"""

from __future__ import annotations

import ntpath
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal

from forge.safety.paths import is_within, real_path

Level = Literal["safe", "ask", "blocked"]

ALIASES = {
    "ls": "get-childitem",
    "dir": "get-childitem",
    "gci": "get-childitem",
    "cat": "get-content",
    "type": "get-content",
    "gc": "get-content",
    "rm": "remove-item",
    "del": "remove-item",
    "erase": "remove-item",
    "rmdir": "remove-item",
    "rd": "remove-item",
    "ri": "remove-item",
    "cp": "copy-item",
    "copy": "copy-item",
    "cpi": "copy-item",
    "mv": "move-item",
    "move": "move-item",
    "mi": "move-item",
    "ren": "rename-item",
    "rni": "rename-item",
    "ni": "new-item",
    "md": "new-item",
    "mkdir": "new-item",
    "sc": "set-content",
    "ac": "add-content",
    "echo": "write-output",
    "write": "write-output",
    "cd": "set-location",
    "sl": "set-location",
    "chdir": "set-location",
    "pwd": "get-location",
    "gl": "get-location",
    "sls": "select-string",
    "iwr": "invoke-webrequest",
    "irm": "invoke-restmethod",
    "curl": "invoke-webrequest",
    "wget": "invoke-webrequest",
    "iex": "invoke-expression",
    "saps": "start-process",
    "start": "start-process",
    "kill": "stop-process",
    "spps": "stop-process",
    "sp": "set-itemproperty",
    "ii": "invoke-item",
    "where": "where-object",
    "select": "select-object",
    "sort": "sort-object",
    "measure": "measure-object",
    "ft": "format-table",
    "fl": "format-list",
    "tee": "tee-object",
}

READ_ONLY = {
    "get-childitem",
    "get-content",
    "get-location",
    "get-item",
    "get-itemproperty",
    "test-path",
    "resolve-path",
    "select-string",
    "measure-object",
    "where-object",
    "select-object",
    "sort-object",
    "format-table",
    "format-list",
    "out-string",
    "out-null",
    "write-output",
    "write-host",
    "get-date",
    "get-command",
    "get-help",
    "get-process",
    "get-filehash",
    "split-path",
    "join-path",
    "set-location",
    "push-location",
    "pop-location",
    "findstr",
    "hostname",
    "whoami",
    "group-object",
    "compare-object",
    "convertfrom-json",
    "convertto-json",
    "get-unique",
    "foreach-object",
}
WRITE_VERBS = {
    "remove-item",
    "set-content",
    "add-content",
    "out-file",
    "new-item",
    "copy-item",
    "move-item",
    "rename-item",
    "clear-content",
    "tee-object",
    "set-item",
    "expand-archive",
    "compress-archive",
}
BLOCKED_VERBS = {
    "invoke-expression": "runs arbitrary strings as code",
    "set-executionpolicy": "changes PowerShell security policy",
    "format-volume": "formats a disk",
    "format": "formats a disk",
    "diskpart": "disk partitioning",
    "reg": "edits the registry",
    "regedit": "edits the registry",
    "set-itemproperty": "edits the registry",
    "new-itemproperty": "edits the registry",
    "remove-itemproperty": "edits the registry",
    "set-mppreference": "changes Windows Defender",
    "add-mppreference": "changes Windows Defender",
    "bcdedit": "changes boot configuration",
    "vssadmin": "deletes shadow copies",
    "cipher": "wipes disk data",
    "shutdown": "shuts the machine down",
    "restart-computer": "restarts the machine",
    "stop-computer": "shuts the machine down",
    "takeown": "takes file ownership",
    "runas": "elevates",
    "net": "changes users/shares",
    "schtasks": "creates scheduled tasks",
    "sc.exe": "changes services",
}
NETWORK_VERBS = {
    "invoke-webrequest",
    "invoke-restmethod",
    "test-netconnection",
    "start-bitstransfer",
    "curl.exe",
    "wget.exe",
    "ssh",
    "scp",
    "ftp",
    "telnet",
}
NESTED_SHELLS = {"powershell", "pwsh", "cmd", "bash", "wsl", "start-process"}
PYTHON_NAMES = {"python", "python3", "py"}
SAFE_PYTHON_MODULES = {
    "pytest",
    "py_compile",
    "compileall",
    "ruff",
    "mypy",
    "flake8",
    "black",
    "isort",
    "flask",
    "unittest",
    "json.tool",
    "pip",
}
SAFE_EXECUTABLES = {"pytest", "ruff", "mypy", "flake8", "black", "isort", "flask"}
LOCAL_WEB_VERBS = {"invoke-webrequest", "invoke-restmethod"}
SAFE_GIT = {"status", "diff", "log", "show", "branch", "rev-parse", "ls-files", "blame"}
LOCAL_HOSTS = ("localhost", "127.0.0.1", "[::1]")
_URL = re.compile(r"https?://([^/:\s'\"]+)", re.IGNORECASE)


@dataclass
class Classification:
    level: Level
    reasons: list[str] = field(default_factory=list)
    always_ask: bool = False  # the reason is on the always-ask list: auto mode must still ask

    def raise_to(self, level: Level, reason: str, always_ask: bool = False) -> None:
        order = {"safe": 0, "ask": 1, "blocked": 2}
        if order[level] > order[self.level]:
            self.level = level
        self.reasons.append(reason)
        self.always_ask = self.always_ask or always_ask


@dataclass
class ShellScope:
    workspace_root: Path
    original_repo: Path | None  # None in Mode B: there is no host repository
    cwd: Path
    readable_roots: list[Path] = field(default_factory=list)  # e.g. the app's venv (reading is fine)
    strict: bool = False  # Mode B (spec §6A.8): anything outside the workspace is blocked, not asked
    # Mode B: inside the workspace root only these folders count as the workspace; other files the user
    # already had in the project folder are outside it (D-211). None = the whole root (Mode A).
    own_folders: list[Path] | None = None


def classify(command: str, scope: ShellScope) -> Classification:
    result = Classification(level="safe")
    if re.search(r"-e(nc(odedcommand)?)?\s", command, re.IGNORECASE) and re.search(
        r"(powershell|pwsh)", command, re.IGNORECASE
    ):
        result.raise_to("blocked", "encoded PowerShell commands are not allowed")
    if _HIDDEN_SECRET_PATH.search(command) or _PROFILE_VARIABLE.search(command):
        # A path built from a variable, or a ".env" named inside a quoted string (python -c "open('.env')"),
        # is invisible to the per-argument checks below, and these files hold Forge's own keys.
        result.raise_to(
            "ask", "refers to a secret file or to the user's profile/Forge folder indirectly", always_ask=True
        )
    segments = split_segments(command)
    if not segments:
        result.raise_to("ask", "empty command")
    for segment in segments:
        _classify_segment(segment, scope, result)
    return result


def _classify_segment(tokens: list[str], scope: ShellScope, result: Classification) -> None:
    verb, args = _verb(tokens)
    if verb in BLOCKED_VERBS:
        result.raise_to("blocked", f"{verb}: {BLOCKED_VERBS[verb]}")
        return
    if verb in NESTED_SHELLS:
        result.raise_to(
            "ask", f"{verb} starts another shell whose commands can't be checked", always_ask=True
        )
    only_local_urls = all(_is_local_url(arg) for arg in args if _URL.search(arg))
    remote_protocol = verb in {"ssh", "scp", "ftp", "telnet"}
    if (verb in NETWORK_VERBS or any(_is_remote_url(arg) for arg in args)) and (
        remote_protocol or not only_local_urls
    ):
        result.raise_to("ask", "network access outside this machine", always_ask=True)
    if verb == "git":
        sub = args[0].lower() if args else ""
        if sub == "push":
            result.raise_to("blocked", "git push is never run by Forge")
        elif sub not in SAFE_GIT:
            result.raise_to("ask", f"git {sub} changes repository state")
    if any(_is_secret_file(arg) for arg in args):
        # read_file shows key names only; the shell would print the values (redaction only knows Forge's
        # own secrets and secret-shaped text, not every value in the app's .env).
        result.raise_to("ask", "touches a secret file (.env, key, certificate)", always_ask=True)
    writes = _write_targets(verb, args)
    for target in writes:
        _check_path(target, scope, result, writing=True)
    for arg in args:
        if _looks_like_path(arg) and arg not in writes:
            _check_path(arg, scope, result, writing=False)
    if _is_pip_install(verb, args):
        result.raise_to("ask", "installs packages", always_ask=True)
    elif verb in WRITE_VERBS or writes:
        # Even inside the workspace: shell writes bypass Forge's checkpoints, so they need approval.
        result.raise_to("ask", f"{verb} changes files")
    elif verb in READ_ONLY or verb in SAFE_EXECUTABLES or _is_safe_python(verb, args) or verb == "git":
        pass
    elif (
        verb in LOCAL_WEB_VERBS
        and args
        and all(_is_local_url(a) for a in args if _URL.search(a))
        and any(_URL.search(a) for a in args)
    ):
        pass  # smoke-testing the app this workspace runs
    else:
        result.raise_to("ask", f"'{verb}' is not on the allowlist")


def _check_path(raw: str, scope: ShellScope, result: Classification, writing: bool) -> None:
    text = raw.strip("'\"")
    if not text or text.startswith("-") or "://" in text:
        return
    candidate = real_path(Path(text) if ntpath.isabs(text) or Path(text).is_absolute() else scope.cwd / text)
    if scope.original_repo is not None and is_within(candidate, scope.original_repo):
        if writing:
            result.raise_to("blocked", f"writes into the original repository: {text}")
        return  # reading the original repository is allowed (read-only reference, spec §6.1)
    if is_within(candidate, scope.workspace_root) and (
        scope.own_folders is None or any(is_within(candidate, folder) for folder in scope.own_folders)
    ):
        return
    if not writing and any(is_within(candidate, root) for root in scope.readable_roots):
        return
    if scope.strict:
        result.raise_to("blocked", f"Mode B: outside the workspace: {text}")
        return
    result.raise_to(
        "ask", f"{'writes' if writing else 'reads'} outside the workspace: {text}", always_ask=True
    )


def _write_targets(verb: str, args: list[str]) -> list[str]:
    targets = []
    for index, arg in enumerate(args):
        if arg in (">", ">>", "2>", "2>>", "*>") and index + 1 < len(args):
            targets.append(args[index + 1])
        elif arg.startswith((">", "2>")) and len(arg.lstrip(">2*")) > 0:
            targets.append(arg.lstrip(">2*"))
    if verb in WRITE_VERBS:
        targets += [arg for arg in args if not arg.startswith("-") and not arg.startswith(">")]
    return [t for t in targets if t.lower() not in ("$null", "null")]


def _verb(tokens: list[str]) -> tuple[str, list[str]]:
    rest = list(tokens)
    while rest and rest[0] in ("&", "."):
        rest.pop(0)
    if not rest:
        return "", []
    head = rest[0].strip("'\"")
    name = ntpath.basename(head).lower()
    if name.endswith(".exe") and name not in BLOCKED_VERBS and name not in NETWORK_VERBS:
        name = name[: -len(".exe")]
    return ALIASES.get(name, name), rest[1:]


def _is_safe_python(verb: str, args: list[str]) -> bool:
    if verb not in PYTHON_NAMES:
        return False
    lowered = [arg.lower() for arg in args]
    if "-m" in lowered and lowered.index("-m") + 1 < len(lowered):
        module = lowered[lowered.index("-m") + 1]
        return module in SAFE_PYTHON_MODULES and not _is_pip_install("python", args)
    return False  # `python script.py` / `python -c` run arbitrary code: ask (auto mode allows)


def _is_pip_install(verb: str, args: list[str]) -> bool:
    lowered = [arg.lower() for arg in args]
    is_pip = verb in ("pip", "pip3") or (verb in PYTHON_NAMES and "pip" in lowered)
    return is_pip and any(word in lowered for word in ("install", "uninstall", "download"))


def _looks_like_path(arg: str) -> bool:
    text = arg.strip("'\"")
    # A leading "/" is a switch on Windows (cmd /c, findstr /i), so it doesn't make a path; "\x" does.
    rooted = re.match(r"^([A-Za-z]:[\\/]|\\\\|\.\.?[\\/]|~[\\/]|\\)", text)
    return bool(rooted) or ".." in text.split("\\") or ".." in text.split("/")


_SECRET_FILE = re.compile(
    r"(^|[\\/])(\.env(\.(?!example$|sample$|template$)[\w.-]+)?|[^\\/]+\.(pem|pfx|p12|key)|id_(rsa|ed25519|ecdsa)"
    r"|secrets[\\/].*)$",
    re.IGNORECASE,
)


# ".env" (not .env.example) after a path separator or quote anywhere in the command text.
_HIDDEN_SECRET_PATH = re.compile(
    r"[\\/'\"]\.env(?!\.(?:example|sample|template)\b)(?:\.[\w.-]+)?(?=$|[\\/'\"\s)\]};,])", re.IGNORECASE
)
# Where Forge keeps its folder and keys, reached through a variable instead of a literal path.
_PROFILE_VARIABLE = re.compile(
    r"\$env:(?:forge_env_file|forge_home|userprofile|home|homepath|appdata|localappdata)\b"
    r"|\$\{?home\b|%(?:forge_env_file|forge_home|userprofile|homepath|appdata|localappdata)%"
    r"|\bFORGE_ENV_FILE\b|\bFORGE_HOME\b",
    re.IGNORECASE,
)


def _is_secret_file(arg: str) -> bool:
    return bool(_SECRET_FILE.search(arg.strip("'\"").lstrip("@")))


def _is_remote_url(arg: str) -> bool:
    match = _URL.search(arg)
    return match is not None and not match.group(1).lower().startswith(LOCAL_HOSTS)


def _is_local_url(arg: str) -> bool:
    match = _URL.search(arg)
    return match is not None and match.group(1).lower().startswith(LOCAL_HOSTS)


def split_segments(command: str) -> list[list[str]]:
    """Splits on ; | && || and newlines (outside quotes) and tokenises each segment PowerShell-style.
    Script blocks and subexpressions are tokenised flat, which is conservative: their commands are
    still seen as arguments and paths."""
    segments: list[list[str]] = []
    tokens: list[str] = []
    current = ""
    quote = ""
    index = 0
    while index < len(command):
        char = command[index]
        if quote:
            if char == "`" and quote == '"' and index + 1 < len(command):
                current += command[index : index + 2]
                index += 2
                continue
            current += char
            if char == quote:
                quote = ""
        elif char in "'\"":
            quote = char
            current += char
        elif char == "`" and index + 1 < len(command):
            current += command[index + 1]
            index += 1
        elif char in " \t":
            if current:
                tokens.append(current)
                current = ""
        elif char in ";|\n\r{}()" or command.startswith("&&", index):
            # Braces and parentheses also end a segment, so the command inside a script block or
            # subexpression ("ForEach-Object { Remove-Item $_ }", "$(Remove-Item x)") is classified
            # as a command of its own instead of hiding as an argument.
            if current:
                tokens.append(current)
                current = ""
            if tokens:
                segments.append(tokens)
                tokens = []
            if command.startswith(("&&", "||"), index):
                index += 1
        else:
            current += char
        index += 1
    if current:
        tokens.append(current)
    if tokens:
        segments.append(tokens)
    return [segment for segment in segments if segment != ["$"]]
