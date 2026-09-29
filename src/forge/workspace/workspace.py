"""An open workspace (spec §6.2) and the single gate through which Forge changes files in it (§6.3).

Every write: jail check -> checkpoint (for /undo) -> copy-on-first-write baseline -> atomic write in the
file's original encoding/line endings -> change log entry (for CHANGES.md).
"""

from __future__ import annotations

import json
import os
import shutil
from datetime import UTC, datetime
from pathlib import Path
from typing import Literal

from pydantic import BaseModel

from forge.errors import ForgeError
from forge.safety.paths import WriteJail, os_path, resolve_inside
from forge.workspace.checkpoints import Checkpoint, CheckpointStore
from forge.workspace.copy_repo import CopyReport
from forge.workspace.ignore import IgnoreRules
from forge.workspace.manifest import BaselineManifest
from forge.workspace.nodeenv import NodeEnvironment
from forge.workspace.pyenv import PythonEnvironment
from forge.workspace.text_format import FileFormat, Newline, decode_text, detect_format, encode_text

WORKSPACE_FORMAT_VERSION = 1


class WorkspaceError(ForgeError):
    pass


class WorkspaceInfo(BaseModel):
    """Contents of .forge/workspace.json."""

    format_version: int = WORKSPACE_FORMAT_VERSION
    mode: Literal["A", "B"] = "A"
    name: str
    project: str = ""  # the project name the user gave (web UI / --project); "" for older workspaces
    repo_path: str
    app_subfolder: str
    created: str
    default_newline: Newline = "lf"
    python_env: PythonEnvironment | None = None
    node_env: NodeEnvironment | None = None
    copy_report: CopyReport = CopyReport()
    status: str = "created"


class Change(BaseModel):
    checkpoint: int
    op: Literal["write", "delete", "move"]
    path: str
    from_path: str | None = None
    reason: str = ""
    ts: str


