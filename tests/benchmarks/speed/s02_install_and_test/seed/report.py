"""Builds a short text report from a YAML file of weekly figures."""

from __future__ import annotations

from datetime import date

import yaml
from dateutil.parser import parse as parse_date
from tabulate import tabulate


def load(path: str) -> list[dict[str, object]]:
    with open(path, encoding="utf-8") as handle:
        return list(yaml.safe_load(handle)["weeks"])


def build_report(weeks: list[dict[str, object]]) -> str:
    rows = []
    for week in weeks:
        start: date = parse_date(str(week["start"])).date()
        rows.append([start.isoformat(), start.strftime("%b %d"), week["sales"]])
    total = sum(int(w["sales"]) for w in weeks)  # type: ignore[call-overload]
    return tabulate(rows, headers=["Week of", "Label", "Sales"]) + f"\nTotal: {total}"
