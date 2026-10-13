"""Native charts at full strength (TODO P2.4, D-284): clustered and stacked columns and bars, lines, areas, pie and donut,
scatter, and column + line combinations with a second axis. Charts are real PowerPoint charts (editable data), styled quietly by
default (no frame, light gridlines, theme colours, labels only where they help) and every option is optional.

Data can be given inline (`categories` and `series`) or read from a CSV or Excel file in the workspace (`data_file`): the first
column is the categories, every other numeric column a series."""

from __future__ import annotations

import csv
import importlib
import io
from typing import Any

from forge.slides.errors import BuildError

MAX_PIE_SLICES = 6
MAX_CATEGORIES = 14
KIND_NAMES = {
    "column": "COLUMN_CLUSTERED",
    "bar": "BAR_CLUSTERED",
    "line": "LINE_MARKERS",
    "pie": "PIE",
    "donut": "DOUGHNUT",
    "area": "AREA",
    "stacked_column": "COLUMN_STACKED",
    "stacked_bar": "BAR_STACKED",
    "stacked_area": "AREA_STACKED",
    "scatter": "XY_SCATTER",
}
ONE_SERIES = ("pie", "donut")
LINE_KINDS = ("line", "scatter")


class ChartError(BuildError):
    """A chart cannot be built; the message names the problem."""


# --- data from files ---


def table_from_file(name: str, data: bytes) -> tuple[list[str], list[tuple[str, list[float]]]]:
    """(categories, [(series name, values)]) from a CSV or xlsx file: first column categories, the rest numbers."""
    if name.lower().endswith((".xlsx", ".xlsm")):
        try:
            workbook_module: Any = importlib.import_module("openpyxl")
        except ImportError as error:
            raise ChartError(
                "reading Excel files needs openpyxl: pip install openpyxl (the optional docs extra)"
            ) from error
        sheet = workbook_module.load_workbook(io.BytesIO(data), read_only=True, data_only=True).worksheets[0]
        rows = [["" if v is None else v for v in row] for row in sheet.iter_rows(values_only=True)]
    else:
        text = data.decode("utf-8-sig", errors="replace")
        try:
            dialect = csv.Sniffer().sniff(text[:2000], delimiters=",;\t")
        except csv.Error:
            dialect = csv.excel
        rows = [row for row in csv.reader(io.StringIO(text), dialect)]
    rows = [r for r in rows if any(str(c).strip() for c in r)]
    if len(rows) < 2 or len(rows[0]) < 2:
        raise ChartError(
            f"{name}: a chart file needs a header row and at least one data row with two columns"
        )
    header, body = [str(c).strip() for c in rows[0]], rows[1:]
    categories = [str(r[0]).strip() for r in body]
    series: list[tuple[str, list[float]]] = []
    for column in range(1, len(header)):
        values: list[float] = []
        for row in body:
            cell = str(row[column]).strip().replace(",", "") if column < len(row) else ""
            try:
                values.append(float(cell.rstrip("%")) if cell else 0.0)
            except ValueError:
                values = []
                break
        if values:
            series.append((header[column] or f"Series {column}", values))
    if not series:
        raise ChartError(f"{name}: no numeric column found after the first (categories) column")
    return categories, series


# --- the builder ---


def _colour(b: Any, token: str) -> Any:
    """A python-pptx colour from a theme name, series1.., or #RRGGBB."""
    from forge.slides.freeform import resolve

    return b.colour(resolve(b.theme, token))


def _axis_title(b: Any, axis: Any, text: str, size: float) -> None:
    axis.has_title = True
    frame = axis.axis_title.text_frame
    frame.text = text
    run = frame.paragraphs[0].runs[0]
    run.font.size = b.m["pt"](size)
    run.font.bold = False
    run.font.color.rgb = b.colour(b.theme.muted)


