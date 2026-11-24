"""Reads a recording: its moments in order."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

FOLDER = Path(__file__).resolve().parent.parent / "recordings"


@dataclass(frozen=True)
class Moment:
    seconds: int
    speech: str
    screen: str


def seconds_of(time: str) -> int:
    hours, minutes, seconds = (int(part) for part in time.split(":"))
    return hours * 3600 + minutes * 60 + seconds


def load(recording_id: str) -> list[Moment]:
    """Raises FileNotFoundError for an unknown recording."""
    if not recording_id.isdigit():
        raise FileNotFoundError(recording_id)
    moments = []
    for line in (FOLDER / f"{recording_id}.txt").read_text(encoding="utf-8").splitlines():
        time, speech, screen = (part.strip() for part in line.split("|"))
        moments.append(
            Moment(seconds_of(time), speech.removeprefix("speech: "), screen.removeprefix("screen: "))
        )
    return moments
