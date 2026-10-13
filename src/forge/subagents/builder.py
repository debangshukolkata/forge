"""Parallel builders (TODO X2, D-305): a builder is a subagent that implements one self-contained piece of work (a variant, a screen, a
service) inside its own folder, while other builders do the same in other folders. The protocol follows the study in
docs/SKILLS_STUDY.md (ideas from the MIT-licensed Superpowers and mattpocock/skills, in our own words):

- the controller (the main agent) writes a brief per builder, never codes the builders' parts itself, and verifies each result;
- a builder reads only its brief, writes only below its folder, runs its own checks, and ends its report with a status line (the controller saves the report file);
- four statuses, each with a defined response; a blocked builder is never retried unchanged;
- a ledger file records every builder's folder and status, so the work survives a compaction of the conversation.
"""

from __future__ import annotations

import re
from datetime import datetime
from pathlib import Path

from forge.toolkit.folders import (  # noqa: F401  (re-exported for callers and tests)
    clean_folder,
    folders_disjoint,
)

BUILDER_ITERATIONS = 60
MAX_PARALLEL_BUILDERS = 3
STATUSES = ("DONE", "DONE_WITH_CONCERNS", "NEEDS_CONTEXT", "BLOCKED")
STATUS_LINE = re.compile(r"STATUS:\s*(DONE_WITH_CONCERNS|DONE|NEEDS_CONTEXT|BLOCKED)", re.IGNORECASE)
LEDGER = "builders/ledger.md"

BUILDER_PROMPT = """You are a builder. The main agent gave you one self-contained piece of work and a folder; other builders are
working in other folders at the same time. You see only this brief, not the main conversation.

Rules:
1. Read the brief first. Work only inside your folder: you can write files only below it, and your commands start there. Do not
   touch other folders, shared files (package.json or lock files at the root, the database schema, configuration) or the
   tests of other parts. If you need a change outside your folder, say so in your report.
2. Use your own port for any server (start_background with {port} gives a free one) and stop what you start before you finish.
3. Build the whole piece, run its checks (tests, lint, a look in the browser when it is a page), and fix what fails. Keep to the
   brief: no extra features.
4. Do not start helpers of your own (no reviewers, no critics). Do not ask the user questions; a missing fact is a status, below.
5. Your final message is your report (it is saved for the main agent): what you built, the files, how you checked it and what is
   left, ending with exactly one status line and at most 120 words of summary above it:
   STATUS: DONE - finished and checked.
   STATUS: DONE_WITH_CONCERNS - finished, but something may be wrong or out of scope: say what.
   STATUS: NEEDS_CONTEXT - you cannot go on without a specific fact or decision: say which.
   STATUS: BLOCKED - something stops you that more effort will not fix: say what and what you tried.
"""

RESPONSES = {
    "DONE": "Verify it yourself (run its checks, look at it) before you count it.",
    "DONE_WITH_CONCERNS": "Handle the concerns that affect correctness or scope first, note the rest, then verify.",
    "NEEDS_CONTEXT": "Give the missing fact in a new brief and start the builder again; do not guess for it.",
    "BLOCKED": "Do not retry unchanged: add context, split the work, change the brief, or do this part yourself.",
}


def parse_status(report: str) -> str:
    """The builder's status from its report (the last status line); BLOCKED when it wrote none, so nothing is counted as done by luck."""
    found = STATUS_LINE.findall(report)
    return found[-1].upper() if found else "BLOCKED"


def safe_name(name: str, folder: str) -> str:
    base = re.sub(r"[^A-Za-z0-9_-]+", "-", name or folder.replace("/", "-")).strip("-").lower()
    return base[:40] or "builder"


def report_path(name: str) -> str:
    """Where a builder writes its report, relative to the repository root's workspace `.forge` folder."""
    return f".forge/builders/{name}-report.md"


def append_ledger(forge_dir: Path, name: str, folder: str, status: str, summary: str) -> None:
    """One line per finished builder in `.forge/builders/ledger.md` (kept outside the conversation, so it survives compaction)."""
    path = forge_dir / LEDGER
    path.parent.mkdir(parents=True, exist_ok=True)
    first = " ".join(summary.split())[:200]
    with path.open("a", encoding="utf-8") as handle:
        handle.write(f"- {datetime.now():%Y-%m-%d %H:%M} {name} [{folder}] {status}: {first}\n")


def result_text(name: str, folder: str, status: str, report: str, report_file: str) -> str:
    return (
        f"[builder {name} in {folder}: {status}]\n{report}\n\n"
        f"Report file: {report_file}. What to do: {RESPONSES[status]}"
    )
