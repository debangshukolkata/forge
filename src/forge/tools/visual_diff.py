"""Visual checks on screenshots (TODO D3 and D6, D-312): do design variants really differ, and did a later edit change a screen that was
approved? Pure image comparison (Pillow), no model involved.

- `compare_designs`: pairwise layout similarity of screenshots plus, when design folders are given, whether their DESIGN.md files
  name the same accent colour and fonts. Variants asked for as different directions must not look like one another.
- `visual_baseline` / `visual_check`: keep an approved screenshot per screen; after later edits compare a new screenshot with it,
  report how much of the page changed and where, and save a diff picture. A change the task planned is approved again with
  `visual_baseline`; an unplanned one is a regression to fix."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from pydantic import Field

from forge.toolkit.base import Tool, ToolArgs, ToolContext, ToolResult

THUMB = (96, 96)
TOO_SIMILAR = 0.75  # layout similarity above this: the variants read as one design
PIXEL_TOLERANCE = 24  # per-channel difference that counts as a changed pixel (anti-aliasing and compression noise stay below)
UNCHANGED_BELOW = 0.002  # share of changed pixels below which a screen counts as unchanged
BAND = 8  # rows of the page reported when saying where it changed
VISUAL_FOLDER = ".forge/visual"
HEX = re.compile(r"#[0-9a-fA-F]{6}\b")
FONT = re.compile(
    r"(?:font-family|font|typeface|heading font|body font)[^\n:]*[:=]\s*[\"']?([A-Za-z][A-Za-z0-9 \-]{2,30})",
    re.IGNORECASE,
)


def _image(path: Path) -> Any:
    from PIL import Image

    return Image.open(path).convert("RGB")


def _edge_grid(image: Any, cells: int = 16) -> list[float]:
    """Where the picture has edges (block borders, text, rules), as a coarse grid of edge density: the structure of the layout,
    independent of colour."""
    from PIL import ImageFilter

    gray = image.convert("L")
    gray.thumbnail((256, 256))
    edges = gray.filter(ImageFilter.FIND_EDGES).point(lambda v: 255 if v > 24 else 0)
    small = edges.resize((cells, cells), resample=2)  # box-like average of the edge pixels per cell
    return [v / 255 for v in small.getdata()]


def layout_similarity(first: Any, second: Any) -> float:
    """1.0 for the same layout structure, towards 0 for different ones (colour and exact text do not count): compares where the two
    pictures have edges."""
    a, b = _edge_grid(first), _edge_grid(second)
    total = sum(x + y for x, y in zip(a, b, strict=True))
    if total == 0:
        return 1.0  # two blank pictures
    return float(1 - sum(abs(x - y) for x, y in zip(a, b, strict=True)) / total)


def palette(image: Any, colours: int = 4) -> list[str]:
    """The picture's main colours as hex, from a small quantised copy (background first)."""
    small = image.resize(THUMB).quantize(colors=colours, method=2).convert("RGB")
    counts = sorted(small.getcolors(maxcolors=THUMB[0] * THUMB[1]) or [], reverse=True)
    return [f"#{r:02x}{g:02x}{b:02x}" for _, (r, g, b) in counts[:colours]]


def _distance(first: str, second: str) -> float:
    a = [int(first[i : i + 2], 16) for i in (1, 3, 5)]
    b = [int(second[i : i + 2], 16) for i in (1, 3, 5)]
    return float(sum((x - y) ** 2 for x, y in zip(a, b, strict=True)) ** 0.5)


def palette_overlap(first: list[str], second: list[str], tolerance: float = 40.0) -> float:
    """The share of the first palette that has a close colour in the second."""
    if not first:
        return 0.0
    return sum(1 for colour in first if any(_distance(colour, other) < tolerance for other in second)) / len(
        first
    )


def design_tokens(folder: Path) -> tuple[list[str], list[str]]:
    """Hex colours and font names a folder's DESIGN.md names (empty when there is none)."""
    for name in ("DESIGN.md", "design.md"):
        try:
            text = (folder / name).read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        colours = [c.lower() for c in HEX.findall(text)]
        fonts = [f.strip().lower() for f in FONT.findall(text)]
        return colours, fonts
    return [], []


