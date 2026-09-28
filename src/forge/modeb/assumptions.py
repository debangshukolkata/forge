"""The assumption register (spec §6A.2): everything Forge had to assume about the host, with a confidence
and a one-line check the user can run inside the host. Surfaced at plan approval and delivered as
output/ASSUMPTIONS.md. Stored in .forge/assumptions.json (redacted)."""

from __future__ import annotations

import json
from typing import Literal

from pydantic import BaseModel, TypeAdapter

from forge.safety.redact import default_redactor
from forge.workspace.workspace import Workspace

Confidence = Literal["high", "medium", "low"]
Impact = Literal["high", "medium", "low"]


class Assumption(BaseModel):
    id: str
    text: str
    confidence: Confidence
    impact: Impact
    check: str  # how the user verifies it in the host (a command or a place to look)
    status: Literal["open", "confirmed", "wrong"] = "open"
    note: str = ""


_LIST = TypeAdapter(list[Assumption])


class AssumptionRegister:
    def __init__(self, workspace: Workspace) -> None:
        self.path = workspace.forge_dir / "assumptions.json"
        self.jail = workspace.jail

    def all(self) -> list[Assumption]:
        return _LIST.validate_json(self.path.read_text(encoding="utf-8")) if self.path.exists() else []

    def add(self, text: str, confidence: Confidence, impact: Impact, check: str) -> Assumption:
        items = self.all()
        assumption = Assumption(
            id=f"A{len(items) + 1}",
            text=default_redactor.redact(text),
            confidence=confidence,
            impact=impact,
            check=default_redactor.redact(check),
        )
        self._save([*items, assumption])
        return assumption

    def resolve(
        self, assumption_id: str, status: Literal["confirmed", "wrong"], note: str = ""
    ) -> Assumption:
        items = self.all()
        for item in items:
            if item.id == assumption_id:
                item.status, item.note = status, default_redactor.redact(note)
                self._save(items)
                return item
        raise KeyError(assumption_id)

    def _save(self, items: list[Assumption]) -> None:
        self.jail.check(self.path).write_bytes(_LIST.dump_json(items, indent=1))

    def markdown(self) -> str:
        items = self.all()
        if not items:
            return "# Assumptions\n\nNone: everything this code relies on was stated in the host profile.\n"
        lines = [
            "# Assumptions about the host",
            "",
            "Forge could not see the host, so the code relies on these. Please check each one in the host "
            "(the check is one line); tell Forge about any that are wrong and it will adapt the code.",
            "",
            "| ID | Assumption | Confidence | Impact | How to check | Status |",
            "|---|---|---|---|---|---|",
        ]
        for item in items:
            status = item.status + (f" ({item.note})" if item.note else "")
            lines.append(
                f"| {item.id} | {_cell(item.text)} | {item.confidence} | {item.impact} | "
                f"{_cell(item.check)} | {status} |"
            )
        return "\n".join(lines) + "\n"

    def summary_for_plan(self) -> str:
        open_items = [a for a in self.all() if a.status == "open"]
        if not open_items:
            return ""
        return "Open assumptions about the host:\n" + "\n".join(
            f"- {a.id} [{a.impact} impact, {a.confidence} confidence] {a.text} — check: {a.check}"
            for a in open_items
        )


def _cell(text: str) -> str:
    return text.replace("|", "\\|").replace("\n", " ")


def dump(workspace: Workspace) -> str:
    return json.dumps([a.model_dump() for a in AssumptionRegister(workspace).all()])
