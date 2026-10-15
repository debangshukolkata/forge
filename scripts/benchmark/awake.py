"""Keeps a Windows machine from going to sleep while a benchmark runs (D-381).

A laptop that sleeps in the middle of a run makes a model call "take" almost two hours and the run's timing worthless. `keep_awake()` asks Windows to stay awake for as long
as the benchmark process lives (the display may still turn off); on other systems it does nothing. Call it once at the start of a runner's `main`."""

from __future__ import annotations

import sys

ES_CONTINUOUS = 0x80000000
ES_SYSTEM_REQUIRED = 0x00000001


def keep_awake() -> bool:
    if sys.platform != "win32":
        return False
    try:
        import ctypes

        return bool(ctypes.windll.kernel32.SetThreadExecutionState(ES_CONTINUOUS | ES_SYSTEM_REQUIRED))  # type: ignore[attr-defined]
    except (AttributeError, OSError):
        return False


def stall_note(row: dict[str, object]) -> str:
    """A short warning for a results table when the run's timing is not valid, else an empty string."""
    if row.get("timing_valid", True):
        return ""
    return f" (INVALID: stalled {max(int(str(row.get('longest_gap_s', 0))), int(str(row.get('longest_model_call_s', 0))))} s)"
