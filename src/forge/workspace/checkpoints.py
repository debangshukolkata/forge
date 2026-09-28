"""Checkpoints for /undo and /rewind (spec §8, M2).

Each checkpoint stores the content of the files it changed *as they were before the change* (only
those files), so undoing is copying them back. Works without git.

Layout: .forge/checkpoints/index.json and .forge/checkpoints/<id>/files/<repo-relative path>
"""

from __future__ import annotations

import shutil
from datetime import UTC, datetime
from pathlib import Path

from pydantic import BaseModel, Field

from forge.safety.paths import WriteJail


class CheckpointFile(BaseModel):
    existed: bool  # False: the file was created in this checkpoint, so undo deletes it


class Checkpoint(BaseModel):
    id: int
    label: str
    created: str
    files: dict[str, CheckpointFile] = Field(default_factory=dict)


class CheckpointIndex(BaseModel):
    next_id: int = 1
    checkpoints: list[Checkpoint] = Field(default_factory=list)


class CheckpointStore:
    def __init__(self, directory: Path, files_root: Path, jail: WriteJail) -> None:
        self.directory = directory
        self.files_root = files_root  # the workspace's repo/ folder
        self.jail = jail
        self._index_path = directory / "index.json"

    def all(self) -> list[Checkpoint]:
        return self._load().checkpoints

    def create(self, label: str, paths: list[str]) -> Checkpoint:
        """Saves the current content of `paths` (repo-relative) before they are changed."""
        index = self._load()
        checkpoint = Checkpoint(
            id=index.next_id, label=label, created=datetime.now(UTC).isoformat(timespec="seconds")
        )
        for relative in paths:
            source = self.files_root / relative
            checkpoint.files[relative] = CheckpointFile(existed=source.exists())
            if source.exists():
                saved = self.jail.check(self._saved_path(checkpoint.id, relative))
                saved.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(source, saved)
        index.checkpoints.append(checkpoint)
        index.next_id += 1
        self._save(index)
        return checkpoint

    def undo(self) -> Checkpoint | None:
        """Restores the files of the latest checkpoint and removes it. None if there is nothing to undo."""
        index = self._load()
        if not index.checkpoints:
            return None
        checkpoint = index.checkpoints.pop()
        self._restore(checkpoint)
        self._save(index)
        return checkpoint

    def rewind(self, checkpoint_id: int) -> list[Checkpoint]:
        """Undoes every checkpoint from the latest back to (and including) checkpoint_id."""
        if not any(cp.id == checkpoint_id for cp in self.all()):
            raise ValueError(f"No checkpoint with id {checkpoint_id}")
        undone = []
        while self.all() and self.all()[-1].id >= checkpoint_id:
            checkpoint = self.undo()
            if checkpoint is not None:
                undone.append(checkpoint)
        return undone

    def _restore(self, checkpoint: Checkpoint) -> None:
        for relative, info in checkpoint.files.items():
            target = self.jail.check(self.files_root / relative)
            if info.existed:
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(self._saved_path(checkpoint.id, relative), target)
            elif target.exists():
                target.unlink()
        shutil.rmtree(self.jail.check(self.directory / f"{checkpoint.id:04d}"), ignore_errors=True)

    def _saved_path(self, checkpoint_id: int, relative: str) -> Path:
        return self.directory / f"{checkpoint_id:04d}" / "files" / relative

    def _load(self) -> CheckpointIndex:
        if not self._index_path.exists():
            return CheckpointIndex()
        return CheckpointIndex.model_validate_json(self._index_path.read_text(encoding="utf-8"))

    def _save(self, index: CheckpointIndex) -> None:
        path = self.jail.check(self._index_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(index.model_dump_json(indent=1), encoding="utf-8")