def _make_combo(chart: Any, line_indexes: list[int], secondary: bool) -> None:
    """Moves the series at `line_indexes` out of the column chart into a line chart, on a second value axis when asked."""
    from pptx.oxml.ns import qn
    from pptx.oxml.xmlchemy import OxmlElement

    plot_area = chart._chartSpace.chart.plotArea
    bar = plot_area.find(qn("c:barChart"))
    series = bar.findall(qn("c:ser"))
    line = OxmlElement("c:lineChart")
    line.append(_val("c:grouping", "standard"))
    line.append(_val("c:varyColors", "0"))
    for index in line_indexes:
        element = series[index]
        bar.remove(element)
        for old in element.findall(qn("c:invertIfNegative")):
            element.remove(old)
        element.append(_val("c:smooth", "0"))
        line.append(element)
    line.append(_val("c:marker", "1"))
    ids = [a.get("val") for a in bar.findall(qn("c:axId"))]
    if secondary:
        ids = ["60000001", "60000002"]
    for axis_id in ids:
        line.append(_val("c:axId", axis_id))
    bar.addnext(line)
    if secondary:
        category = OxmlElement("c:catAx")
        for child in (
            _val("c:axId", ids[0]),
            _scaling(),
            _val("c:delete", "1"),
            _val("c:axPos", "b"),
            _val("c:majorTickMark", "none"),
            _val("c:minorTickMark", "none"),
            _val("c:tickLblPos", "nextTo"),
            _val("c:crossAx", ids[1]),
            _val("c:crosses", "autoZero"),
        ):
            category.append(child)
        value = OxmlElement("c:valAx")
        for child in (
            _val("c:axId", ids[1]),
            _scaling(),
            _val("c:delete", "0"),
            _val("c:axPos", "r"),
            _val("c:numFmt", "General", attribute="formatCode", extra={"sourceLinked": "1"}),
            _val("c:majorTickMark", "none"),
            _val("c:minorTickMark", "none"),
            _val("c:tickLblPos", "nextTo"),
            _val("c:crossAx", ids[0]),
            _val("c:crosses", "max"),
        ):
            value.append(child)
        last_axis = plot_area.findall(qn("c:valAx"))[-1]
        last_axis.addnext(category)
        category.addnext(value)


def _val(tag: str, value: str, attribute: str = "val", extra: dict[str, str] | None = None) -> Any:
    from pptx.oxml.xmlchemy import OxmlElement

    element = OxmlElement(tag)
    element.set(attribute, value)
    for name, text in (extra or {}).items():
        element.set(name, text)
    return element


def _scaling() -> Any:
    from pptx.oxml.xmlchemy import OxmlElement

    scaling = OxmlElement("c:scaling")
    scaling.append(_val("c:orientation", "minMax"))
    return scaling