def compare_reports(
    pictures: dict[str, Path], folders: dict[str, Path] | None = None
) -> tuple[list[str], bool]:
    """Pairwise findings for named screenshots (and optional design folders) and whether any pair is too alike."""
    loaded = {name: _image(path) for name, path in pictures.items()}
    lines: list[str] = []
    alike = False
    names = list(loaded)
    for i, first in enumerate(names):
        for second in names[i + 1 :]:
            similarity = layout_similarity(loaded[first], loaded[second])
            colours = palette_overlap(palette(loaded[first]), palette(loaded[second]))
            verdict = "TOO SIMILAR" if similarity > TOO_SIMILAR else "different"
            alike = alike or similarity > TOO_SIMILAR
            lines.append(
                f"{first} vs {second}: layout similarity {similarity:.0%}, shared colours {colours:.0%}: {verdict}"
            )
    tokens = {name: design_tokens(folder) for name, folder in (folders or {}).items()}
    keys = list(tokens)
    for i, first in enumerate(keys):
        for second in keys[i + 1 :]:
            (colours_a, fonts_a), (colours_b, fonts_b) = tokens[first], tokens[second]
            if not (colours_a and colours_b) and not (fonts_a and fonts_b):
                continue
            same_accent = bool(colours_a and colours_b and colours_a[0] == colours_b[0])
            same_fonts = bool(fonts_a and fonts_b and fonts_a[0] == fonts_b[0])
            if same_accent or same_fonts:
                alike = True
                lines.append(
                    f"{first} vs {second}: DESIGN.md names the same "
                    + " and ".join(
                        x for x, ok in (("first colour", same_accent), ("first font", same_fonts)) if ok
                    )
                    + ": a different direction needs a different palette and typeface"
                )
    return lines, alike


