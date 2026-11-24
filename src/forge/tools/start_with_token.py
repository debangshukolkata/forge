"""`start_with_token`: starts the application with the fresh token DebCraft signs in for (D-648, the user, 2026-11-24).

An application under test sometimes calls the dev environment itself (its file service, for example). A token pasted
into app.env ends after a while and reaches every command. Here the user approves one command of one project on a red
card; that command, and nothing else, gets the token of one environment in one variable. The model never sees it, and
it is masked in every output. The approval is kept in DebCraft Home, where no command of the model can write it; a
changed command asks again."""

from __future__ import annotations

import hashlib
import json
import os
import re
from pathlib import Path
from typing import Any

from pydantic import Field

from forge.config import forge_home
from forge.errors import ConfigError
from forge.home_layout import data_path
from forge.toolkit import field_log
from forge.toolkit.app_keys import is_debcrafts_own
from forge.toolkit.app_logins import LOGINS_FILE, EnvLogin, TokenStore, load_logins
from forge.toolkit.background import StartBackground
from forge.toolkit.base import ToolContext, ToolResult
from forge.tools.app_login import ensure_token

APPROVALS = "app_tokens.json"
VARIABLE = re.compile(r"[A-Z][A-Z0-9_]{2,63}")
APPROVE = "Give it the token"
# the variables that decide how the program itself runs: never replaced by a token
RESERVED = {
    "PATH",
    "PYTHONPATH",
    "PYTHONHOME",
    "NODE_OPTIONS",
    "HOME",
    "USERPROFILE",
    "TEMP",
    "TMP",
    "COMSPEC",
}


def _project(context: ToolContext) -> str:
    return hashlib.sha256(os.path.normcase(str(context.workspace.root.resolve())).encode()).hexdigest()[:16]


def _load(home: Path) -> dict[str, list[str]]:
    try:
        data = json.loads(data_path(home, APPROVALS).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return data if isinstance(data, dict) else {}


def _save(home: Path, data: dict[str, list[str]]) -> None:
    target = data_path(home, APPROVALS)
    target.parent.mkdir(parents=True, exist_ok=True)
    scratch = target.with_suffix(".tmp")
    scratch.write_text(json.dumps(data), encoding="utf-8")
    scratch.replace(target)


def forget_approvals(context: ToolContext, home: Path | None = None) -> bool:
    """`/app-keys off`: the commands of this project are asked about again."""
    base = home or forge_home()
    data = _load(base)
    if data.pop(_project(context), None) is None:
        return False
    _save(base, data)
    return True


class StartWithToken(StartBackground):
    name = "start_with_token"
    description = (
        "start_background for an application that itself calls the dev (or SIT) environment and needs that "
        "environment's sign-in token: DebCraft signs in, and the started program, and only it, gets a fresh token in "
        "the environment variable you name. You never see it. The user approves the exact command once per project on "
        "a card; a changed command asks again. The token ends after a while: start the program again with this tool "
        "for a new one. Not for calling an API yourself (http_request signs in by itself), and not needed when the "
        "application only passes on the token of its caller. Never make the program print, log or save the token."
    )

    class Args(StartBackground.Args):
        environment: str = Field(default="dev", description="A name in app_logins.yaml, such as dev.")
        variable: str = Field(
            description="The variable the program reads the token from, e.g. DEV_FILE_TOKEN."
        )
        reason: str = Field(description="One line: which call of the program needs it (file and line).")

    def summary(self, args: Any) -> str:
        return f"start '{args.name}' with the {args.environment} token in {args.variable}: {args.command}"

    async def run(self, args: Any, context: ToolContext) -> ToolResult:
        if context.workspace is None or context.shell is None or context.background is None:
            return ToolResult(ok=False, content="No application can be started here.")
        if not VARIABLE.fullmatch(args.variable) or args.variable in RESERVED:
            return ToolResult(
                ok=False, content=f"{args.variable[:40]!r} cannot be used as the variable's name."
            )
        if is_debcrafts_own(args.variable):
            return ToolResult(
                ok=False, content=f"{args.variable} is one of DebCraft's own names; use another."
            )
        home = forge_home()
        try:
            login = load_logins(home).get(args.environment)
        except ConfigError as error:
            return ToolResult(ok=False, content=str(error))
        if login is None:
            return ToolResult(ok=False, content=f"No environment {args.environment!r} in {LOGINS_FILE}.")
        if refused := await self._approve(args, login, context, home):
            return refused
        ensured = await ensure_token(login, home, ask=context.ask_user)
        if not ensured.token:
            return ToolResult(ok=False, content=f"No {login.name} token: {ensured.message}")
        result = await self.start(args, context, {args.variable: ensured.token})
        left = (TokenStore(home).remaining(login.token_name) or 0) // 60
        field_log.write(
            "app_token_given", home, env=login.name, variable=args.variable, ok=result.ok, minutes=left
        )
        if result.ok:
            result.content += f"\n[{args.variable} holds the {login.name} token in this program only, for about {left} more minutes]"
        return result

    async def _approve(
        self, args: Any, login: EnvLogin, context: ToolContext, home: Path
    ) -> ToolResult | None:
        assert context.shell is not None
        cwd = context.shell.resolve_cwd(args.cwd)
        text = "\n".join([login.name, login.host, login.token_name, args.variable, str(cwd), args.command])
        key = hashlib.sha256(text.encode()).hexdigest()
        project = _project(context)
        if key in _load(home).get(project, []):
            return None
        if context.confirm_danger is None:
            return ToolResult(ok=False, content="Nobody can approve this here. Go on without it and say so.")
        approved, note = await context.confirm_danger(
            f"Give this program your {login.name} sign-in token?",
            f"The program:\n\n    {args.command}\n\nin {context.shell.display(cwd)}\n\n"
            f"Needed for: {args.reason[:300]}\n\nIt gets the token for {login.host} in `{args.variable}` and can do "
            "there what you can do. It runs code DebCraft may have changed. The token is not shown to the model and "
            "is masked in every output, but the program could store it or send it elsewhere. Asked again when the "
            "command changes; `/app-keys off` takes it back.",
            APPROVE,
        )
        if not approved:
            return ToolResult(
                ok=False,
                content=f"The user did not agree{f' ({note})' if note else ''}. Go on without the token and say what "
                "could not be checked.",
            )
        data = _load(home)
        data.setdefault(project, []).append(key)
        _save(home, data)
        return None