def add_chart(
    b: Any, slide: Any, options: Any, box: tuple[float, float, float, float], descr: str, font_size: float
) -> None:
    """Builds the chart described by `options` (a ChartBase) in `box` and styles it quietly from the theme."""
    chart_data: Any = importlib.import_module("pptx.chart.data")
    CategoryChartData, XyChartData = chart_data.CategoryChartData, chart_data.XyChartData
    from pptx.enum.chart import XL_CHART_TYPE, XL_LEGEND_POSITION, XL_MARKER_STYLE, XL_TICK_MARK

    where = f"slide {b.report.number}"
    kind = options.kind
    categories = list(options.categories)
    series = list(options.series)
    if options.data_file:
        names, columns = table_from_file(options.data_file, b.read_image(options.data_file))
        categories = names
        series = _series_from(options, columns)
    if not series:
        raise ChartError(f"{where}: the chart has no series (give `series` or a `data_file`)")
    if kind in ONE_SERIES and len(series) != 1:
        raise ChartError(f"{where}: a {kind} chart takes exactly one series")
    if kind == "scatter":
        for item in series:
            if not item.points:
                raise ChartError(f"{where}: scatter series '{item.name}' needs `points` as [x, y] pairs")
        data: Any = XyChartData()
        for item in series:
            made = data.add_series(item.name)
            for x, y in item.points:
                made.add_data_point(x, y)
    else:
        for item in series:
            if len(item.values) != len(categories):
                raise ChartError(
                    f"{where}: series '{item.name}' has {len(item.values)} values but there are {len(categories)} categories"
                )
        data = CategoryChartData()
        data.categories = categories
        for item in series:
            data.add_series(item.name, item.values)
    line_indexes = [i for i, item in enumerate(series) if item.kind == "line"]
    secondary = any(item.axis == "secondary" for item in series)
    if (line_indexes or secondary) and kind != "column":
        raise ChartError(
            f"{where}: a combination chart needs kind 'column' with some series set to kind 'line'"
        )
    if secondary and not line_indexes:
        raise ChartError(
            f"{where}: a second axis is for line series: set kind 'line' on the series that use it"
        )
    chart_type = getattr(XL_CHART_TYPE, KIND_NAMES[kind])
    frame = slide.shapes.add_chart(chart_type, *(b.m["inches"](v) for v in box), data)
    frame._element.nvGraphicFramePr.cNvPr.set("descr", descr)
    chart = frame.chart
    chart.font.size, chart.font.name = b.m["pt"](font_size), b.theme.body_font
    chart.font.color.rgb = b.colour(b.theme.text)
    if options.title:
        chart.has_title = True
        chart.chart_title.text_frame.text = options.title
        title_run = chart.chart_title.text_frame.paragraphs[0].runs[0]
        title_run.font.size, title_run.font.bold = b.m["pt"](font_size + 2), True
        title_run.font.color.rgb = b.colour(b.theme.text)
    else:
        chart.has_title = False
    if line_indexes:
        _make_combo(chart, line_indexes, secondary)
    many = len(series) > 1
    legend = options.legend
    show_legend = legend != "none" and (legend != "auto" or many or kind in ONE_SERIES)
    chart.has_legend = show_legend
    if show_legend:
        chart.legend.position = {
            "auto": XL_LEGEND_POSITION.BOTTOM,
            "bottom": XL_LEGEND_POSITION.BOTTOM,
            "right": XL_LEGEND_POSITION.RIGHT,
            "top": XL_LEGEND_POSITION.TOP,
        }[legend]
        chart.legend.include_in_layout = False
    colours = [_colour(b, c) for c in options.colors] or [b.colour(c) for c in b.theme.palette]
    palette = [colours[i % len(colours)] for i in range(max(len(series), len(categories), 1))]
    labels = options.data_labels if options.data_labels is not None else (kind in ONE_SERIES or not many)
    number_format = options.number_format
    if kind in ONE_SERIES:
        plot = chart.plots[0]
        plot.has_data_labels = True
        labels_ = plot.data_labels
        labels_.number_format, labels_.number_format_is_linked = number_format or "0.#", False
        labels_.font.size = b.m["pt"](font_size)
        for index, point in enumerate(plot.series[0].points):
            point.format.fill.solid()
            point.format.fill.fore_color.rgb = (
                _colour(b, options.point_colors[index % len(options.point_colors)])
                if options.point_colors
                else palette[index % len(palette)]
            )
        if len(categories) > MAX_PIE_SLICES:
            b.warn(
                f"the {kind} chart has {len(categories)} slices: more than {MAX_PIE_SLICES} is hard to read, group the small ones"
            )
        if any(v < 0 for v in series[0].values):
            b.warn(f"the {kind} chart has a negative value, which a pie cannot show")
        return
    if len(categories) > MAX_CATEGORIES and kind != "scatter":
        b.warn(
            f"{len(categories)} categories: more than {MAX_CATEGORIES} will be crowded, group or filter them"
        )
    for plot in chart.plots:
        for index, item in enumerate(plot.series):
            number = index if len(chart.plots) == 1 else _series_number(series, plot, index)
            colour = palette[number % len(palette)]
            if kind in LINE_KINDS or item.__class__.__name__ == "LineSeries":
                item.format.line.color.rgb = colour
                item.format.line.width = b.m["pt"](3)
                if kind == "scatter":
                    item.format.line.fill.background()
                item.marker.style = XL_MARKER_STYLE.CIRCLE
                item.marker.size = 8
                item.marker.format.fill.solid()
                item.marker.format.fill.fore_color.rgb = colour
                item.marker.format.line.color.rgb = colour
                if options.smooth and kind != "scatter":
                    item.smooth = True
            else:
                item.format.fill.solid()
                item.format.fill.fore_color.rgb = colour
            if options.point_colors and not many and kind not in LINE_KINDS:
                for point_index, _ in enumerate(categories):
                    point = item.points[point_index]
                    point.format.fill.solid()
                    point.format.fill.fore_color.rgb = _colour(
                        b, options.point_colors[point_index % len(options.point_colors)]
                    )
        if kind == "scatter":
            continue  # an XY plot has no plot-level data labels in PowerPoint's chart model
        plot.has_data_labels = labels
        if labels:
            plot.data_labels.font.size = b.m["pt"](max(font_size - 2, 11))
            if number_format:
                plot.data_labels.number_format, plot.data_labels.number_format_is_linked = (
                    number_format,
                    False,
                )
    if options.gap_width is not None and hasattr(chart.plots[0], "gap_width"):
        chart.plots[0].gap_width = options.gap_width
    category_axis, value_axis, second_axis = _axes(chart)
    value_axis.major_gridlines.format.line.color.rgb = b.colour(b.theme.surface)
    value_axis.has_major_gridlines = options.gridlines
    value_axis.format.line.fill.background()
    value_axis.major_tick_mark = XL_TICK_MARK.NONE
    category_axis.major_tick_mark = XL_TICK_MARK.NONE
    category_axis.format.line.color.rgb = b.colour(b.theme.muted)
    for axis in (category_axis, value_axis):
        axis.tick_labels.font.size = b.m["pt"](font_size)
        axis.tick_labels.font.color.rgb = b.colour(b.theme.muted)
    if number_format:
        value_axis.tick_labels.number_format, value_axis.tick_labels.number_format_is_linked = (
            number_format,
            False,
        )
    if options.y_min is not None:
        value_axis.minimum_scale = options.y_min
    if options.y_max is not None:
        value_axis.maximum_scale = options.y_max
    if options.x_title:
        _axis_title(b, category_axis, options.x_title, font_size)
    if options.y_title:
        _axis_title(b, value_axis, options.y_title, font_size)
    if second_axis is not None:  # the right-hand axis of a combination chart: quiet, no gridlines of its own
        second_axis.has_major_gridlines = False
        second_axis.format.line.fill.background()
        second_axis.major_tick_mark = XL_TICK_MARK.NONE
        second_axis.tick_labels.font.size = b.m["pt"](font_size)
        second_axis.tick_labels.font.color.rgb = b.colour(b.theme.muted)
        if options.y2_number_format:
            second_axis.tick_labels.number_format = options.y2_number_format
            second_axis.tick_labels.number_format_is_linked = False
        if options.y2_title:
            _axis_title(b, second_axis, options.y2_title, font_size)


