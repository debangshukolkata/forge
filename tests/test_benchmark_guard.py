"""D-381: a benchmark run whose machine slept or lost its network is marked invalid instead of reporting a huge wall time."""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts" / "benchmark"))
from awake import keep_awake, stall_note
from run_speed_benchmark import timing


def write_events(path: Path, stamps: list[str], call_latency: float) -> None:
    events = [{"type": "user_message", "ts": stamps[0], "payload": {"text": "go"}}]
    for stamp in stamps[1:]:
        events.append(
            {
                "type": "llm_call",
                "ts": stamp,
                "payload": {"latency_s": call_latency, "usage": {"input_tokens": 10, "output_tokens": 5}},
            }
        )
    path.write_text("\n".join(json.dumps(e) for e in events), encoding="utf-8")


def test_a_run_with_a_long_gap_or_a_very_long_call_is_invalid(tmp_path: Path) -> None:
    normal = tmp_path / "normal.jsonl"
    write_events(
        normal, ["2026-10-15T00:00:00+00:00", "2026-10-15T00:01:00+00:00", "2026-10-15T00:02:00+00:00"], 30.0
    )
    row = timing(normal)
    assert row["timing_valid"] is True and row["longest_gap_s"] == 60 and stall_note(row) == ""
    slept = tmp_path / "slept.jsonl"
    write_events(
        slept, ["2026-10-15T00:00:00+00:00", "2026-10-15T00:01:00+00:00", "2026-10-15T01:55:00+00:00"], 6700.0
    )
    bad = timing(slept)
    assert bad["timing_valid"] is False and bad["longest_model_call_s"] == 6700
    assert "INVALID: stalled" in stall_note(bad) and "6840" in stall_note(bad)


def test_keep_awake_is_safe_everywhere() -> None:
    assert keep_awake() in (True, False)