def diff_pictures(
    baseline: Path, current: Path, output: Path | None = None
) -> tuple[float, list[tuple[int, int]]]:
    """(share of changed pixels, changed bands as pixel row ranges of the compared size). Writes a red-marked diff picture when asked."""
    from PIL import Image, ImageChops

    first, second = _image(baseline), _image(current)
    if first.size != second.size:
        second = second.resize(first.size)
    difference = ImageChops.difference(first, second).convert("L")
    mask = difference.point(lambda v: 255 if v > PIXEL_TOLERANCE else 0)
    changed = mask.histogram()[255] / (first.size[0] * first.size[1])
    width, height = first.size
    rows: list[tuple[int, int]] = []
    band_height = max(1, height // BAND)
    for index in range(BAND):
        top = index * band_height
        box = (0, top, width, min(height, top + band_height))
        if mask.crop(box).getbbox() is not None:
            rows.append((top, box[3]))
    if output is not None:
        marked = second.copy()
        red = Image.new("RGB", marked.size, (255, 0, 0))
        marked.paste(red, mask=mask.point(lambda v: 130 if v else 0))
        output.parent.mkdir(parents=True, exist_ok=True)
        marked.save(output)
    return changed, rows


def _resolve(context: ToolContext, path: str) -> Path:
    """A path the model gives: DebCraft's own `.forge/...` files by workspace root, everything else relative to the repository."""
    clean = path.replace("\\", "/")
    while clean.startswith("./") or clean.startswith("/"):
        clean = clean[2:] if clean.startswith("./") else clean[1:]
    base = context.workspace.root / clean if clean.startswith(".forge/") else context.workspace.path_of(clean)
    return context.workspace.jail.check(base)


def _name(raw: str) -> str:
    return re.sub(r"[^A-Za-z0-9_-]+", "-", raw).strip("-").lower()[:40] or "screen"


def _latest_screenshot(context: ToolContext) -> Path | None:
    shots = sorted((context.workspace.forge_dir / "screenshots").glob("shot-*.png"))
    return shots[-1] if shots else None


class CompareDesigns(Tool):
    name = "compare_designs"
    read_only = True
    description = (
        "Check that design variants really look different: give a screenshot per variant (and optionally each variant's folder with "
        "its DESIGN.md). Reports the layout similarity of every pair and flags a pair that reads as one design, or whose DESIGN.md "
        "files name the same first colour or font. Use it after you screenshot the variants of a 'give me three designs' request."
    )

    class Args(ToolArgs):
        screenshots: dict[str, str] = Field(
            description="Variant name -> screenshot path (e.g. {'a': '.forge/screenshots/shot-1.png'})"
        )
        folders: dict[str, str] = Field(
            default_factory=dict, description="Variant name -> its folder, for the DESIGN.md comparison"
        )

    async def run(self, args: CompareDesigns.Args, context: ToolContext) -> ToolResult:
        if len(args.screenshots) < 2:
            return ToolResult(ok=False, content="Give at least two screenshots to compare.")
        try:
            pictures = {name: _resolve(context, p) for name, p in args.screenshots.items()}
            folders = {name: _resolve(context, p) for name, p in args.folders.items()}
            lines, alike = compare_reports(pictures, folders)
        except ImportError:
            return ToolResult(
                ok=False, content="Pillow is not installed, so pictures cannot be compared here."
            )
        except (OSError, ValueError) as error:
            return ToolResult(ok=False, content=f"Could not read a picture: {error}")
        verdict = (
            "BLOCKER: some variants are too alike: change the layout (section order, grid, hero shape) and the palette and typeface "
            "of the later ones, not just the colours."
            if alike
            else "The variants differ."
        )
        return ToolResult(ok=True, content="\n".join([*lines, verdict]))


class VisualBaseline(Tool):
    name = "visual_baseline"
    read_only = False
    description = (
        "Approve a screenshot as the baseline of a screen (a name like 'home' or 'checkout-mobile'). Later `visual_check` compares new "
        "screenshots with it. Use it when a screen looks right; use it again after a change that was meant to alter the look."
    )

    class Args(ToolArgs):
        name: str = Field(description="Screen name, e.g. 'home-desktop'")
        screenshot: str = Field(default="", description="Screenshot path; default the latest one you took")

    async def run(self, args: VisualBaseline.Args, context: ToolContext) -> ToolResult:
        source = _resolve(context, args.screenshot) if args.screenshot else _latest_screenshot(context)
        if source is None or not source.is_file():
            return ToolResult(
                ok=False, content="No screenshot to approve: take one with browser_screenshot first."
            )
        target = _resolve(context, f"{VISUAL_FOLDER}/{_name(args.name)}.png")
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(source.read_bytes())
        return ToolResult(
            ok=True,
            content=f"Approved {source.name} as the baseline of '{_name(args.name)}' ({VISUAL_FOLDER}/{target.name}).",
        )


class VisualCheck(Tool):
    name = "visual_check"
    read_only = False
    description = (
        "Compare a screenshot with the approved baseline of the same screen and report how much of the page changed and where, with a diff "
        "picture (changes in red). A change you planned: look at it, then approve it again with visual_baseline. A change you did not "
        "plan is a regression: fix it. Run it for the screens an edit could touch (shared styles, layouts, components)."
    )

    class Args(ToolArgs):
        name: str
        screenshot: str = Field(default="", description="Screenshot path; default the latest one you took")

    async def run(self, args: VisualCheck.Args, context: ToolContext) -> ToolResult:
        name = _name(args.name)
        baseline = _resolve(context, f"{VISUAL_FOLDER}/{name}.png")
        if not baseline.is_file():
            return ToolResult(
                ok=False,
                content=f"No baseline for '{name}': approve one with visual_baseline when the screen looks right.",
            )
        current = _resolve(context, args.screenshot) if args.screenshot else _latest_screenshot(context)
        if current is None or not current.is_file():
            return ToolResult(
                ok=False, content="No screenshot to check: take one with browser_screenshot first."
            )
        diff_path = _resolve(context, f"{VISUAL_FOLDER}/{name}-diff.png")
        try:
            changed, rows = diff_pictures(baseline, current, diff_path)
        except ImportError:
            return ToolResult(
                ok=False, content="Pillow is not installed, so pictures cannot be compared here."
            )
        except OSError as error:
            return ToolResult(ok=False, content=f"Could not read a picture: {error}")
        if changed < UNCHANGED_BELOW:
            return ToolResult(
                ok=True,
                content=f"'{name}' is unchanged ({changed:.2%} of the pixels differ, below the noise level).",
            )
        where = ", ".join(f"{a}-{b}px" for a, b in rows[:BAND])
        return ToolResult(
            ok=True,
            content=(
                f"'{name}' changed: {changed:.1%} of the page differs, in the rows {where}. Diff picture: {VISUAL_FOLDER}/{name}-diff.png "
                "(look at it with view_image). If the edit was meant to change this screen, approve the new look with visual_baseline; "
                "if not, this is a regression: find which change caused it and fix it."
            ),
        )
