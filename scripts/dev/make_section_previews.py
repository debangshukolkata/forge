"""A reference picture for every page section of the ui-design-quality skill (TODO L10, D-395).

    python scripts/dev/make_section_previews.py

Builds the sections together on the charity template's tokens (the same build as tests/test_sections.py), photographs each one on its own at 1280 px with Edge and writes
assets/preview/sec-<name>.jpg, and sets `preview:` in the section's asset file. Directions get the picture of the design system they pair with. Needs ui-react/node_modules,
Edge and Pillow."""

from __future__ import annotations

import re
import sys
from io import BytesIO
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))
from tests import vite_harness as harness  # noqa: E402

SKILL = REPO / "src" / "forge" / "skills" / "ui-design-quality"
RECIPES = SKILL / "recipes"
PREVIEW = SKILL / "assets" / "preview"
SKIPPED = {"ArtTile"}  # a drawing, not a section


def kebab(name: str) -> str:
    return re.sub(r"(?<!^)(?=[A-Z])", "-", name).lower()


def gallery_files(names: list[str]) -> dict[str, str | bytes]:
    css = (RECIPES / "templates/charity/index.css").read_text(encoding="utf-8")
    css = css.replace('@import "./fonts/fraunces.css";\n', "").replace('@import "./fonts/inter.css";\n', "")
    files: dict[str, str | bytes] = {"src/index.css": css}
    for path in (RECIPES / "sections").glob("*.tsx"):
        files[f"src/sections/{path.name}"] = path.read_text(encoding="utf-8")
    imports = "\n".join(f'import {n} from "./sections/{n}";' for n in names)
    body = "\n".join(f"        <{n} />" for n in names)
    files["src/App.tsx"] = (
        f"{imports}\n\nexport default function App() {{\n  return (\n    <>\n{body}\n    </>\n  );\n}}\n"
    )
    return files


def set_preview(markdown_file: Path, relative: str) -> None:
    text = markdown_file.read_text(encoding="utf-8")
    if "\npreview:" in text:
        return
    markdown_file.write_text(
        text.replace("\ntested:", f"\npreview: {relative}\ntested:", 1), encoding="utf-8", newline="\n"
    )


def main() -> int:
    from PIL import Image
    from playwright.sync_api import sync_playwright

    if not harness.available():
        print("ui-react/node_modules is not installed")
        return 1
    names = sorted(p.stem for p in (RECIPES / "sections").glob("*.tsx") if p.stem not in SKIPPED)
    dist = harness.build("section-previews", gallery_files(names), title="Section previews")
    PREVIEW.mkdir(parents=True, exist_ok=True)
    with harness.serve(dist) as url, sync_playwright() as playwright:
        browser = playwright.chromium.launch(channel="msedge", headless=True)
        page = browser.new_page(viewport={"width": 1280, "height": 900})
        page.goto(url)
        page.wait_for_timeout(600)
        roots = page.locator("#root > *")
        if roots.count() != len(names):
            print(f"expected {len(names)} section roots, found {roots.count()}")
            return 1
        for index, name in enumerate(names):
            target = PREVIEW / f"sec-{kebab(name)}.jpg"
            asset = SKILL / "assets" / "section" / f"sec-{kebab(name)}.md"
            image = Image.open(BytesIO(roots.nth(index).screenshot())).convert("RGB")
            if image.height > 1800:
                image = image.crop((0, 0, image.width, 1800))
            image.save(target, "JPEG", quality=78, optimize=True)
            if asset.is_file():
                set_preview(asset, f"assets/preview/{target.name}")
            print("wrote", target.name, "" if asset.is_file() else "(no asset file for this section)")
        browser.close()
    for direction in sorted((SKILL / "assets" / "direction").glob("dir-*.md")):
        specimen = f"ds-{direction.stem[4:]}-specimen.jpg"
        if (PREVIEW / specimen).is_file():
            set_preview(direction, f"assets/preview/{specimen}")
            print("direction", direction.stem, "->", specimen)
    return 0


if __name__ == "__main__":
    sys.exit(main())
