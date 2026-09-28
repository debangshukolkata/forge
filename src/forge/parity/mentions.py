"""@-mentions and long pastes (spec §13B).

In a user message: `@path` includes a workspace file, `@path:10-80` a line range; `@image.png` (an image in
the workspace or a pasted path) is saved to .forge/inputs/ and attached; `@DBR-3`, `@REQ-0007`, `@L12` (or
`@lesson-12`) bring in Forge objects. A message longer than LONG_PASTE_CHARS is stored as a file in
.forge/inputs/ and referenced instead of being sent inline in full.
"""

from __future__ import annotations

import re
import shutil
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

from forge.errors import ForgeError
from forge.workspace.workspace import Workspace

MENTION = re.compile(r"(?<![\w@])@([A-Za-z]:[\\/][^\s]+|[\w./\\-]+(?::\d+-\d+)?)")
IMAGE_SUFFIXES = {".png", ".jpg", ".jpeg", ".gif", ".webp", ".bmp", ".tif", ".tiff"}
LONG_PASTE_CHARS = 8000
PREVIEW_CHARS = 1500
MAX_FILE_CHARS = 30_000


@dataclass
class Expanded:
    text: str
    images: list[Path] = field(default_factory=list)  # attached images (saved under .forge/inputs/)
    notes: list[str] = field(default_factory=list)  # what was resolved, for the UI


def expand(message: str, workspace: Workspace, lookup: dict[str, object] | None = None) -> Expanded:
    """lookup maps object kinds to callables: {"DBR": fn(id)->str|None, "REQ": ..., "L": ...}."""
    result = Expanded(text=message)
    stored = _store_long_paste(message, workspace)
    if stored is not None:
        preview = "\n".join(message.splitlines()[:40])[:PREVIEW_CHARS]  # a one-line paste is long too
        relative = stored.relative_to(workspace.root).as_posix()
        result.text = (
            f"{preview}\n\n[… the full pasted text ({len(message)} characters) is in {relative}; "
            "read it with read_file …]"
        )
        result.notes.append(f"long paste saved to {relative}")
    attachments: list[str] = []
    for token in dict.fromkeys(MENTION.findall(message)):
        block = _resolve(token, workspace, lookup or {}, result)
        if block:
            attachments.append(block)
    if attachments:
        result.text += "\n\n" + "\n\n".join(attachments)
    return result


def _resolve(token: str, workspace: Workspace, lookup: dict[str, object], result: Expanded) -> str | None:
    object_match = re.fullmatch(r"(DBR|REQ|L|lesson)-?(\d+)", token, re.IGNORECASE)
    if object_match:
        kind = object_match.group(1).upper()
        kind = "L" if kind == "LESSON" else kind
        getter = lookup.get(kind)
        ident = f"{kind}-{object_match.group(2)}" if kind != "L" else f"L{object_match.group(2)}"
        if kind == "REQ":
            ident = f"REQ-{int(object_match.group(2)):04d}"
        text = getter(ident) if callable(getter) else None
        if text:
            result.notes.append(f"@{token}")
            return f"[@{token}]\n{text}"
        return None
    path_text, _, span = token.partition(":") if re.search(r":\d+-\d+$", token) else (token, "", "")
    candidate = Path(path_text)
    if candidate.suffix.lower() in IMAGE_SUFFIXES:
        return _attach_image(candidate, workspace, result)
    try:
        path = workspace.path_of(path_text.replace("\\", "/"))
    except (ForgeError, ValueError):
        return None
    if not path.is_file() or workspace.is_secret(path_text.replace("\\", "/")):
        return None
    lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    if span:
        start, end = (int(n) for n in span.split("-"))
        chosen = lines[max(start - 1, 0) : end]
        label = f"{path_text} lines {start}-{end}"
    else:
        start, chosen, label = 1, lines, path_text
    body = "\n".join(f"{start + i:>5}\t{line}" for i, line in enumerate(chosen))[:MAX_FILE_CHARS]
    result.notes.append(f"@{token}")
    return f"[@{label}]\n```\n{body}\n```"


def _attach_image(candidate: Path, workspace: Workspace, result: Expanded) -> str | None:
    source = candidate if candidate.is_absolute() else None
    if source is None:
        try:
            source = workspace.path_of(candidate.as_posix())
        except (ForgeError, ValueError):
            return None
    if not source.is_file():
        return None
    inputs = workspace.jail.check(workspace.forge_dir / "inputs")
    inputs.mkdir(parents=True, exist_ok=True)
    target = workspace.jail.check(inputs / f"{datetime.now():%Y%m%d%H%M%S}-{source.name}")
    shutil.copyfile(source, target)
    result.images.append(target)
    relative = target.relative_to(workspace.root).as_posix()
    result.notes.append(f"image attached: {relative}")
    return f"[image attached: {relative} — look at it with view_image]"


def _store_long_paste(message: str, workspace: Workspace) -> Path | None:
    if len(message) <= LONG_PASTE_CHARS:
        return None
    inputs = workspace.jail.check(workspace.forge_dir / "inputs")
    inputs.mkdir(parents=True, exist_ok=True)
    path = workspace.jail.check(inputs / f"paste-{datetime.now():%Y%m%d%H%M%S}.txt")
    path.write_text(message, encoding="utf-8")
    return path
