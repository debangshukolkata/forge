"""The saved environment (D-186): the last check results and the confirmed model plan, per machine."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

FILE = "environment.json"


def _path(home: Path) -> Path:
    return home / FILE


def load(home: Path) -> dict[str, Any]:
    """Always a dict with `results`, `plan`, `confirmed_at`; a missing or damaged file means nothing saved."""
    empty: dict[str, Any] = {"results": {}, "plan": {}, "confirmed_at": None, "answers": {}}
    try:
        data = json.loads(_path(home).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return empty
    if not isinstance(data, dict):
        return empty
    return {
        "results": data.get("results") if isinstance(data.get("results"), dict) else {},
        "plan": data.get("plan") if isinstance(data.get("plan"), dict) else {},
        "confirmed_at": data.get("confirmed_at") if isinstance(data.get("confirmed_at"), str) else None,
        # What the user said about optional tools ("is Tesseract installed?"): check id -> yes/no.
        "answers": {k: v for k, v in (data.get("answers") or {}).items() if isinstance(v, bool)}
        if isinstance(data.get("answers"), dict)
        else {},
    }


def _write(home: Path, data: dict[str, Any]) -> None:
    home.mkdir(parents=True, exist_ok=True)
    _path(home).write_text(json.dumps(data, indent=1), encoding="utf-8")


def now() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")


def save_result(home: Path, check_id: str, result: dict[str, Any]) -> None:
    data = load(home)
    data["results"][check_id] = {**result, "checked_at": now()}
    _write(home, data)


def save_answer(home: Path, check_id: str, enabled: bool) -> None:
    data = load(home)
    data["answers"][check_id] = enabled
    _write(home, data)


def save_plan(home: Path, plan: dict[str, str]) -> None:
    data = load(home)
    data["plan"] = dict(plan)
    data["confirmed_at"] = now()
    _write(home, data)