def _axes(chart: Any) -> tuple[Any, Any, Any]:
    """The category axis, the primary value axis and (combination charts) the secondary one, in document order; python-pptx's
    own `chart.value_axis` would return the wrong one once a second axis exists."""
    from pptx.oxml.ns import qn

    axis_module: Any = importlib.import_module("pptx.chart.axis")
    CategoryAxis, ValueAxis = axis_module.CategoryAxis, axis_module.ValueAxis

    plot_area = chart._chartSpace.chart.plotArea
    categories = plot_area.findall(qn("c:catAx"))
    values = plot_area.findall(qn("c:valAx"))
    if not categories:  # an XY (scatter) chart has two value axes: x first, then y
        return ValueAxis(values[0]), ValueAxis(values[1]), None
    return (
        CategoryAxis(categories[0]),
        ValueAxis(values[0]),
        ValueAxis(values[1]) if len(values) > 1 else None,
    )


def _series_from(options: Any, columns: list[tuple[str, list[float]]]) -> list[Any]:
    from forge.slides.spec import Series

    return [Series(name=n, values=v) for n, v in columns]


def _series_number(series: list[Any], plot: Any, index: int) -> int:
    """The position in the user's series list of the `index`-th series of one plot of a combination chart."""
    names = [item.name for item in plot.series]
    return next((i for i, s in enumerate(series) if s.name == names[index]), index)
