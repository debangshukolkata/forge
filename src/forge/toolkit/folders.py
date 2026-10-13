"""Folder helpers for parallel builders (X2, D-305): kept in the toolkit so both the agent loop (which decides what may run side by side)
and the builder agent can use them."""

from __future__ import annotations


def clean_folder(folder: str) -> str:
    """A folder relative to the repository root with forward slashes, no './' parts and no trailing '/'; '' when it is unusable
    (empty, going up with '..', or an absolute or drive path)."""
    text = folder.replace(chr(92), "/").strip()
    parts = [p for p in text.split("/") if p and p != "."]
    if not parts or ".." in parts or ":" in parts[0] or text.startswith("/"):
        return ""
    return "/".join(parts)


def folders_disjoint(first: str, second: str) -> bool:
    """True when neither folder is the same as, or inside, the other: two builders there cannot write the same file."""
    a, b = clean_folder(first), clean_folder(second)
    if not a or not b:
        return False
    return not (a == b or a.startswith(b + "/") or b.startswith(a + "/"))
