"""`settings_file`: DebCraft reads and, with the user's approval, writes the user's own settings files (D-618).

`app_logins.yaml` says how to sign in to the user's dev and SIT sites and which hosts may receive their tokens;
`tunnels.yaml` holds a command DebCraft starts on the user's machine. Both are decisions only the user may make, so
DebCraft never writes them silently: it proposes the whole new file, the text is checked with the same parsers that
read it later, and the user approves exactly that text on a red card (nothing is remembered; the next change asks
again). The user's own words decide what goes in: the tool refuses a file that holds a secret, and the previous
file is kept beside it as `<name>.bak`. `config.yaml` is not here: DebCraft never changes its own configuration."""

from __future__ import annotations

import difflib
import os
import re
from pathlib import Path
from typing import Literal

from pydantic import Field

from forge.config import forge_home
from forge.db.tunnel import TUNNELS_FILE, parse_tunnels
from forge.errors import ConfigError
from forge.safety.redact import default_redactor
from forge.toolkit.app_logins import LOGINS_FILE, parse_logins
from forge.toolkit.base import Tool, ToolArgs, ToolContext, ToolResult

CHECKERS = {LOGINS_FILE: parse_logins, TUNNELS_FILE: parse_tunnels}
WHAT_IT_DOES = {
    LOGINS_FILE: "DebCraft signs in to these sites and sends the tokens to their hosts, and only to them",
    TUNNELS_FILE: "DebCraft starts this command on your computer when the development database is needed",
}
MAX_CHARS = 8000
NOTHING_CHANGED = "Nothing was changed."


def _path(name: str) -> Path:
    return forge_home() / name


TOKEN_KEYS = re.compile(r"\b\w*token\w*(?=\s*:)", re.IGNORECASE)


def _holds_secret(content: str) -> bool:
    """True when the redactor finds a secret value. The settings keys themselves (`token_name`, `token`,
    `warn_without_token`) have `token` in their names and would trip the redactor's "name = value" rule on every
    valid file, so they are set aside before the check: what is looked for is a value."""
    probe = TOKEN_KEYS.sub("kind", content)
    return default_redactor.redact(probe) != probe


def _current(name: str) -> str:
    try:
        return _path(name).read_text(encoding="utf-8")
    except OSError:
        return ""


def _card(name: str, content: str, reason: str, previous: str) -> str:
    """What the user sees before approving: where, why, what it lets DebCraft do, and the changes."""
    changes = "".join(
        difflib.unified_diff(
            previous.splitlines(keepends=True),
            content.splitlines(keepends=True),
            "now",
            "new",
            n=1,
        )
    )
    return (
        f"File: {_path(name)}\nWhy: {reason.strip() or 'not given'}\n"
        f"What the file does: {WHAT_IT_DOES[name]}.\n\n"
        + (f"The whole new file:\n\n{content}\n" if not previous.strip() else f"Changes:\n\n{changes}\n")
        + f"\nThe previous file is kept as {name}.bak."
    )


