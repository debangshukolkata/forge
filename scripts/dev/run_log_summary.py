"""What a run did, from its event log: where the output tokens and the time went, which assets it used, what was refused (D-381).

    python scripts/dev/run_log_summary.py <workspace folder or events.jsonl> [...]

Prints, per run: model calls, output and input tokens, wall time, model time, tool counts, the catalogue assets copied with add_asset, every write of a page or style file with its
size (a page written more than once is a sign of waste), the refusals (a gate or a tool said no), and the biggest model calls. Used for the S5 analysis and the app-screen check."""

from __future__ import annotations

import collections
import json
import sys
from datetime import datetime
from pathlib import Path


def load(path: Path) -> list[dict[str, object]]:
    events_file = path if path.suffix == ".jsonl" else path / ".forge" / "transcripts" / "events.jsonl"
    return [
        json.loads(line)
        for line in events_file.read_text(encoding="utf-8", errors="replace").splitlines()
        if line.strip()
    ]


def seconds(stamp: object) -> float:
    return datetime.fromisoformat(str(stamp)).timestamp()


def summarise(path: Path) -> str:
    events = load(path)
    if not events:
        return f"{path}: no events"
    calls = [e for e in events if e["type"] == "llm_call"]
    payloads = [c["payload"] for c in calls]  # type: ignore[index]
    out_tokens = sum(p["usage"].get("output_tokens", 0) for p in payloads)
    in_tokens = sum(p["usage"].get("input_tokens", 0) for p in payloads)
    wall = seconds(events[-1]["ts"]) - seconds(events[0]["ts"])
    model_s = sum(p.get("latency_s", 0.0) for p in payloads)
    tools: collections.Counter[str] = collections.Counter()
    assets: list[str] = []
    writes: collections.Counter[str] = collections.Counter()
    starts: dict[str, dict[str, object]] = {}
    refused: list[str] = []
    for e in events:
        payload: dict[str, object] = e["payload"]  # type: ignore[assignment]
        if e["type"] == "tool_call_started":
            name = str(payload["name"])
            tools[name] += 1
            starts[str(payload["id"])] = payload
            arguments = payload.get("arguments") if isinstance(payload.get("arguments"), dict) else {}
            if name == "add_asset":
                assets.append(str(arguments.get("id")))  # type: ignore[union-attr]
            if name in ("write_file", "multi_edit", "edit_file"):
                writes[str(payload.get("summary"))[:70]] += 1
        elif e["type"] == "tool_call_finished" and not payload.get("ok", True):
            refused.append(
                f"{str(e['ts'])[11:19]} {payload.get('name')}: {str(payload.get('preview'))[:110]}".replace(
                    "\n", " "
                )
            )
    big = sorted(payloads, key=lambda p: -p["usage"].get("output_tokens", 0))[:5]
    lines = [
        f"== {path}",
        f"wall {wall:.0f} s, model time {model_s:.0f} s, {len(calls)} model calls, output tokens {out_tokens}, input tokens {in_tokens}",
        "tools: " + ", ".join(f"{k} {v}" for k, v in tools.most_common(12)),
        "assets copied: " + (", ".join(assets) if assets else "none"),
        "writes and edits repeated: "
        + (", ".join(f"{k} x{v}" for k, v in writes.items() if v > 1) or "none"),
        f"refusals and failures: {len(refused)}",
        *[f"   {r}" for r in refused[:12]],
        "biggest calls: "
        + "; ".join(
            f"{p['usage'].get('output_tokens', 0)} tokens {p.get('latency_s', 0):.0f} s ({', '.join(p.get('tool_calls', []))[:50]})"
            for p in big
        ),  # type: ignore[attr-defined]
    ]
    return "\n".join(lines)


def main(argv: list[str]) -> int:
    if not argv:
        print(__doc__)
        return 1
    for item in argv:
        print(summarise(Path(item)))
        print()
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
