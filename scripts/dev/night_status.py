"""Progress of tonight's work in one screen: python scripts/dev/night_status.py [benchmark-run-name]

Reads TODO.md section 0c (items marked [x] done, [~] partly, [ ] open) and the design benchmark folder (briefs finished, running, waiting)."""

from __future__ import annotations

import json
import re
import sys
import time
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
RUNS = Path(r"C:\Work\ForgeRuns\designbench")
BRIEFS = ["d01_science_museum", "d02_ramen_bar", "d03_ops_dashboard", "d04_member_table", "d05_booking_wizard"]


def todo_counts() -> tuple[dict[str, list[str]], int]:
    text = (REPO / "TODO.md").read_text(encoding="utf-8")
    start = text.index("0c")
    section = text[start:]
    groups: dict[str, list[str]] = {"x": [], "~": [], " ": []}
    for match in re.finditer(r"^(\d+)\. \[([x~ ])\] \*\*(.{0,70})", section, re.M):
        number = int(match.group(1))
        if number <= 30:
            groups[match.group(2)].append(f"{number}. {match.group(3).strip(' *')}")
    return groups, sum(len(v) for v in groups.values())


def benchmark(name: str) -> None:
    folder = RUNS / name
    print(f"\nDESIGN BENCHMARK {name}")
    running_seen = False
    for brief in BRIEFS:
        run_file = folder / f"{brief}_run.json"
        events = folder / brief / ".forge" / "transcripts" / "events.jsonl"
        if run_file.exists():
            print(f"  [done]    {brief}")
        elif events.exists():
            calls = sum(1 for line in events.open(encoding="utf-8", errors="replace") if '"tool_call_started"' in line)
            minutes = (time.time() - (folder / f"{brief}_prompt.txt").stat().st_mtime) / 60
            print(f"  [RUNNING] {brief}: {calls} tool calls, {minutes:.0f} min in")
            running_seen = True
        else:
            print(f"  [waiting] {brief}")
    print("  results.md written" if (folder / "results.md").exists() else "  results.md: not yet" + ("" if running_seen else " (nothing running?)"))
    if (folder / "results.json").exists():
        try:
            json.loads((folder / "results.json").read_text(encoding="utf-8"))
        except ValueError:
            pass


def main() -> None:
    name = sys.argv[1] if len(sys.argv) > 1 else "night-1"
    groups, total = todo_counts()
    print(f"TONIGHT'S LIST (TODO 0c): {len(groups['x'])} done, {len(groups['~'])} partly, {len(groups[' '])} open of {total}")
    for key, label in (("~", "partly"), (" ", "open")):
        for item in groups[key]:
            print(f"  [{label}] {item}")
    benchmark(name)


if __name__ == "__main__":
    main()
