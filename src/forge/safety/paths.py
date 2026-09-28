"""The write jail (spec §14.1): every write Forge makes is checked here first.

A path is writable only if its *real* location — after resolving `..`, symlinks and Windows
junctions — is inside one of the allowed roots and not inside a forbidden root (the user's
original repository). This module never writes anything itself.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

from forge.errors import ForgeError

# Windows paths at or beyond this length need the \\?\ prefix for most file APIs.
WINDOWS_PATH_LIMIT = 240


class JailViolationError(ForgeError):
    """A write was attempted outside the workspace, or inside the user's original repository."""


def real_path(path: Path | str) -> Path:
    # os.path.realpath follows symlinks and junctions on Windows too, even for paths that don't exist yet.
    return Path(os.path.realpath(os.path.abspath(path)))


def is_within(path: Path, root: Path) -> bool:
    candidate = os.path.normcase(str(path))
    base = os.path.normcase(str(root))
    return candidate == base or candidate.startswith(base.rstrip("\\/") + os.sep)


class WriteJail:
    def __init__(self, allowed_roots: list[Path], forbidden_roots: list[Path] | None = None) -> None:
        self.allowed_roots = [real_path(root) for root in allowed_roots]
        self.forbidden_roots = [real_path(root) for root in forbidden_roots or []]

    def check(self, path: Path | str) -> Path:
        """Returns the resolved path if writing to it is allowed, else raises JailViolationError."""
        resolved = real_path(path)
        for forbidden in self.forbidden_roots:
            if is_within(resolved, forbidden):
                raise JailViolationError(f"Refusing to write inside the original repository: {resolved}")
        if not any(is_within(resolved, root) for root in self.allowed_roots):
            raise JailViolationError(f"Refusing to write outside the workspace: {resolved}")
        return resolved


def resolve_inside(root: Path, relative: str) -> Path:
    """Joins a model- or user-supplied relative path onto root, rejecting anything that escapes it."""
    if not relative or Path(relative).is_absolute() or Path(relative).drive:
        raise JailViolationError(f"Expected a path relative to {root}, got: {relative!r}")
    candidate = real_path(root / relative)
    if not is_within(candidate, real_path(root)):
        raise JailViolationError(f"Path escapes {root}: {relative!r}")
    return candidate


def os_path(path: Path | str, force: bool = False) -> str:
    """The string to hand to OS file APIs: adds the \\\\?\\ prefix for long Windows paths
    (or always, with force=True, e.g. for a directory walk that may go deep)."""
    text = str(path)
    long_enough = force or len(text) >= WINDOWS_PATH_LIMIT
    if sys.platform == "win32" and long_enough and not text.startswith("\\\\?\\"):
        absolute = os.path.abspath(text)
        return "\\\\?\\UNC\\" + absolute[2:] if absolute.startswith("\\\\") else "\\\\?\\" + absolute
    return text
