"""A value in an API's answer goes to the project's commands under a name, and never to the model (D-611).

Some things do not work from a developer's machine (the secret store, a key service) but the development
instance can hand the value out through its API. The user does this by hand: call the API, copy the secret,
pass it to the code. For DebCraft the copy step must not go through the model (safety invariant 3), so
`http_request` takes `keep_secret`: for each variable name the path of the field in the JSON answer. The value
is taken out of the answer before the model sees it, masked everywhere from then on, and set in the environment
of the commands of this session after the user agreed once per name and project. It is kept in memory only.
"""

from __future__ import annotations

import json
import re
from typing import Any

from forge.safety.redact import default_redactor
from forge.toolkit.app_keys import DEFAULT_TOKEN_NAMES, is_debcrafts_own
from forge.toolkit.base import ToolContext
from forge.tools.interaction import OptionSpec

NAMES_FILE = (
    "kept_secret_names.json"  # in the project's .forge folder: names the user agreed to, never a value
)
NAME = re.compile(r"^[A-Z][A-Z0-9_]{1,80}$")
ALLOW = "Allow"
REFUSE = "Do not allow"


def check_names(wanted: dict[str, str]) -> str:
    """Why this `keep_secret` cannot be used, or an empty string."""
    for name, path in wanted.items():
        if not NAME.match(name):
            return (
                "`keep_secret` maps a variable NAME (upper case letters, digits and _) to the path of a field"
            )
        if is_debcrafts_own(name) or name in DEFAULT_TOKEN_NAMES:
            return f"{name} is one of DebCraft's own names and cannot be set this way; choose the application's name"
        if not path.strip():
            return f"`keep_secret` needs the path of the field for {name}, for example `secret.secretValue`"
    return ""


def _find(parsed: Any, path: str) -> tuple[Any, str]:
    """The value at a dotted path (`data.items.0.value`), or what is there instead where the path ends."""
    current = parsed
    walked: list[str] = []
    for part in [piece for piece in path.strip().split(".") if piece]:
        if isinstance(current, dict) and part in current:
            current = current[part]
        elif isinstance(current, list) and part.isdigit() and int(part) < len(current):
            current = current[int(part)]
        else:
            here = ".".join(walked) or "the top"
            there = (
                f"fields {', '.join(map(str, list(current)[:30]))}"
                if isinstance(current, dict)
                else f"a list of {len(current)}"
                if isinstance(current, list)
                else "a plain value"
            )
            return None, f"no `{part}` at {here} ({there})"
        walked.append(part)
    if isinstance(current, dict | list) or current is None:
        return None, "the path ends at an object, a list or null: name the field that holds the value"
    return current, ""


def _agreed(context: ToolContext) -> list[str]:
    try:
        data = json.loads((context.workspace.forge_dir / NAMES_FILE).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return []
    return [name for name in data if isinstance(name, str)] if isinstance(data, list) else []


async def keep_from_answer(
    wanted: dict[str, str], parsed: Any, host: str, context: ToolContext
) -> tuple[list[str], list[tuple[str, str]]]:
    """Takes the wanted values out of a JSON answer. Returns the lines to tell the model (names only) and the
    (value, name) pairs to blank in the answer. Every value found is masked from now on, whether or not the
    user lets commands have it."""
    found: dict[str, str] = {}
    lines: list[str] = []
    for name, path in wanted.items():
        value, problem = _find(parsed, path)
        if problem:
            lines.append(f"{name} was not kept: {problem}.")
            continue
        found[name] = str(value)
        default_redactor.register(found[name], name)  # before anything of the answer leaves this function
    hidden = [(value, name) for name, value in found.items()]
    shell = context.shell
    if not found:
        return lines, hidden
    if shell is None or context.workspace is None:
        return [*lines, "Nothing was kept: there are no commands to hand a value to here."], hidden
    agreed = _agreed(context)
    asking = [name for name in found if name not in agreed]
    if asking:
        if context.ask_user is None:
            return [*lines, f"{', '.join(asking)} not kept: the user cannot be asked here."], hidden
        answer = await context.ask_user(
            f"Let the commands of this project use {', '.join(asking)}, fetched from {host}?",
            f"DebCraft called {host} and the answer holds the value(s). They go into the environment of the "
            "commands DebCraft runs in this project, for this session only; DebCraft (the model) never sees "
            "them, they are masked in every output and are not written to a file.",
            [
                OptionSpec(label=ALLOW, description="Commands of this project get these values."),
                OptionSpec(label=REFUSE, description="The values are dropped."),
            ],
            ALLOW,
        )
        if not answer.strip().removeprefix("The user chose:").strip().startswith(ALLOW):
            return [*lines, f"The user did not let commands use {', '.join(asking)}; dropped."], hidden
        target = context.workspace.jail.check(context.workspace.forge_dir / NAMES_FILE)
        target.write_text(json.dumps(sorted({*agreed, *asking})), encoding="utf-8")
    shell.kept_env.update(found)
    first = next(iter(found))
    lines.append(
        f"Kept for the commands of this session: {', '.join(found)} (Python: os.environ['{first}']). You do not "
        "see the values and must not print them or write them into a file. A process that is already running "
        "does not have them: stop it and start it again. They are gone when the session ends: make the call "
        "again then."
    )
    return lines, hidden


def blank(text: str, hidden: list[tuple[str, str]]) -> str:
    """The answer without the kept values, also where JSON wrote them with escapes."""
    for value, name in hidden:
        marker = f"[kept as {name}]"
        text = text.replace(value, marker).replace(json.dumps(value)[1:-1], marker)
    return text
