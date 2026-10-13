"""Real text measurement through PowerPoint (TODO P2.18, D-287). The builder estimates whether text fits its box; with PowerPoint
installed it can instead ask PowerPoint for the true height and width of every text range and of every table, and report the
boxes whose text spills out or that run off the slide. Windows with PowerPoint only; without it the callers keep the estimate.
Same safety as the preview: the deck path goes through an environment variable, DebCraft's own variables are not passed on,
and a PowerPoint the user already had open stays open."""

from __future__ import annotations

import json
import os
import subprocess
from dataclasses import dataclass
from pathlib import Path

from forge.slides.preview import PreviewUnavailable, available
from forge.toolkit.private_env import without_private

TIMEOUT_S = 180
POINTS_PER_INCH = 72.0
SLACK_IN = 0.04  # the measure is exact; this absorbs rounding
MAX_REPORTED = 12

SCRIPT = r"""
$ErrorActionPreference = 'Stop'
$wasRunning = [bool](Get-Process POWERPNT -ErrorAction SilentlyContinue)
$app = New-Object -ComObject PowerPoint.Application
$rows = @()
try {
    $presentation = $app.Presentations.Open($env:DECK_FILE, -1, 0, 0)
    try {
        $slideWidth = $presentation.PageSetup.SlideWidth
        $slideHeight = $presentation.PageSetup.SlideHeight
        foreach ($slide in $presentation.Slides) {
            foreach ($shape in $slide.Shapes) {
                $row = [ordered]@{
                    slide = $slide.SlideIndex; name = $shape.Name; left = $shape.Left; top = $shape.Top
                    width = $shape.Width; height = $shape.Height; kind = 'shape'
                    slideWidth = $slideWidth; slideHeight = $slideHeight
                }
                if ($shape.HasTable) {
                    $row.kind = 'table'
                } elseif ($shape.HasTextFrame -and $shape.TextFrame2.HasText) {
                    $range = $shape.TextFrame2.TextRange
                    $row.kind = 'text'
                    $row.textHeight = $range.BoundHeight
                    $row.textWidth = $range.BoundWidth
                    $row.marginTop = $shape.TextFrame2.MarginTop
                    $row.marginBottom = $shape.TextFrame2.MarginBottom
                    $row.marginLeft = $shape.TextFrame2.MarginLeft
                    $row.marginRight = $shape.TextFrame2.MarginRight
                    $row.text = $range.Text.Substring(0, [Math]::Min(40, $range.Text.Length))
                    $row.autosize = $shape.TextFrame2.AutoSize
                }
                $rows += [pscustomobject]$row
            }
        }
    } finally { $presentation.Close() }
} finally {
    if (-not $wasRunning) { $app.Quit() }
}
$json = ConvertTo-Json -InputObject @($rows) -Depth 3 -Compress
# the console code page would turn curly quotes into plain ones inside the JSON: send every non-ASCII character escaped
[regex]::Replace($json, '[^\x00-\x7F]', { param($m) '\u{0:x4}' -f [int]$m.Value[0] })
"""


@dataclass(frozen=True)
class Measure:
    slide: int
    name: str
    kind: str  # text, table or shape
    left: float
    top: float
    width: float
    height: float
    slide_width: float
    slide_height: float
    text_height: float = 0.0
    text_width: float = 0.0
    margins: tuple[float, float, float, float] = (0.0, 0.0, 0.0, 0.0)  # top, bottom, left, right
    text: str = ""


def measure_deck(deck: Path) -> list[Measure]:
    """Every shape of the deck with PowerPoint's own text measurements (sizes in points)."""
    if not available():
        raise PreviewUnavailable("PowerPoint is not installed on this computer (or this is not Windows).")
    environment = {**without_private(os.environ), "DECK_FILE": str(deck.resolve())}
    try:
        done = subprocess.run(
            ["powershell", "-NoProfile", "-NonInteractive", "-Command", SCRIPT],
            capture_output=True,
            text=True,
            encoding="utf-8",
            timeout=TIMEOUT_S,
            env=environment,
            check=False,
        )
    except subprocess.TimeoutExpired as error:
        raise PreviewUnavailable(f"PowerPoint did not answer within {TIMEOUT_S} seconds.") from error
    if done.returncode != 0 or not done.stdout.strip():
        reason = (done.stderr or done.stdout).strip().splitlines()[:2]
        raise PreviewUnavailable("PowerPoint could not measure the deck: " + " ".join(reason)[:300])
    return parse_measures(done.stdout)


def parse_measures(output: str) -> list[Measure]:
    data = json.loads(output)
    if isinstance(data, dict):
        data = [data]
    return [
        Measure(
            slide=int(row["slide"]),
            name=str(row["name"]),
            kind=str(row["kind"]),
            left=float(row["left"]),
            top=float(row["top"]),
            width=float(row["width"]),
            height=float(row["height"]),
            slide_width=float(row["slideWidth"]),
            slide_height=float(row["slideHeight"]),
            text_height=float(row.get("textHeight") or 0),
            text_width=float(row.get("textWidth") or 0),
            margins=(
                float(row.get("marginTop") or 0),
                float(row.get("marginBottom") or 0),
                float(row.get("marginLeft") or 0),
                float(row.get("marginRight") or 0),
            ),
            text=str(row.get("text") or ""),
        )
        for row in data
    ]


def overflow_problems(measures: list[Measure]) -> list[str]:
    """Sentences naming the text that does not fit its box, and the tables or shapes that run off the slide. Sizes in inches."""
    found: list[str] = []
    slack = SLACK_IN * POINTS_PER_INCH
    for m in measures:
        label = f"slide {m.slide}, '{m.name}'" + (f" ({m.text!r})" if m.text else "")
        if m.kind == "text":
            room = m.height - m.margins[0] - m.margins[1]
            if m.text_height > room + slack:
                found.append(
                    f"{label}: the text is {m.text_height / POINTS_PER_INCH:.2f} in tall but its box has "
                    f"{room / POINTS_PER_INCH:.2f} in: enlarge the box, shorten the text or use a smaller size"
                )
            elif m.text_width > m.width - m.margins[2] - m.margins[3] + slack:
                found.append(
                    f"{label}: a word or line is wider than its box: widen the box or shorten the text"
                )
        if m.kind in ("table", "text") and (
            m.top + m.height > m.slide_height + slack or m.left + m.width > m.slide_width + slack
        ):
            what = (
                "the table grew past the slide edge"
                if m.kind == "table"
                else "the box extends past the slide edge"
            )
            found.append(f"{label}: {what}: remove rows, shorten text or make it smaller")
    return found[:MAX_REPORTED]
