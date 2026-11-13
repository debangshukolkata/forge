"""How this project was run before (D-597): the tools record it themselves, so a new session or a new conversation does
not start over. A reopened project began with a model that had forgotten the command that started the application
and the call that reached its agent, although the files, the copied rows and the settings were all still there.

What is kept, in `<project>/.forge/run_notes.json` (shared by all conversations of the project): the processes
that were started and reached their ready state (command, folder, port, the NAMES of the settings given to it) and the
HTTP calls that worked (method, address without query string, a short body, the NAME of the token variable). Never a
secret value: command lines and bodies pass the redactor, and only names of settings are stored."""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

from forge.safety.redact import default_redactor
from forge.workspace.workspace import Workspace

NOTES_FILE = "run_notes.json"
MAX_STARTS = 6
MAX_CALLS = 8
BODY_CHARS = 300
COMMAND_CHARS = 400
VERSION = 1


def _today() -> str:
    return time.strftime("%Y-%m-%d")


class RunNotes:
    def __init__(self, workspace: Workspace) -> None:
        self.workspace = workspace
        self.path = workspace.forge_dir / NOTES_FILE

    def load(self) -> dict[str, Any]:
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return {"version": VERSION, "starts": [], "calls": []}
        if not isinstance(data, dict) or data.get("version") != VERSION:
            return {"version": VERSION, "starts": [], "calls": []}
        data.setdefault("starts", [])
        data.setdefault("calls", [])
        return data

    def _save(self, data: dict[str, Any]) -> None:
        target = self.workspace.jail.check(self.path)
        target.parent.mkdir(parents=True, exist_ok=True)
        scratch = target.with_name(target.name + ".tmp")
        scratch.write_text(json.dumps(data, indent=1, ensure_ascii=False), encoding="utf-8")
        scratch.replace(target)

    def record_start(
        self, name: str, command: str, cwd: str | None, port: int | None, setting_names: list[str]
    ) -> None:
        """A background process that reached its ready state; the same name replaces the earlier note."""
        data = self.load()
        entry = {
            "name": name,
            "command": default_redactor.redact(command)[:COMMAND_CHARS],
            "cwd": cwd or "",
            "port": port,
            "settings": sorted(setting_names)[:20],
            "at": _today(),
        }
        data["starts"] = [*[e for e in data["starts"] if e.get("name") != name][-(MAX_STARTS - 1) :], entry]
        self._save(data)

    def record_call(self, method: str, url: str, body: Any, token_env: str, status: int) -> None:
        """An HTTP call that worked (a status below 400); the same method and address replace the earlier note."""
        address = url.split("?", 1)[0]
        text = ""
        if body not in (None, "", {}):
            text = default_redactor.redact(json.dumps(body, ensure_ascii=False, default=str))[:BODY_CHARS]
        data = self.load()
        entry = {
            "method": method,
            "url": address,
            "body": text,
            "token_env": token_env,
            "status": status,
            "at": _today(),
        }
        kept = [e for e in data["calls"] if (e.get("method"), e.get("url")) != (method, address)]
        data["calls"] = [*kept[-(MAX_CALLS - 1) :], entry]
        self._save(data)

    def render(self) -> str | None:
        data = self.load()
        lines: list[str] = []
        for start in data["starts"]:
            where = f" in {start['cwd']}" if start.get("cwd") else ""
            port = f", port {start['port']}" if start.get("port") else ""
            given = (
                f"; settings it was given: {', '.join(start['settings'])}" if start.get("settings") else ""
            )
            lines.append(
                f"- Started '{start['name']}' with `{start['command']}`{where}{port}{given} ({start['at']})."
            )
        for call in data["calls"]:
            token = f", token from {call['token_env']}" if call.get("token_env") else ""
            body = f" with {call['body']}" if call.get("body") else ""
            lines.append(
                f"- Worked: {call['method']} {call['url']}{body}{token} (status {call['status']}, {call['at']})."
            )
        if not lines:
            return None
        return (
            "Recorded by DebCraft itself in earlier sessions of this project (names only, never values). Start the "
            "application the same way and repeat the call before looking for another way; if it no longer works, "
            "say what changed.\n" + "\n".join(lines)
        )


def notes_path(root: Path) -> Path:
    return root / ".forge" / NOTES_FILE
