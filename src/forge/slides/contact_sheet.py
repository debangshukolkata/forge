"""Contact sheets (TODO P1.1, D-278): one picture with many slides in a numbered grid, so the model judges the flow,
the rhythm and the consistency of a deck in one look instead of one `view_image` per slide. A sheet holds at most
12 slides (3 x 4); longer decks get several sheets. Pillow is imported lazily."""

from __future__ import annotations

from pathlib import Path

COLUMNS = 3
PER_SHEET = 12
CELL_WIDTH = 560
GAP = 14
BACKGROUND = (226, 229, 234)
BADGE = (27, 36, 48)


class ContactSheetUnavailable(Exception):
    """Pillow is missing."""


def make_contact_sheets(
    pictures: list[Path],
    folder: Path,
    columns: int = COLUMNS,
    per_sheet: int = PER_SHEET,
    prefix: str = "contact-sheet",
) -> list[Path]:
    """Writes `contact-sheet-1.png`, `contact-sheet-2.png`, ... into `folder` from the slide pictures (in order) and
    returns their paths. The slide numbers are drawn on each tile."""
    try:
        from PIL import Image, ImageDraw
    except ImportError as error:
        raise ContactSheetUnavailable("Pillow is not installed; look at the slides one by one.") from error
    sheets: list[Path] = []
    for old in folder.glob(f"{prefix}-*.png"):
        old.unlink()
    for sheet_number, start in enumerate(range(0, len(pictures), per_sheet), start=1):
        group = pictures[start : start + per_sheet]
        tiles = []
        for offset, path in enumerate(group):
            with Image.open(path) as source:
                image = source.convert("RGB")
            height = round(CELL_WIDTH * image.height / image.width)
            tiles.append((start + offset + 1, image.resize((CELL_WIDTH, height))))
        cell_height = max(tile.height for _, tile in tiles)
        rows = -(-len(tiles) // columns)
        canvas = Image.new(
            "RGB",
            (columns * CELL_WIDTH + (columns + 1) * GAP, rows * cell_height + (rows + 1) * GAP),
            BACKGROUND,
        )
        draw = ImageDraw.Draw(canvas)
        for index, (number, tile) in enumerate(tiles):
            x = GAP + (index % columns) * (CELL_WIDTH + GAP)
            y = GAP + (index // columns) * (cell_height + GAP)
            canvas.paste(tile, (x, y))
            draw.rectangle((x, y, x + 46, y + 30), fill=BADGE)
            draw.text((x + 8, y + 8), str(number), fill=(255, 255, 255))
        target = folder / f"{prefix}-{sheet_number}.png"
        canvas.save(target)
        sheets.append(target)
    return sheets
