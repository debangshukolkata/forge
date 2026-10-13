r"""Prompt-cache report (TODO S3): how much of the input was served from the cache in each run, and where the cache broke.

    python scripts/dev/cache_report.py C:\Work\ForgeRuns\speedbench\speed-3 [more run folders ...]

Reads every workspace's .forge/transcripts/events.jsonl under the given folders. A "miss" is a model call with no cached tokens right
after a call that had many: something in the prompt prefix changed (compaction, a trimmed tool output, a changed pinned block) or the
cache expired. Prints one line per workspace and the biggest misses with the step and the cost in tokens."""

from __future__ import annotations

import json
import sys
from pathlib import Path

MIN_PREVIOUS_CACHED = 4000


def calls(events: Path) -> list[dict[str, object]]:
    out = []
    for line in events.read_text(encoding="utf-8", errors="replace").splitlines():
        if not line.strip():
            continue
        event = json.loads(line)
        if event["type"] == "llm_call":
            usage = event["payload"].get("usage", {})
            out.append(
                {
                    "input": usage.get("input_tokens", 0),
                    "cached": usage.get("cached_input_tokens", 0),
                    "role": event["payload"].get("role", "?"),
                    "latency": event["payload"].get("latency_s", 0.0),
                }
            )
    return out


def main(folders: list[str]) -> int:
    for folder in folders:
        for events in sorted(Path(folder).rglob("events.jsonl")):
            rows = calls(events)
            if len(rows) < 3:
                continue
            total_in = sum(int(r["input"]) for r in rows)  # type: ignore[call-overload]
            total_cached = sum(int(r["cached"]) for r in rows)  # type: ignore[call-overload]
            misses = []
            for index in range(1, len(rows)):
                before, now = rows[index - 1], rows[index]
                if (
                    int(before["cached"]) >= MIN_PREVIOUS_CACHED
                    and int(now["cached"]) < int(before["cached"]) * 0.5
                ):  # type: ignore[call-overload]
                    misses.append((index + 1, int(before["cached"]), int(now["cached"]), int(now["input"])))  # type: ignore[call-overload]
            name = events.parent.parent.parent.name
            share = 100 * total_cached / total_in if total_in else 0
            lost = sum(m[1] - m[2] for m in misses)
            print(
                f"{name:32s} calls {len(rows):3d}  cached {share:5.1f}% of {total_in:>9,}  misses {len(misses):2d}  tokens re-read after misses {lost:>8,}"
            )
            for call, before, now, size in sorted(misses, key=lambda m: m[1] - m[2], reverse=True)[:3]:
                print(f"    call {call}: cached {before:,} -> {now:,} (input {size:,})")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
