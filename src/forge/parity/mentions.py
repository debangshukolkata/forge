"""@-mentions and long pastes (spec §13B).

In a user message: `@path` includes a workspace file, `@path:10-80` a line range; `@image.png` (an image in
the workspace or a pasted path) is saved to .forge/inputs/ and attached; `@DBR-3` brings in a Forge object.
A message longer than LONG_PASTE_CHARS is stored as a file in
.forge/inputs/ and referenced instead of being sent inline in full.
"""

from __future__ import annotations

import re
import shutil
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

from forge.errors import ForgeError
from forge.safety.paths import is_within, real_path
from forge.workspace.read_grants import ReadGrantError
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
    grants: list[str] = field(default_factory=list)  # read access the user's own words opened (D-208)


def expand(message: str, workspace: Workspace, lookup: dict[str, object] | None = None) -> Expanded:
    """lookup maps object kinds to callables: {"DBR": fn(id)->str|None}."""
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
    if stored is None:  # a long paste is not the user's own instruction
        _grant_typed_paths(message, workspace, result)
    attachments: list[str] = []
    for token in dict.fromkeys(MENTION.findall(message)):
        block = _resolve(token, workspace, lookup or {}, result)
        if block:
            attachments.append(block)
    if attachments:
        result.text += "\n\n" + "\n\n".join(attachments)
    return result


def _resolve(token: str, workspace: Workspace, lookup: dict[str, object], result: Expanded) -> str | None:
    object_match = re.fullmatch(r"(DBR)-?(\d+)", token, re.IGNORECASE)
    if object_match:
        kind = object_match.group(1).upper()
        getter = lookup.get(kind)
        ident = f"{kind}-{object_match.group(2)}"
        text = getter(ident) if callable(getter) else None
        if text:
            result.notes.append(f"@{token}")
            return f"[@{token}]\n{text}"
        return None
    if token.replace("\\", "/").startswith(INPUTS_PREFIX):
        return _resolve_input(token.replace("\\", "/")[len(INPUTS_PREFIX) :], workspace, result)
    path_text, _, span = token.partition(":") if re.search(r":\d+-\d+$", token) else (token, "", "")
    candidate = Path(path_text)
    if candidate.is_absolute() and candidate.suffix.lower() not in IMAGE_SUFFIXES:
        _grant(path_text, workspace, result)  # an explicit @path outside the project is a request to read it
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


def _grant_typed_paths(message: str, workspace: Workspace, result: Expanded) -> None:
    """A path the user typed with a word like 'read' or 'review' is a request to read it: folders include
    everything under them. Only the user's own message is looked at, never tool output or file contents."""
    if not READ_INTENT.search(message):
        return
    for match in TYPED_PATH.finditer(message):
        text = (match.group(1) or match.group(2) or match.group(3)).rstrip(".,;:)")
        _grant(text, workspace, result)


def _grant(text: str, workspace: Workspace, result: Expanded) -> None:
    candidate = Path(text)
    if not candidate.is_absolute() or not candidate.exists():
        return
    resolved = real_path(candidate)
    if is_within(resolved, real_path(workspace.root)) or workspace.read_grants.allows(resolved):
        return
    try:
        granted = workspace.read_grants.grant(text)
    except ReadGrantError as error:
        result.grants.append(f"Not opened for reading: {error}")
        return
    result.grants.append(
        f"Forge may now read {granted} (everything under it too) in this project; read only. "
        f"/revoke-read {granted} undoes it."
    )
    result.text += (
        f"\n\n[The user opened {granted} for reading. Use that full path with read_file, list_dir, glob "
        "and grep; do not turn it into a relative path.]"
    )


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


INPUTS_PREFIX = ".forge/inputs/"
TYPED_PATH = re.compile(
    r'"([A-Za-z]:[\\/][^"]+)"|(?<![\w@/\\])([A-Za-z]:[\\/][^\s"\'<>|*?]+)|(?<![\w.:/\\@])(/(?:[\w.-]+/)*[\w.-]+)'
)
READ_INTENT = re.compile(
    r"\b(read|open|look(?:ing)? at|take a look|review|inspect|analy[sz]e|summari[sz]e|study|examine"
    r"|go through|refer to|check out)\b",
    re.IGNORECASE,
)
TEXT_SUFFIXES = {
    ".txt",
    ".md",
    ".py",
    ".json",
    ".yaml",
    ".yml",
    ".toml",
    ".ini",
    ".cfg",
    ".csv",
    ".sql",
    ".xml",
    ".html",
    ".js",
    ".ts",
    ".tsx",
    ".jsx",
    ".css",
    ".ps1",
    ".sh",
    ".java",
    ".cs",
    ".go",
    ".rs",
    ".log",
    ".env.example",
}
MAX_INPUT_NAME = 80


def store_input(workspace: Workspace, name: str, data: bytes) -> dict[str, str]:
    """An attachment from the UI, saved as .forge/inputs/<timestamp>-<name> (inside the workspace jail).
    Returns its mention path and kind; the UI puts `@<path>` in the message."""
    clean = re.sub(r"[^A-Za-z0-9._-]+", "-", Path(name).name).strip("-.")[:MAX_INPUT_NAME] or "attachment"
    inputs = workspace.jail.check(workspace.forge_dir / "inputs")
    inputs.mkdir(parents=True, exist_ok=True)
    target = workspace.jail.check(inputs / f"{datetime.now():%Y%m%d-%H%M%S%f}-{clean}")
    target.write_bytes(data)
    return {"path": INPUTS_PREFIX + target.name, "name": clean, "kind": _input_kind(target)}


def _input_kind(path: Path) -> str:
    suffix = path.suffix.lower()
    if suffix in IMAGE_SUFFIXES:
        return "image"
    if suffix == ".pdf":
        return "pdf"
    return "text" if suffix in TEXT_SUFFIXES else "file"


def _resolve_input(name: str, workspace: Workspace, result: Expanded) -> str | None:
    """@.forge/inputs/<file>: an attachment the UI uploaded (only that folder, no sub-paths)."""
    if not name or "/" in name or ".." in name:
        return None
    path = workspace.forge_dir / "inputs" / name
    if not path.is_file():
        return None
    relative = INPUTS_PREFIX + name
    kind = _input_kind(path)
    if kind == "image":
        result.images.append(path)
        result.notes.append(f"image attached: {relative}")
        return f"[image attached: {relative} — look at it with view_image]"
    if kind == "pdf":
        result.notes.append(f"PDF attached: {relative}")
        return f"[PDF attached: {relative} — render its pages with pdf_render, then view_image them]"
    if kind == "text":
        body = path.read_text(encoding="utf-8", errors="replace")[:MAX_FILE_CHARS]
        result.notes.append(f"file attached: {relative}")
        return f"[@{relative}]\n```\n{body}\n```"
    result.notes.append(f"file attached: {relative}")
    return (
        f"[file attached: {relative} ({path.stat().st_size} bytes) — Forge can't read this format directly; "
        "ask the user to paste the relevant text if you need it]"
    )


def _store_long_paste(message: str, workspace: Workspace) -> Path | None:
    if len(message) <= LONG_PASTE_CHARS:
        return None
    inputs = workspace.jail.check(workspace.forge_dir / "inputs")
    inputs.mkdir(parents=True, exist_ok=True)
    path = workspace.jail.check(inputs / f"paste-{datetime.now():%Y%m%d%H%M%S}.txt")
    path.write_text(message, encoding="utf-8")
    return path
