"""The outline a workbook is built from (JSON or YAML, D-339). A cell value that starts with "=" is a formula and stays one."""

from __future__ import annotations

import json
from typing import Any, Literal

from pydantic import BaseModel, Field, ValidationError

from forge.brand.kit import BrandKit
from forge.errors import ForgeError


class WorkbookError(ForgeError):
    """The outline or the workbook is wrong; the message says what to change."""


class Column(BaseModel):
    header: str
    width: float | None = None
    format: str | None = Field(
        default=None, description="Excel number format, e.g. '#,##0.00', '0.0%', 'yyyy-mm-dd'"
    )


class Validation(BaseModel):
    range: str
    choices: list[str] | None = None
    whole: tuple[int, int] | None = None
    decimal: tuple[float, float] | None = None
    message: str = ""


class Conditional(BaseModel):
    range: str
    rule: Literal["greater_than", "less_than", "between", "equal", "text_contains", "color_scale", "data_bar"]
    value: Any = None
    value2: Any = None
    fill: str = "FFC7CE"
    font: str | None = None


class ChartSpec(BaseModel):
    type: Literal["column", "bar", "line", "pie", "area", "scatter"] = "column"
    title: str = ""
    data: str = Field(description="Range of the values including the header row, e.g. B1:D13")
    categories: str | None = Field(
        default=None, description="Range of the category labels without header, e.g. A2:A13"
    )
    anchor: str = "H2"
    x_title: str = ""
    y_title: str = ""


class SheetSpec(BaseModel):
    name: str
    columns: list[Column] = Field(default_factory=list)
    rows: list[list[Any]] = Field(default_factory=list)
    table: bool = Field(
        default=False, description="Make the header and rows an Excel table (filter buttons, banding)"
    )
    freeze: str | None = Field(default=None, description="Cell above and left of which panes freeze, e.g. A2")
    total_row: dict[str, str] | None = Field(
        default=None,
        description="{'A': 'Total', 'B': 'SUM', 'C': 'AVERAGE'}: a label or a function per column",
    )
    validations: list[Validation] = Field(default_factory=list)
    conditional: list[Conditional] = Field(default_factory=list)
    charts: list[ChartSpec] = Field(default_factory=list)
    notes: dict[str, str] = Field(
        default_factory=dict, description="Cell comments, e.g. {'B1': 'Source: ...'}"
    )
    tab_colour: str | None = None


class WorkbookSpec(BaseModel):
    title: str = ""
    brand: BrandKit | None = Field(
        default=None, description="Company colours and fonts: header rows and cell fonts follow it"
    )
    sheets: list[SheetSpec]
    names: dict[str, str] = Field(
        default_factory=dict, description="Named ranges: {'TaxRate': 'Assumptions!$B$2'}"
    )


def parse_workbook(text: str, as_yaml: bool = False) -> WorkbookSpec:
    try:
        if as_yaml:
            import yaml

            data = yaml.safe_load(text)
        else:
            data = json.loads(text)
        return WorkbookSpec.model_validate(data)
    except (ValueError, ValidationError) as error:
        raise WorkbookError(f"The workbook outline is not valid: {str(error)[:600]}") from error
    except Exception as error:  # yaml errors
        raise WorkbookError(f"The workbook outline could not be read: {str(error)[:300]}") from error
