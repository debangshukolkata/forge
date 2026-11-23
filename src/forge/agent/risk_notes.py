"""The "Noticed, not changed" list under an answer (D-410, D-641).

DebCraft writes the list itself from the scan. It used to ask the model to add it to its final reply, and the model
wrote the whole answer a second time. Each risk is shown once per project."""

from __future__ import annotations

import contextlib
import hashlib
import json
from typing import Any

from forge.safety.risk_scan import Risk, mentioned, scan_text, scannable
from forge.toolkit.base import ToolContext
from forge.workspace.workspace import Workspace

SHOWN_FILE = "risks_shown.json"
MAX_SHOWN = 30
HISTORY_NOTE = (
    "DebCraft showed the user this list under your answer, as 'Noticed, not changed'. Do not repeat it and do not "
    "fix any of it unless the user asks:\n"
)


def _load_shown(workspace: Workspace) -> set[str]:
    try:
        data = json.loads((workspace.forge_dir / SHOWN_FILE).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return set()
    return {str(key) for key in data} if isinstance(data, list) else set()


def _save_shown(workspace: Workspace, keys: set[str]) -> None:
    target = workspace.jail.check(workspace.forge_dir / SHOWN_FILE)
    target.parent.mkdir(parents=True, exist_ok=True)
    scratch = target.with_name(target.name + ".tmp")
    scratch.write_text(json.dumps(sorted(keys)), encoding="utf-8")
    scratch.replace(target)


def _key(risk: Risk) -> str:
    """Not the line number: an edit above moves it, and the same risk would be shown again."""
    return hashlib.sha256(f"{risk.path}|{risk.kind}|{risk.code}".encode()).hexdigest()[:20]


def _named_in(reply: str, risk: Risk) -> bool:
    name = risk.path.replace("\\", "/").rsplit("/", 1)[-1].lower()
    return name in reply.lower() and mentioned(risk, reply)


def take_new_risks(context: ToolContext, reply: str) -> list[Risk]:
    """The risks in the source files read that this project was not shown yet; they count as shown from here on."""
    workspace = context.workspace
    if workspace is None:
        return []
    shown = _load_shown(workspace)
    before = len(shown)
    fresh: list[Risk] = []
    for path in context.reads.paths():
        if not scannable(path):
            continue
        try:
            text = workspace.read_text(path)[0]
        except Exception:  # a file that cannot be read now is not worth a note
            continue
        for risk in scan_text(path, text):
            key = _key(risk)
            if key in shown:
                continue
            named = _named_in(reply, risk)
            if not named and len(fresh) >= MAX_SHOWN:
                continue  # left for a later turn
            shown.add(key)
            if not named:
                fresh.append(risk)
    if len(shown) > before:
        with contextlib.suppress(OSError):  # shown again next time; never a reason to fail the turn
            _save_shown(workspace, shown)
    return fresh


def risk_notice(risks: list[Risk]) -> dict[str, Any]:
    return {
        "kind": "risks_noticed",
        "text": "Noticed, not changed:\n" + "\n".join(f"- {risk.sentence()}" for risk in risks),
        "risks": [
            {
                "path": risk.path,
                "line": risk.line,
                "kind": risk.kind,
                "what": risk.what,
                "advice": risk.advice,
            }
            for risk in risks
        ],
    }


def history_note(risks: list[Risk]) -> str:
    return HISTORY_NOTE + "\n".join(f"- {risk.sentence()}" for risk in risks)
