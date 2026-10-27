"""Reference pictures of the plain-HTML page compositions (BO9).

    python scripts/dev/make_composition_previews.py [name ...]

Photographs recipes/compositions/<name>.html in headless Edge at 1280 and 375 px and writes assets/preview/lay-<name>-desktop.jpg (1000 px wide) and
-phone.jpg (480 px wide), the first screens only so the files stay small. Without names every composition is photographed. Needs Edge and Pillow."""

from __future__ import annotations

import sys
from io import BytesIO
from pathlib import Path

SKILL = Path(__file__).resolve().parents[2] / "src" / "forge" / "skills" / "ui-design-quality"
PREVIEW = SKILL / "assets" / "preview"
SIZES = (("desktop", 1280, 1000, 2400), ("phone", 375, 480, 3000))  # label, viewport, saved width, height cap


def main(names: list[str]) -> int:
    from PIL import Image
    from playwright.sync_api import sync_playwright

    files = sorted((SKILL / "recipes" / "compositions").glob("*.html"))
    if names:
        files = [file for file in files if file.stem in names]
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(channel="msedge", headless=True)
        for file in files:
            for label, width, saved_width, limit in SIZES:
                page = browser.new_page(viewport={"width": width, "height": 800})
                page.goto(file.resolve().as_uri())
                page.wait_for_timeout(300)
                image = Image.open(BytesIO(page.screenshot(full_page=True))).convert("RGB")
                page.close()
                image = image.resize((saved_width, round(image.height * saved_width / image.width)))
                limit = round(limit * saved_width / width)
                if image.height > limit:
                    image = image.crop((0, 0, image.width, limit))
                image.save(PREVIEW / f"lay-{file.stem}-{label}.jpg", "JPEG", quality=78, optimize=True)
            print("wrote", file.stem)
        browser.close()
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
