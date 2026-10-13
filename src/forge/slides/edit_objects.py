"""Edit operations on tables and charts (D-289): add and remove rows and columns, change a chart's type, chart title, legend,
labels and colours."""

from __future__ import annotations

import re
from copy import deepcopy
from typing import Any, Literal

from pydantic import Field

from forge.slides.edit_base import CHART_TYPES, HEX
from forge.slides.edit_base import Op as _Op
from forge.slides.edit_base import rgb as _rgb
from forge.slides.edit_find import find_shape, slide_at
from forge.slides.edit_text import set_frame_text
from forge.slides.open_deck import DeckError


class TableRows(_Op):
    op: Literal["add_table_row", "delete_table_row"]
    slide: int
    shape: int | str
    row: int  # 1-based; add = insert before this row (number of rows + 1 = at the end), delete = this row
    values: list[str] = Field(default_factory=list)  # add only; a copy of the row above keeps the look


class TableColumns(_Op):
    op: Literal["add_table_column", "delete_table_column"]
    slide: int
    shape: int | str
    column: int  # 1-based, as for rows
    values: list[str] = Field(default_factory=list)  # add only, one per row from the top


class ChartType(_Op):
    op: Literal["change_chart_type"]
    slide: int
    shape: int | str
    kind: Literal[
        "column", "stacked_column", "bar", "stacked_bar", "line", "area", "stacked_area", "pie", "donut"
    ]


class ChartFormat(_Op):
    op: Literal["format_chart"]
    slide: int
    shape: int | str
    title: str | None = None  # "" removes it
    legend: bool | None = None
    data_labels: bool | None = None
    number_format: str | None = None  # e.g. '0.0"%"', '#,##0'
    colors: list[str] | None = None  # one per series (per slice for a pie)


# --- tables ---


def _table(deck: Any, slide: int, ref: int | str) -> tuple[Any, Any]:
    shape = find_shape(slide_at(deck, slide), ref)
    if not getattr(shape, "has_table", False) or not shape.has_table:
        raise DeckError(f'"{shape.name}" is not a table')
    return shape, shape.table


def _write_cell(cell: Any, value: str) -> None:
    set_frame_text(cell.text_frame, [value])


def _table_rows(deck: Any, op: TableRows) -> str:
    shape, table = _table(deck, op.slide, op.shape)
    rows = table._tbl.tr_lst
    if op.op == "delete_table_row":
        if not 1 <= op.row <= len(rows) or len(rows) == 1:
            raise DeckError(
                f"the table has {len(rows)} rows: there is no row {op.row} to delete (the last row cannot go)"
            )
        shape.height = max(shape.height - rows[op.row - 1].h, 1)
        table._tbl.remove(rows[op.row - 1])
        return f"deleted row {op.row} of the table on slide {op.slide}"
    if not 1 <= op.row <= len(rows) + 1:
        raise DeckError(f"the table has {len(rows)} rows: insert at 1 to {len(rows) + 1}")
    if len(op.values) > len(table.columns):
        raise DeckError(f"the table has {len(table.columns)} columns: {len(op.values)} values given")
    model = rows[min(op.row, len(rows)) - 1] if op.row > 1 else rows[min(1, len(rows) - 1)]
    fresh = deepcopy(model)
    for cell in fresh.tc_lst:
        for paragraph in cell.txBody.p_lst[1:]:
            cell.txBody.remove(paragraph)
    if op.row == len(rows) + 1:
        rows[-1].addnext(fresh)
    else:
        rows[op.row - 1].addprevious(fresh)
    index = op.row - 1
    for column in range(len(table.columns)):
        _write_cell(table.cell(index, column), op.values[column] if column < len(op.values) else "")
    shape.height = shape.height + fresh.h
    return f"added a row at {op.row} to the table on slide {op.slide}"


