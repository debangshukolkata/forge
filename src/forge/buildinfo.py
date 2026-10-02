"""Which Forge build is this (D-153)? The package version never changes between commits, so an installed copy
can't be told apart from a newer one. The build id is a short hash of the package's own source files, so it
is the same for any copy of the same code, with or without a .git folder, and can be recomputed from any
commit."""

from __future__ import annotations

import hashlib
from functools import lru_cache
from pathlib import Path

import forge

HASH_CHARS = 10


@lru_cache(maxsize=1)
def build_id() -> str:
    root = Path(forge.__file__).resolve().parent
    digest = hashlib.sha256()
    for path in sorted(root.rglob("*.py")):
        if "__pycache__" in path.parts:
            continue
        digest.update(path.relative_to(root).as_posix().encode())
        # Normalise line endings so a CRLF checkout and an LF zip of the same commit agree.
        digest.update(path.read_bytes().replace(b"\r\n", b"\n"))
    return digest.hexdigest()[:HASH_CHARS]


def describe() -> str:
    return f"forge {forge.__version__} (build {build_id()})"
