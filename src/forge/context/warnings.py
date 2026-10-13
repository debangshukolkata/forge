"""Context-usage warnings (TODO C12 e, D-298): tell the user before a long context slows the model down and makes it less accurate,
with what they can do about it. Pure logic: the agent loop calls `next_warning` after each model call with the current fill level and
the level already warned about; it returns the notice text (or None) and the new level."""

from __future__ import annotations

from forge.config import ContextConfig


def next_warning(percent: float, warned_level: int, settings: ContextConfig) -> tuple[str | None, int]:
    """`percent` is how full the usable window is (0-100); `warned_level` is 0 (nothing said), 1 or 2. Each level is said once until
    the context drops well below the first threshold again (after a compaction or /clear)."""
    first, second = settings.warn_at * 100, settings.warn_again_at * 100
    if percent < first - 10:
        return None, 0
    if percent >= second and warned_level < 2:
        text = (
            f"The context is {percent:.0f}% full: answers get slower and less reliable from here. /compact [what to keep] now, "
            "or /clear if the earlier work is no longer needed."
        )
        return text, 2
    if percent >= first and warned_level < 1:
        text = (
            f"The context is {percent:.0f}% full. DebCraft summarises earlier turns on its own when the history reaches "
            f"{settings.auto_compact_at * 100:.0f}% of its share; /compact [what to keep] does it now, and unrelated work is "
            "better in a new requirement (a long context makes every answer slower and a little less accurate)."
        )
        return text, 1
    return None, warned_level
