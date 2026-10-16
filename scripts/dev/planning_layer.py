"""The planning layer of one DebCraft run, from its event log: `python scripts/dev/planning_layer.py <run folder or workspace> [--out file]`

Prints, in the order they happened and before the first project file was written: the planner's report, every question asked (and how it was answered), each assumption, each task list, and what `propose_requirements` and `propose_plan` said.
This is what docs/APP_BENCHMARK.md judges: the understanding, the decisions and the scope, not the finished screens."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any


def load(folder: Path) -> list[dict[str, Any]]:
    workspace = folder / "ws" if (folder / "ws").is_dir() else folder
    path = workspace / ".forge" / "transcripts" / "events.jsonl"
    events = []
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        try:
            events.append(json.loads(line))
        except ValueError:
            continue
    return events


def text_of(value: Any) -> str:
    return value if isinstance(value, str) else json.dumps(value, ensure_ascii=False, indent=1)


def render(events: list[dict[str, Any]]) -> str:
    started: dict[str, dict[str, Any]] = {}
    out: list[str] = []
    for event in events:
        payload = event.get("payload", {})
        stamp = event["ts"][11:19]
        kind = event["type"]
        if kind == "tool_call_started":
            started[payload.get("id", "")] = payload
            name = payload.get("name")
            args = payload.get("arguments") or {}
            if name in ("write_file", "multi_edit"):
                path = str(args.get("path") or "").replace("\\", "/")
                if (
                    path
                    and not path.startswith(".forge")
                    and path.split("/")[-1] not in ("DESIGN.md", "NOTICES.md")
                ):
                    out.append(
                        f"\n--- {stamp} first project file written ({path}): the planning layer ends here ---"
                    )
                    break
            if name in ("assumption_add", "todo_write", "propose_requirements", "propose_plan", "ask_user"):
                out.append(f"\n## {stamp} {name}\n{text_of(args)}")
        elif kind == "tool_call_finished" and payload.get("name") == "spawn_subagent":
            task = (started.get(payload.get("id", "")) or {}).get("arguments", {})
            out.append(
                f"\n## {stamp} sub-agent {task.get('agent', '')}: report\n{payload.get('preview', '')}"
            )
        elif kind == "question_asked":
            out.append(f"\n## {stamp} question asked\n{text_of(payload)}")
        elif kind == "question_answered":
            out.append(f"\n## {stamp} answered\n{text_of(payload)}")
    return "\n".join(out)


if __name__ == "__main__":
    folder = Path(sys.argv[1])
    text = render(load(folder))
    target = Path(sys.argv[sys.argv.index("--out") + 1]) if "--out" in sys.argv else folder / "planning.md"
    target.write_text(text, encoding="utf-8")
    print(f"{len(text.split())} words -> {target}")