class SettingsFile(Tool):
    name = "settings_file"
    read_only = (
        True  # its approval is its own red card, shown with the exact text; the call needs no second prompt
    )
    description = (
        "Read or write the user's own settings files in DebCraft Home: `app_logins.yaml` (how to sign in to their dev and "
        "SIT sites: environments with login_url, token_name, token cookie or header, steps, check_url) and "
        "`tunnels.yaml` (the command that opens the tunnel to the development database). action `read` returns the "
        "file as it is. action `write` proposes the WHOLE new file in `content` (read it first and keep what is "
        "right) with a `reason`; the text is checked, the user sees what changes on a red card and approves it each "
        "time. Ask the user for anything you do not know (the address of the login page, the texts of the buttons): "
        "never invent an address or a command; an environment you cannot complete is left out of the file, not "
        "filled with guesses. Never put a token, password or key in these files: a file that holds one is refused. "
        "Use it when a call is refused for the file's content or the file is missing. Formats (do not search the web "
        "for them):\n"
        "app_logins.yaml:\n"
        "environments:\n"
        "  dev:                                  # any name\n"
        "    login_url: https://dev.example.com/app/login/\n"
        "    token_name: DEV_TOKEN               # the NAME the token is kept under\n"
        "    token: {cookie: access_token_cookie}   # or {header: authorization}; exactly one\n"
        "    steps:                              # click: button text; wait_url: part of the address that follows; pause: seconds\n"
        '      - click: "Sign in"\n'
        '      - wait_url: "uuid_key"\n'
        "    check_url: https://dev.example.com/app/api/me   # optional, same host as login_url\n"
        "    warn_without_token: true            # optional\n"
        "tunnels.yaml:\n"
        "tunnels:\n"
        "  dev:\n"
        '    command: [gcloud, compute, start-iap-tunnel, vm1, "4572", --local-host-port=localhost:9006]\n'
        "    port: 9006                          # the local port that must answer"
    )

    class Args(ToolArgs):
        action: Literal["read", "write"]
        file: Literal["app_logins.yaml", "tunnels.yaml"]
        content: str = Field(default="", description="For `write`: the whole new file.")
        reason: str = Field(default="", description="For `write`: why, in one sentence, for the user.")

    def summary(self, args: SettingsFile.Args) -> str:
        return f"settings_file {args.action} {args.file}"

    async def run(self, args: SettingsFile.Args, context: ToolContext) -> ToolResult:
        if context.workspace is None or context.workspace.mode_b:
            return ToolResult(
                ok=False, content="DebCraft's settings files are not available in this session."
            )
        if args.action == "read":
            text = _current(args.file)
            where = _path(args.file)
            return ToolResult(
                ok=True,
                content=text if text else f"{where} does not exist or is empty (nothing written yet).",
            )
        content = args.content.replace("\r\n", "\n")
        if not content.strip() or len(content) > MAX_CHARS:
            return ToolResult(
                ok=False,
                content=f"Give the whole new file in `content` (at most {MAX_CHARS} characters). {NOTHING_CHANGED}",
            )
        if _holds_secret(content):
            return ToolResult(
                ok=False,
                content="That text looks like it holds a secret (a token, key or password). These files hold "
                "addresses, names and steps only: tokens are kept by DebCraft in its own store. "
                f"{NOTHING_CHANGED}",
            )
        try:
            CHECKERS[args.file](content)
        except ConfigError as error:
            return ToolResult(ok=False, content=f"The file would not work: {error} {NOTHING_CHANGED}")
        if context.confirm_danger is None:
            return ToolResult(
                ok=False,
                content="The user cannot be asked here, and these files change only with their approval each "
                f"time. {NOTHING_CHANGED}",
            )
        previous = _current(args.file)
        if previous.replace("\r\n", "\n") == content:
            return ToolResult(ok=True, content=f"{args.file} already holds exactly this. {NOTHING_CHANGED}")
        approved, note = await context.confirm_danger(
            f"Write {args.file}?", _card(args.file, content, args.reason, previous), f"Write {args.file}"
        )
        if not approved:
            said = f" The user said: {note}" if note else ""
            return ToolResult(
                ok=False,
                content=f"The user did not approve this file. {NOTHING_CHANGED}{said} Do not ask again for the "
                "same text; ask the user what they want instead.",
            )
        target = _path(args.file)
        target.parent.mkdir(parents=True, exist_ok=True)
        if previous:
            target.with_name(target.name + ".bak").write_text(previous, encoding="utf-8")
        scratch = target.with_name(target.name + ".tmp")
        scratch.write_text(content, encoding="utf-8")
        os.replace(scratch, target)
        await context.emit("notice", {"kind": "settings_file", "text": f"Wrote {target} (approved by you)."})
        return ToolResult(
            ok=True,
            content=f"Approved by the user and written: {target} (the previous file is {target.name}.bak). "
            "It is read on every call: no restart is needed.",
        )
