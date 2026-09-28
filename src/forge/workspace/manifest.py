"""The baseline manifest: what every copied file looked like before Forge touched it (spec §6.1 step 4)."""

from __future__ import annotations

import hashlib
from datetime import UTC, datetime
from pathlib import Path

from pydantic import BaseModel

from forge.workspace.text_format import FileFormat


class ManifestEntry(BaseModel):
    sha256: str
    size: int
    mtime: float
    format: FileFormat
    secret: bool = False


class BaselineManifest(BaseModel):
    created: str
    files: dict[str, ManifestEntry]  # repository-root-relative POSIX path -> entry

    @classmethod
    def empty(cls) -> BaselineManifest:
        return cls(created=datetime.now(UTC).isoformat(timespec="seconds"), files={})

    def save(self, path: Path) -> None:
        path.write_text(self.model_dump_json(indent=1), encoding="utf-8")

    @classmethod
    def load(cls, path: Path) -> BaselineManifest:
        return cls.model_validate_json(path.read_text(encoding="utf-8"))


def sha256_of(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()