class Workspace:
    def __init__(self, root: Path, info: WorkspaceInfo) -> None:
        self.root = root
        self.info = info
        # Mode B (spec §6A.1): project/ holds the deliverable (host-relative paths), _harness/ the stand-ins
        # that make it run here; there is no host repository at all.
        self.mode_b = info.mode == "B"
        self.repo_dir = root / ("project" if self.mode_b else "repo")
        self.harness_dir = root / "_harness"
        self.output_dir = root / "output"
        self.forge_dir = root / ".forge"
        self.app_dir = self.repo_dir / info.app_subfolder
        writable = [self.repo_dir, self.output_dir, self.forge_dir]
        if self.mode_b:
            writable.append(self.harness_dir)
        forbidden = [Path(info.repo_path)] if info.repo_path else []
        self.jail = WriteJail(writable, forbidden_roots=forbidden)
        self.checkpoints = CheckpointStore(self.forge_dir / "checkpoints", self.repo_dir, self.jail)
        self._manifest: BaselineManifest | None = None

    # --- persistence ---

    @property
    def manifest(self) -> BaselineManifest:
        if self._manifest is None:
            self._manifest = BaselineManifest.load(self.forge_dir / "baseline_manifest.json")
        return self._manifest

    def save_info(self) -> None:
        path = self.jail.check(self.forge_dir / "workspace.json")
        path.write_text(self.info.model_dump_json(indent=1), encoding="utf-8")

    @classmethod
    def open(cls, root: Path | str) -> Workspace:
        root = Path(root)
        info_path = root / ".forge" / "workspace.json"
        if not info_path.is_file():
            raise WorkspaceError(f"{root} is not a Forge workspace (no .forge/workspace.json)")
        return cls(root, WorkspaceInfo.model_validate_json(info_path.read_text(encoding="utf-8")))

    def ignore_rules(self) -> IgnoreRules:
        return IgnoreRules(self.repo_dir)

    # --- reading ---

    def path_of(self, relative: str) -> Path:
        normalised = relative.replace("\\", "/")
        if self.mode_b and (normalised == "_harness" or normalised.startswith("_harness/")):
            inside = normalised.removeprefix("_harness").lstrip("/")
            return resolve_inside(self.harness_dir, inside) if inside else self.harness_dir
        if (
            self.mode_b
            and normalised.lstrip("./").startswith("project/")
            and not (self.repo_dir / "project").is_dir()
        ):
            # Seen live: the model wrote everything to project/project/<pkg>/…, which was then delivered
            # under output/project/ and couldn't be imported by the host.
            raise WorkspaceError(
                f"{relative}: paths are already relative to project/ (the host's root). Drop the 'project/' "
                "prefix, e.g. 'claims_app/x.py', not 'project/claims_app/x.py'."
            )
        return resolve_inside(self.repo_dir, relative)

    def is_secret(self, relative: str) -> bool:
        entry = self.manifest.files.get(relative)
        return entry.secret if entry else self.ignore_rules().is_secret(relative)

    def read_text(self, relative: str) -> tuple[str, FileFormat]:
        data = Path(os_path(self.path_of(relative))).read_bytes()
        file_format = detect_format(data)
        if file_format.binary:
            raise WorkspaceError(f"{relative} is a binary file")
        return decode_text(data, file_format), file_format

    # --- writing (the only way Forge changes workspace files) ---

    def write_text(self, relative: str, text: str, reason: str = "") -> Checkpoint:
        target = self.jail.check(self.path_of(relative))
        if target.exists():
            file_format = detect_format(target.read_bytes())
            if file_format.binary:
                raise WorkspaceError(f"Refusing to overwrite binary file {relative} with text")
        else:
            file_format = FileFormat(newline="crlf" if self.info.default_newline == "crlf" else "lf")
        checkpoint = self.checkpoints.create(f"write {relative}", [relative])
        self._save_baseline(relative)
        self._atomic_write(target, encode_text(text, file_format))
        self._log(Change(checkpoint=checkpoint.id, op="write", path=relative, reason=reason, ts=_now()))
        return checkpoint

    def delete(self, relative: str, reason: str = "") -> Checkpoint:
        target = self.jail.check(self.path_of(relative))
        if not target.is_file():
            raise WorkspaceError(f"{relative} does not exist")
        checkpoint = self.checkpoints.create(f"delete {relative}", [relative])
        self._save_baseline(relative)
        target.unlink()
        self._log(Change(checkpoint=checkpoint.id, op="delete", path=relative, reason=reason, ts=_now()))
        return checkpoint

    def move(self, source: str, destination: str, reason: str = "") -> Checkpoint:
        source_path = self.jail.check(self.path_of(source))
        destination_path = self.jail.check(self.path_of(destination))
        if not source_path.is_file():
            raise WorkspaceError(f"{source} does not exist")
        if destination_path.exists():
            raise WorkspaceError(f"{destination} already exists")
        checkpoint = self.checkpoints.create(f"move {source} -> {destination}", [source, destination])
        self._save_baseline(source)
        destination_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(source_path, destination_path)
        self._log(
            Change(
                checkpoint=checkpoint.id,
                op="move",
                path=destination,
                from_path=source,
                reason=reason,
                ts=_now(),
            )
        )
        return checkpoint

    def undo(self) -> Checkpoint | None:
        checkpoint = self.checkpoints.undo()
        if checkpoint is not None:
            self._forget_changes({checkpoint.id})
        return checkpoint

    def rewind(self, checkpoint_id: int) -> list[Checkpoint]:
        undone = self.checkpoints.rewind(checkpoint_id)
        self._forget_changes({checkpoint.id for checkpoint in undone})
        return undone

    def changes(self) -> list[Change]:
        path = self.forge_dir / "changes.jsonl"
        if not path.exists():
            return []
        return [
            Change.model_validate(json.loads(line))
            for line in path.read_text(encoding="utf-8").splitlines()
            if line
        ]

    # --- internals ---

    def _save_baseline(self, relative: str) -> None:
        """Copy-on-first-write: keep the original of every pre-existing file Forge changes."""
        if relative not in self.manifest.files:
            return
        saved = self.jail.check(self.forge_dir / "baseline" / relative)
        source = self.path_of(relative)
        if not saved.exists() and source.exists():
            saved.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, saved)

    def _atomic_write(self, target: Path, data: bytes) -> None:
        target.parent.mkdir(parents=True, exist_ok=True)
        temporary = self.jail.check(target.with_name(target.name + ".forge-tmp"))
        temporary.write_bytes(data)
        os.replace(temporary, target)

    def _log(self, change: Change) -> None:
        path = self.jail.check(self.forge_dir / "changes.jsonl")
        with path.open("a", encoding="utf-8") as log:
            log.write(change.model_dump_json() + "\n")

    def _forget_changes(self, checkpoint_ids: set[int]) -> None:
        kept = [change for change in self.changes() if change.checkpoint not in checkpoint_ids]
        path = self.jail.check(self.forge_dir / "changes.jsonl")
        path.write_text("".join(change.model_dump_json() + "\n" for change in kept), encoding="utf-8")


def _now() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")