def _table_columns(deck: Any, op: TableColumns) -> str:
    _, table = _table(deck, op.slide, op.shape)
    grid = table._tbl.tblGrid
    columns = list(grid)
    total = sum(int(c.get("w")) for c in columns)
    if op.op == "delete_table_column":
        if not 1 <= op.column <= len(columns) or len(columns) == 1:
            raise DeckError(f"the table has {len(columns)} columns: there is no column {op.column} to delete")
        grid.remove(columns[op.column - 1])
        for row in table._tbl.tr_lst:
            row.remove(row.tc_lst[op.column - 1])
    else:
        if not 1 <= op.column <= len(columns) + 1:
            raise DeckError(f"the table has {len(columns)} columns: insert at 1 to {len(columns) + 1}")
        source = min(op.column, len(columns)) - 1
        new_grid = deepcopy(columns[source])
        (grid.append if op.column == len(columns) + 1 else columns[op.column - 1].addprevious)(new_grid)
        for number, row in enumerate(table._tbl.tr_lst):
            cell = deepcopy(row.tc_lst[source])
            for paragraph in cell.txBody.p_lst[1:]:
                cell.txBody.remove(paragraph)
            tcs = row.tc_lst
            if op.column == len(tcs) + 1:
                tcs[-1].addnext(cell)
            else:
                tcs[op.column - 1].addprevious(cell)
            _write_cell(
                table.cell(number, op.column - 1), op.values[number] if number < len(op.values) else ""
            )
    widths = list(table._tbl.tblGrid)  # the table keeps its overall width
    scale = total / sum(int(c.get("w")) for c in widths)
    for column in widths:
        column.set("w", str(int(int(column.get("w")) * scale)))
    return f"{'added' if op.op.startswith('add') else 'deleted'} column {op.column} of the table on slide {op.slide}"


# --- charts ---


def _chart_of(deck: Any, slide: int, ref: int | str) -> Any:
    shape = find_shape(slide_at(deck, slide), ref)
    if not getattr(shape, "has_chart", False) or not shape.has_chart:
        raise DeckError(f'"{shape.name}" is not a chart')
    return shape


def _change_chart_type(deck: Any, op: ChartType) -> str:
    from pptx.chart.data import CategoryChartData
    from pptx.enum.chart import XL_CHART_TYPE

    old = _chart_of(deck, op.slide, op.shape)
    plot = old.chart.plots[0]
    try:
        categories = [str(c) for c in plot.categories]
        series = [(s.name, list(s.values)) for p in old.chart.plots for s in p.series]
    except (AttributeError, ValueError) as error:
        raise DeckError("only charts with categories (not scatter or bubble) can change type") from error
    factory: Any = CategoryChartData
    data = factory()
    data.categories = categories
    for name, values in series:
        data.add_series(name, values)
    if op.kind in ("pie", "donut") and len(series) > 1:
        raise DeckError("a pie or donut shows one series: delete the others first with update_chart")
    created = slide_at(deck, op.slide).shapes.add_chart(
        getattr(XL_CHART_TYPE, CHART_TYPES[op.kind]), old.left, old.top, old.width, old.height, data
    )
    chart = created.chart
    chart.has_legend = len(series) > 1 or op.kind in ("pie", "donut")
    if chart.has_legend:
        chart.legend.include_in_layout = False
    chart.has_title = old.chart.has_title
    if old.chart.has_title and old.chart.chart_title.has_text_frame:
        chart.chart_title.text_frame.text = old.chart.chart_title.text_frame.text
    created._element.nvGraphicFramePr.cNvPr.set("name", old.name)
    old._element.addprevious(created._element)  # same place in the stacking order
    old._element.getparent().remove(old._element)
    return f'changed the chart "{old.name}" on slide {op.slide} to {op.kind}'


def _format_chart(deck: Any, op: ChartFormat) -> str:
    chart = _chart_of(deck, op.slide, op.shape).chart
    done = []
    if op.title is not None:
        chart.has_title = bool(op.title)
        if op.title:
            chart.chart_title.text_frame.text = op.title
        done.append("title")
    if op.legend is not None:
        chart.has_legend = op.legend
        if op.legend:
            chart.legend.include_in_layout = False
        done.append("legend")
    plot = chart.plots[0]
    if op.data_labels is not None or op.number_format is not None:
        plot.has_data_labels = True if op.number_format and op.data_labels is None else bool(op.data_labels)
        if plot.has_data_labels and op.number_format:
            plot.data_labels.number_format = op.number_format
            plot.data_labels.number_format_is_linked = False
        done.append("data labels")
    if op.colors:
        for colour in op.colors:
            if not re.fullmatch(HEX, colour):
                raise DeckError(f"colour {colour!r} is not hex like 0B6E4F")
        paint = [_rgb(c) for c in op.colors]
        if chart.chart_type.name in ("PIE", "DOUGHNUT"):
            for index, point in enumerate(plot.series[0].points):
                point.format.fill.solid()
                point.format.fill.fore_color.rgb = paint[index % len(paint)]
        else:
            for index, series in enumerate(plot.series):
                series.format.fill.solid()
                series.format.fill.fore_color.rgb = paint[index % len(paint)]
                if chart.chart_type.name.startswith("LINE"):
                    series.format.line.color.rgb = paint[index % len(paint)]
        done.append("colours")
    if not done:
        raise DeckError("give title, legend, data_labels, number_format or colors")
    return f"formatted the chart on slide {op.slide}: " + ", ".join(done)
