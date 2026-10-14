"""Builds the application-screen recipes of the ui-design-quality skill (D-366): standalone HTML files, their catalogue entries and two pictures each.

    python scripts/dev/make_app_screens.py [--no-previews] [id ...]

Writes recipes/app-screens/<id>.html, assets/section/app-<id>.md and (with Edge) assets/preview/app-<id>-desktop.jpg and -phone.jpg.
Run scripts/build_asset_catalogue.py afterwards. The screens live in scripts/dev/app_screens/ (kit.py has the shared stylesheet and charts)."""

from __future__ import annotations

import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "scripts" / "dev"))
sys.path.insert(0, str(REPO / "src"))

from app_screens import (  # noqa: E402
    screens_apps,
    screens_dashboards,
    screens_forms,
    screens_settings,
    screens_tables,
)
from app_screens.kit import page  # noqa: E402
from app_screens.screen import Screen  # noqa: E402

MODULES = [screens_dashboards, screens_tables, screens_forms, screens_settings, screens_apps]
SKILL = REPO / "src" / "forge" / "skills" / "ui-design-quality"
PREVIEW = SKILL / "assets" / "preview"
SOURCE = "authored for DebCraft (D-366, application screens for plain HTML apps)"
TESTED = "rendered in Edge at 1280 and 375 px: no sideways scroll, the style audit reports nothing, looked at (tests/test_app_screens.py, D-366)"

NOTE = """A complete, working application screen in plain HTML and CSS: {uses}. Open the file to see it, then bring it into the project and make it the
product's own. Do not ship it as it is.
1. Replace the `:root` block with the tokens exported from DESIGN.md (`design_md_export css-variables`); the screen only uses those variables, so the
   look follows the design system. Fetch and link the fonts the tokens name (`fetch_font`).
2. Change every word, name and number to the product's real content (no placeholder names left), keep the structure that fits the data, and remove what
   the product does not have. The icons are one inline sprite: keep the ones you use.
3. In a framework project, split it into components (the layout, the table, the chart cards) and keep the same classes or turn them into the project's
   utility classes. The charts are SVG shapes with HTML labels: feed them real series instead of the sample numbers.
4. Check it at 1280 and 375 px with `browser_screenshot`; on a phone the side navigation becomes a strip and tables scroll inside their frame."""


def asset_markdown(screen: Screen) -> str:
    tags = ", ".join(
        [
            *screen.tags,
            "app screen",
            "plain html",
            "css",
            "no build step",
            "dark" if screen.palette == "ink" else "light",
        ]
    )
    return (
        f'---\nid: app-{screen.id}\ntype: section\ntitle: "App screen: {screen.title}"\nsummary: "{screen.summary}"\n'
        f"moods: [{', '.join(screen.moods)}]\nproducts: [{', '.join(screen.products)}]\ntags: [{tags}]\ndensity: {screen.density}\ndependencies: []\n"
        f'licence: original\nsource: "{SOURCE}"\ntested: "{TESTED}"\nfiles:\n  - from: recipes/app-screens/{screen.id}.html\n    to: screens/{screen.id}.html\n---\n'
        f"{NOTE.format(uses=screen.uses)}\n"
    )


def photograph(files: list[Path]) -> None:
    from io import BytesIO

    from PIL import Image
    from playwright.sync_api import sync_playwright

    PREVIEW.mkdir(parents=True, exist_ok=True)
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(channel="msedge", headless=True)
        for file in files:
            for label, width, limit in (("desktop", 1280, 2400), ("phone", 375, 3000)):
                page_ = browser.new_page(viewport={"width": width, "height": 800})
                page_.goto(file.resolve().as_uri())
                page_.wait_for_timeout(300)
                image = Image.open(BytesIO(page_.screenshot(full_page=True))).convert("RGB")
                if image.height > limit:
                    image = image.crop((0, 0, image.width, limit))
                image.save(PREVIEW / f"app-{file.stem}-{label}.jpg", "JPEG", quality=78, optimize=True)
                page_.close()
        browser.close()


def main(argv: list[str]) -> int:
    wanted = {a for a in argv if not a.startswith("--")}
    folder = SKILL / "recipes" / "app-screens"
    folder.mkdir(parents=True, exist_ok=True)
    written: list[Path] = []
    for module in MODULES:
        for make in module.ALL:
            screen = make()
            if wanted and screen.id not in wanted:
                continue
            note = f"{screen.title}. {screen.summary} Use it for {screen.uses}."
            target = folder / f"{screen.id}.html"
            target.write_text(
                page(
                    screen.title,
                    note,
                    screen.palette,
                    screen.font,
                    screen.css,
                    screen.body,
                    screen.icons,
                    screen.extra_root,
                ),
                encoding="utf-8",
                newline="\n",
            )
            (SKILL / "assets" / "section" / f"app-{screen.id}.md").write_text(
                asset_markdown(screen), encoding="utf-8", newline="\n"
            )
            written.append(target)
            print("wrote", target.name)
    if "--no-previews" not in argv and written:
        photograph(written)
        print("pictures written")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
