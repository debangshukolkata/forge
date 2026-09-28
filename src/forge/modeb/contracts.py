"""User-pinned interface contracts (spec §6A.2A, D-129): a signature the user hands Forge upfront for a
seam (the LLM call wrapper, a file read/write helper, ...) so generated code is easy to retrofit into the
host repository by hand. Forge builds to a pinned contract instead of inventing its own for that seam.

Stored per host profile (not per workspace): a contract pinned on one requirement should be honoured, and
recommended, on the next one for the same host. `CONTRACTS.md` in the profile is the human-readable form;
`contracts.json` next to it is the structured form the tools read and write.
"""

from __future__ import annotations

import json
import re
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field, TypeAdapter

from forge.modeb.profile import HostProfile

ContractSource = Literal["user", "corrected"]  # user: pinned directly; corrected: Forge got it wrong twice+


class Contract(BaseModel):
    id: str
    seam: str  # short name, e.g. "llm_call_wrapper", "file_read_write"
    signature: str  # the exact signature/contract text the user gave
    note: str = ""  # why, or how it's used
    source: ContractSource = "user"
    pinned: str = Field(default_factory=lambda: datetime.now().isoformat(timespec="seconds"))
    revised: str = ""  # set when the user changes it mid-way (D-129)


_LIST = TypeAdapter(list[Contract])
_SEAM = re.compile(r"^[a-z][a-z0-9_]{0,63}$")


class ContractError(ValueError):
    pass


class ContractRegister:
    def __init__(self, profile: HostProfile) -> None:
        self.profile = profile
        self.path = profile.root / "contracts.json"

    def all(self) -> list[Contract]:
        return _LIST.validate_json(self.path.read_text(encoding="utf-8")) if self.path.exists() else []

    def for_seam(self, seam: str) -> Contract | None:
        return next((c for c in self.all() if c.seam == seam.strip().lower()), None)

    def pin(self, seam: str, signature: str, note: str, source: ContractSource = "user") -> Contract:
        """Sets (or replaces) the contract for a seam. Replacing an existing one is a revision (D-129:
        the user may change a pinned contract mid-way, after seeing generated code)."""
        seam = seam.strip().lower()
        if not _SEAM.fullmatch(seam):
            raise ContractError(
                f"Seam name {seam!r} should be short and lowercase, e.g. 'llm_call_wrapper' or "
                "'file_read_write'."
            )
        items = [c for c in self.all() if c.seam != seam]
        now = datetime.now().isoformat(timespec="seconds")
        existing = self.for_seam(seam)
        contract = Contract(
            id=existing.id if existing else f"C{len(self.all()) + 1}",
            seam=seam,
            signature=self.profile.clean(signature),
            note=self.profile.clean(note),
            source=source,
            pinned=existing.pinned if existing else now,
            revised=now if existing else "",
        )
        self._save([*items, contract])
        self.profile.record_change(f"contract {contract.id} ({seam}) {'revised' if existing else 'pinned'}")
        return contract

    def forget(self, seam_or_id: str) -> bool:
        items = self.all()
        kept = [c for c in items if c.seam != seam_or_id.strip().lower() and c.id != seam_or_id.upper()]
        if len(kept) == len(items):
            return False
        self._save(kept)
        self.profile.record_change(f"contract {seam_or_id} forgotten")
        return True

    def _save(self, items: list[Contract]) -> None:
        self.path.write_bytes(_LIST.dump_json(items, indent=1))
        self._write_markdown(items)

    def _write_markdown(self, items: list[Contract]) -> None:
        if not items:
            text = "# Interface contracts\n\nNone pinned yet: the seams below are Forge's own design.\n"
        else:
            lines = [
                "# Interface contracts",
                "",
                "Signatures the user pinned; Forge builds new code at these seams to match them exactly, "
                "so the result drops into the host with minimal changes.",
                "",
            ]
            for item in sorted(items, key=lambda c: c.seam):
                lines += [
                    f"## {item.seam} ({item.id})",
                    f"```\n{item.signature}\n```",
                    *([item.note] if item.note else []),
                    f"_pinned {item.pinned}" + (f", revised {item.revised}" if item.revised else "") + "_",
                    "",
                ]
            text = "\n".join(lines)
        (self.profile.root / "CONTRACTS.md").write_text(text, encoding="utf-8")

    def essentials(self) -> str:
        """For pinned context (§10.2): the active contracts, compact — empty string when there are none,
        so it adds nothing to the prompt on a profile that has never used this."""
        items = self.all()
        if not items:
            return ""
        lines = [f"- {c.seam}: `{c.signature}`" + (f" — {c.note}" if c.note else "") for c in items]
        return "Pinned interface contracts (build new code at these seams to match exactly):\n" + "\n".join(
            lines
        )


def read_markdown(profile: HostProfile) -> str:
    path = profile.root / "CONTRACTS.md"
    return path.read_text(encoding="utf-8") if path.exists() else ""


def dump(profile: HostProfile) -> str:
    return json.dumps([c.model_dump() for c in ContractRegister(profile).all()])
