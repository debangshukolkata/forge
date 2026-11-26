"""The saved environment (D-186): the last check results and the confirmed model plan, per machine."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from forge.home_layout import data_path

FILE = "environment.json"
# Raised when the shipped role proposals change so much that choices made by hand before should give way once (D-661:
# the roles of the role challenge, Hydrogen codes and plans, Argon checks, GPT-5.4 falls back). A plan saved with an
# older number keeps its models, but no role counts as chosen by hand any more, so every role follows the proposal.
ROLE_DEFAULTS = 2


def _path(home: Path) -> Path:
    return data_path(home, FILE)


def load(home: Path) -> dict[str, Any]:
    """Always a dict with `results`, `plan`, `confirmed_at`; a missing or damaged file means nothing saved."""
    empty: dict[str, Any] = {
        "results": {},
        "plan": {},
        "manual": [],
        "role_defaults": ROLE_DEFAULTS,
        "confirmed_at": None,
        "answers": {},
    }
    try:
        data = json.loads(_path(home).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return empty
    if not isinstance(data, dict):
        return empty
    return {
        "results": data.get("results") if isinstance(data.get("results"), dict) else {},
        "plan": data.get("plan") if isinstance(data.get("plan"), dict) else {},
        # The roles the user chose by hand when the plan was saved (D-416): only these keep their value when the proposals change; the others follow the new proposal.
        "manual": [r for r in data.get("manual", []) if isinstance(r, str)]
        if isinstance(data.get("manual"), list) and data.get("role_defaults") == ROLE_DEFAULTS
        else [],
        # Every role follows the shipped proposals from this version on (the hand choices were cleared above).
        "role_defaults": ROLE_DEFAULTS,
        "confirmed_at": data.get("confirmed_at") if isinstance(data.get("confirmed_at"), str) else None,
        # What the user said about optional tools ("is Tesseract installed?"): check id -> yes/no.
        "answers": {k: v for k, v in (data.get("answers") or {}).items() if isinstance(v, bool)}
        if isinstance(data.get("answers"), dict)
        else {},
    }


def _write(home: Path, data: dict[str, Any]) -> None:
    _path(home).parent.mkdir(parents=True, exist_ok=True)
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


def tesseract_ready(home: Path) -> bool:
    """The user said Tesseract is installed and its last test passed: only then is `ocr_image` offered."""
    data = load(home)
    result = data["results"].get("tesseract")
    return (
        data["answers"].get("tesseract") is True and isinstance(result, dict) and result.get("status") == "ok"
    )


def tavily_declined(home: Path) -> bool:
    """The user answered that the Tavily search service is not available to them: it is never tried."""
    return load(home)["answers"].get("tavily") is False


def save_plan(home: Path, plan: dict[str, str], manual: list[str] | None = None) -> None:
    data = load(home)
    data["plan"] = dict(plan)
    data["manual"] = list(manual or [])
    data["role_defaults"] = ROLE_DEFAULTS
    data["confirmed_at"] = now()
    _write(home, data)
