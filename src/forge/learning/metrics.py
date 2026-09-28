"""Metrics (spec §12.4): one JSON line per task and per run in <forge_home>/learning/metrics.jsonl, with
Forge's version, so /stats can show trends and improvements can be measured before/after."""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any

from forge import __version__


class Metrics:
    def __init__(self, home: Path) -> None:
        self.path = home / "learning" / "metrics.jsonl"

    def record(self, kind: str, scope: str, workspace: str, **values: Any) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        entry = {
            "ts": datetime.now().isoformat(timespec="seconds"),
            "kind": kind,
            "scope": scope,
            "workspace": workspace,
            "forge_version": __version__,
            **values,
        }
        with self.path.open("a", encoding="utf-8") as log:
            log.write(json.dumps(entry, default=str) + "\n")

    def entries(self) -> list[dict[str, Any]]:
        if not self.path.exists():
            return []
        return [
            json.loads(line) for line in self.path.read_text(encoding="utf-8").splitlines() if line.strip()
        ]

    def stats(self) -> str:
        runs = [e for e in self.entries() if e["kind"] == "run"]
        tasks = [e for e in self.entries() if e["kind"] == "task"]
        if not runs and not tasks:
            return "No metrics yet: they are recorded when a requirement is exported."
        first_pass = [t for t in tasks if t.get("fix_attempts", 0) == 0]
        average_cost = sum(r.get("cost_usd", 0) for r in runs) / max(len(runs), 1)
        lines = [
            f"Requirements: {len(runs)} · tasks: {len(tasks)}",
            f"Average cost per requirement: ${average_cost:.4f}",
            f"Tasks done without a failed verification: {len(first_pass)}/{len(tasks)}",
            f"Stuck events: {sum(t.get('stuck_events', 0) for t in tasks)} · review findings: "
            f"{sum(r.get('review_findings', 0) for r in runs)} · diagnose issues: "
            f"{sum(r.get('diagnose_issues', 0) for r in runs)}",
        ]
        causes: dict[str, int] = {}
        for task in tasks:
            for cause in task.get("failure_causes", []):
                causes[cause] = causes.get(cause, 0) + 1
        if causes:
            common = sorted(causes.items(), key=lambda item: -item[1])[:5]
            lines.append("Most common failure causes: " + ", ".join(f"{c} ({n})" for c, n in common))
        return "\n".join(lines)
