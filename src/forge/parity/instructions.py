"""FORGE.md instruction files (spec §13B), the equivalent of CLAUDE.md, loaded hierarchically and always
pinned (capped): <forge_home>/FORGE.md (user-wide) -> <kb folder or host profile>/FORGE.md (repo/host) ->
<workspace>/FORGE.md (this requirement). `/init` drafts the repo-level file from the knowledge base;
a chat line starting with '#' appends to a chosen file after confirmation."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from forge.llm.tokens import head_and_tail
from forge.safety.redact import default_redactor

INSTRUCTIONS_TOKEN_CAP = 1500
LEVELS = ("user", "repo", "workspace")


@dataclass
class InstructionFile:
    level: str
    path: Path

    def text(self) -> str:
        return self.path.read_text(encoding="utf-8").strip() if self.path.exists() else ""


def instruction_files(
    home: Path, repo_level_dir: Path | None, workspace_root: Path | None
) -> list[InstructionFile]:
    files = [InstructionFile("user", home / "FORGE.md")]
    if repo_level_dir is not None:
        files.append(InstructionFile("repo", repo_level_dir / "FORGE.md"))
    if workspace_root is not None:
        files.append(InstructionFile("workspace", workspace_root / "FORGE.md"))
    return files


def render(files: list[InstructionFile], style: str | None = None) -> str | None:
    parts = [f"From {f.level}-level FORGE.md:\n{f.text()}" for f in files if f.text()]
    if style and style in STYLES:
        parts.append(f"Output style ({style}): {STYLES[style]}")
    if not parts:
        return None
    text = "\n\n".join(parts)
    head, tail, omitted = head_and_tail(text, INSTRUCTIONS_TOKEN_CAP)
    return head + (f"\n[… {omitted} tokens of instructions omitted …]\n" + tail if omitted else "")


def append_line(file: InstructionFile, line: str) -> None:
    """The '#' chat shortcut, after the user confirmed which file."""
    file.path.parent.mkdir(parents=True, exist_ok=True)
    existing = file.text()
    body = (
        existing + "\n" if existing else "# Instructions for Forge\n\n"
    ) + f"- {default_redactor.redact(line.strip())}\n"
    file.path.write_text(body, encoding="utf-8")


def draft_from_kb(essentials: str | None, name: str) -> str:
    """/init: a starting point from what the KB already knows; the user edits it afterwards."""
    lines = [
        f"# Instructions for Forge — {name}",
        "",
        "Edit this file freely: Forge reads it at the start of every session for this repository.",
        "",
        "## Conventions to always follow",
        "- (add yours, e.g. 'always add type hints', 'errors use the ClaimsAppError hierarchy')",
        "",
        "## Things Forge must never do here",
        "- (e.g. 'never touch the alembic folder')",
    ]
    if essentials:
        lines += [
            "",
            "## What the knowledge base found (for reference; trim as you like)",
            essentials.strip()[:3000],
        ]
    return "\n".join(lines) + "\n"


STYLES = {
    "concise": "Say only what changed and how it was verified; no explanations unless asked.",
    "explanatory": "While working, add a short 'why' note to each significant choice (one or two sentences).",
    "learning": (
        "Teach as you go: explain choices briefly and leave one or two small, clearly marked TODOs "
        "(`# TODO(you): ...`) for the user to implement where it helps them learn; say where they are."
    ),
}
