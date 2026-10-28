"""Turn two older recipe notes into catalogue assets (TODO L0, D-508).

    python scripts/dev/make_recipe_assets.py

Reads `recipes/palettes-and-fonts.md` (the palette table) and `recipes/css-techniques.md` (one asset per `##` section) and writes
`assets/palette/pal-*.md`, `assets/css-technique/css-*.md` and a swatch picture per palette in `assets/preview/`. The recipe notes stay the
source: edit them, rerun this, then `python scripts/build_asset_catalogue.py`. Needs Pillow."""

from __future__ import annotations

import re
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

SKILL = Path(__file__).resolve().parents[2] / "src" / "forge" / "skills" / "ui-design-quality"
RECIPES = SKILL / "recipes"
ASSETS = SKILL / "assets"
HEX = re.compile(r"#[0-9a-fA-F]{6}")

TECHNIQUE_MOODS = {
    "Layout": ["responsive"],
    "Selectors that remove JavaScript": ["selectors"],
    "Colour": ["oklch"],
    "Depth, surfaces, effects": ["shadows"],
    "Animation techniques": ["scroll", "transitions"],
    "Native HTML that replaces widgets": ["dialog", "popover"],
    "Typography details": ["typesetting"],
    "Responsive and accessibility basics": ["focus", "contrast"],
}


def slug(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")


def write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8", newline="\n")


def swatch_picture(asset_id: str, mood: str, colours: list[str]) -> str:
    """A 640x360 card: the colours as bands and the mood as a caption. Returns the preview path relative to the skill folder."""
    width, height = 640, 360
    image = Image.new("RGB", (width, height), colours[-1] if len(colours) > 3 else "#ffffff")
    draw = ImageDraw.Draw(image)
    band = width // len(colours)
    for index, colour in enumerate(colours):
        draw.rectangle([index * band, 0, (index + 1) * band, 250], fill=colour)
        draw.text(
            (index * band + 10, 225),
            colour,
            fill="#ffffff" if sum(int(colour[i : i + 2], 16) for i in (1, 3, 5)) < 384 else "#111111",
            font=ImageFont.load_default(),
        )
    draw.rectangle([0, 250, width, height], fill="#ffffff")
    draw.text((16, 280), mood, fill="#111111", font=ImageFont.load_default(size=22))
    target = ASSETS / "preview" / f"{asset_id}.jpg"
    target.parent.mkdir(parents=True, exist_ok=True)
    image.save(target, quality=85)
    return f"assets/preview/{asset_id}.jpg"


def make_palettes() -> int:
    text = (RECIPES / "palettes-and-fonts.md").read_text(encoding="utf-8")
    count = 0
    for line in text.splitlines():
        cells = [cell.strip() for cell in line.strip().strip("|").split("|")]
        if len(cells) != 5 or not HEX.search(cells[1]) or cells[0] == "Mood":
            continue
        mood, accent, surfaces, text_colour, use = cells
        colours = [c.lower() for c in HEX.findall(" ".join(cells[1:4]))]
        asset_id = f"pal-{slug(mood.split('(')[0])}"
        preview = swatch_picture(asset_id, mood, colours[:6])
        products = [word.strip() for word in use.split(",")]
        body = (
            f"## {mood}\n\n- Accent: {accent}\n- Surfaces: {surfaces}\n- Text: {text_colour}\n- Used for: {use}\n\n"
            "Use one accent scale and one neutral scale and semantic ok/warn/error colours; write the choice at the top of the CSS file. "
            "Check text contrast 4.5:1 before using a pair. Do not reuse the reference page's palette.\n"
        )
        header = (
            f'---\nid: {asset_id}\ntype: palette\ntitle: "{mood}"\nsummary: "One accent and neutral surfaces for {use}."\n'
            f"moods: [{slug(mood.split('(')[0]).replace('-', ', ')}]\nproducts: [{', '.join(products)}]\ntags: [palette, colour]\n"
            f'density: any\ndependencies: []\nlicence: original\nsource: "authored for DebCraft (recipes/palettes-and-fonts.md)"\n'
            f"tested: contrast pairs read from the recipe table; picture is the swatch sheet\npreview: {preview}\n---\n\n"
        )
        write(ASSETS / "palette" / f"{asset_id}.md", header + body)
        count += 1
    return count


def make_techniques() -> int:
    text = (RECIPES / "css-techniques.md").read_text(encoding="utf-8")
    count = 0
    for block in re.split(r"^## ", text, flags=re.M)[1:]:
        title, _, body = block.partition("\n")
        title = title.strip()
        asset_id = f"css-{slug(title)}"
        moods = TECHNIQUE_MOODS.get(title, ["any"])
        header = (
            f'---\nid: {asset_id}\ntype: css-technique\ntitle: "{title}"\n'
            f'summary: "Snippets for {title.lower()}."\n'
            f"moods: [{', '.join(moods)}]\nproducts: [web, landing, app, dashboard]\ntags: [css, html, native, no dependency]\n"
            f'density: any\ndependencies: []\nlicence: original\nsource: "authored for DebCraft (recipes/css-techniques.md)"\n'
            f"tested: snippets follow current Chromium (Edge) behaviour; checked when the recipe was written (D-251)\n---\n\n"
        )
        write(ASSETS / "css-technique" / f"{asset_id}.md", header + f"## {title}\n{body.rstrip()}\n")
        count += 1
    return count


if __name__ == "__main__":
    print(f"{make_palettes()} palettes, {make_techniques()} CSS technique assets written")
