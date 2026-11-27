"""A delivered file copied into the user's repository, on the user's click only (D-674).

Safety invariant 1 says DebCraft never writes to the user's original repository. The user's one exception (2026-11-27):
a click in a red card of the web app replaces one file there with the delivered one. Nothing the model can call reaches
this module: the agent loop has no tool for it, the web route needs the server token and the signed-in user's cookie,
and a copy needs the one-time code of the card that showed the command. The replaced file is kept first, so the copy
can be undone; Mode B has no repository and never copies.

The delivered bytes are the copy's without its temporary changes (WF2), as in the output folder."""

from __future__ import annotations

import difflib
import hashlib
import json
import os
import time
from dataclasses import dataclass
from pathlib import Path

from forge.errors import ForgeError
from forge.safety.paths import resolve_inside
from forge.workspace.output import _decoded, changes_of, delivered_bytes, repository_state
from forge.workspace.temporary_edits import TemporaryEdits
from forge.workspace.workspace import Workspace

COPIES = "repo_copies"  # under .forge: one folder per copy, with the replaced file and what was written


class RepoCopyError(ForgeError):
    """A file that cannot be copied into the user's repository from this card."""


@dataclass(frozen=True)
class CopyPlan:
    relative: str
    source: Path  # the file in the workspace copy
    target: Path  # the file in the user's repository
    status: str  # "added" or "modified"
    target_exists: bool
    state: str  # repository_state: "same", "applied", "differs" or "missing"
    edited_lines: int  # lines the user changed in the repository since the project began (0: none)
    temporary: bool  # the copy holds temporary changes that are not delivered

    @property
    def command(self) -> str:
        """The same copy as a PowerShell line, so the user sees exactly what happens."""
        return f'Copy-Item -LiteralPath "{self.source}" -Destination "{self.target}" -Force'


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _changed_lines(before: str, after: str) -> int:
    diff = difflib.unified_diff(before.splitlines(), after.splitlines(), lineterm="", n=0)
    return sum(1 for line in diff if line[:1] in "+-" and not line.startswith(("+++", "---")))


def plan_copy(workspace: Workspace, relative: str) -> CopyPlan:
    """What a copy of this file would do, or RepoCopyError saying why it cannot be copied from here."""
    if workspace.mode_b or not workspace.info.repo_path:
        raise RepoCopyError("This project has no original repository to copy into.")
    relative = relative.strip().replace("\\", "/").lstrip("/")
    if not relative or workspace.is_secret(relative):
        raise RepoCopyError("This file is not copied from here.")
    change = next((c for c in changes_of(workspace, {relative}) if c.path == relative), None)
    if change is None:
        raise RepoCopyError("DebCraft has not changed this file: there is nothing to copy.")
    if change.secret:
        raise RepoCopyError("This file is not copied from here.")
    if change.status == "deleted":
        raise RepoCopyError("DebCraft deleted this file in its copy; delete it in your repository yourself.")
    repo_root = Path(workspace.info.repo_path)
    target = resolve_inside(repo_root, relative)
    source = resolve_inside(workspace.repo_dir, relative)
    state = repository_state(workspace, change) or "differs"
    edited = 0
    if target.is_file() and state not in (
        "same",
        "applied",
    ):  # the user's own copy of the change is not an edit
        baseline = workspace.forge_dir / "baseline" / relative
        before = baseline if baseline.is_file() else None
        try:
            if change.status == "added":
                edited = max(
                    1, len(_decoded(target).splitlines())
                )  # a file of that name appeared there since
            elif before is not None and before.read_bytes() != target.read_bytes():
                edited = max(1, _changed_lines(_decoded(before), _decoded(target)))
        except ValueError:  # a binary file: it differs, but has no lines
            edited = 1
    return CopyPlan(
        relative=relative,
        source=source,
        target=target,
        status=change.status,
        target_exists=target.is_file(),
        state=state,
        edited_lines=edited,
        temporary=bool(TemporaryEdits(workspace).active(relative)),
    )


def copy_to_repository(workspace: Workspace, plan: CopyPlan) -> str:
    """Writes the delivered file into the repository after keeping what was there; returns the copy's id for undo."""
    data, _ = delivered_bytes(workspace, plan.relative, plan.source.read_bytes(), TemporaryEdits(workspace))
    copy_id = time.strftime("%Y%m%d-%H%M%S") + f"-{_sha(plan.relative.encode())[:8]}"
    folder = workspace.forge_dir / COPIES / copy_id
    folder.mkdir(parents=True, exist_ok=False)
    existed = plan.target.is_file()
    if existed:
        (folder / "replaced").write_bytes(plan.target.read_bytes())
    record = {
        "relative": plan.relative,
        "target": str(plan.target),
        "existed": existed,
        "written": _sha(data),
        "at": time.time(),
    }
    (folder / "record.json").write_text(json.dumps(record), encoding="utf-8")
    plan.target.parent.mkdir(parents=True, exist_ok=True)
    temporary = plan.target.with_name(plan.target.name + ".debcraft-copy")
    temporary.write_bytes(data)
    os.replace(temporary, plan.target)  # one step: the repository never holds half a file
    return copy_id


def undo_copy(workspace: Workspace, copy_id: str) -> str:
    """Puts back what the copy replaced (or removes a file it added); returns the file's relative path."""
    if not copy_id.replace("-", "").isalnum():
        raise RepoCopyError("Unknown copy.")
    folder = workspace.forge_dir / COPIES / copy_id
    try:
        record = json.loads((folder / "record.json").read_text(encoding="utf-8"))
    except (OSError, ValueError) as error:
        raise RepoCopyError("Unknown copy.") from error
    target = resolve_inside(Path(workspace.info.repo_path), record["relative"])
    if not target.is_file() or _sha(target.read_bytes()) != record["written"]:
        raise RepoCopyError("The file in your repository changed after the copy; it is left as it is.")
    if record["existed"]:
        temporary = target.with_name(target.name + ".debcraft-copy")
        temporary.write_bytes((folder / "replaced").read_bytes())
        os.replace(temporary, target)
    else:
        target.unlink()
    (folder / "record.json").rename(folder / "undone.json")
    return str(record["relative"])
