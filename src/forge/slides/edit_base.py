"""Shared pieces of the edit operation models."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict

HEX = r"^#?[0-9A-Fa-f]{6}$"
CHART_TYPES = {
    "column": "COLUMN_CLUSTERED",
    "stacked_column": "COLUMN_STACKED",
    "bar": "BAR_CLUSTERED",
    "stacked_bar": "BAR_STACKED",
    "line": "LINE_MARKERS",
    "area": "AREA",
    "stacked_area": "AREA_STACKED",
    "pie": "PIE",
    "donut": "DOUGHNUT",
}


class Op(BaseModel):
    model_config = ConfigDict(extra="forbid")


def rgb(value: str) -> Any:
    from pptx.dml.color import RGBColor

    factory: Any = RGBColor
    return factory.from_string(value.lstrip("#").upper())
