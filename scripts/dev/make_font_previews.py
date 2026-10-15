"""Specimen pictures for the bundled font pairings (TODO L3, D-394).

    python scripts/dev/make_font_previews.py [pair-id ...]

For each assets/font-pairing/pair-*.md: renders a specimen (a headline in the display font, a paragraph and an interface line in the text font, in the
pairing's own script: Bengali and Devanagari get native sample text) with Edge from the bundled font files, saves assets/preview/<id>.jpg and adds the
`preview:` line to the asset's front matter. Needs Edge and Pillow; run it after changing a pairing."""

from __future__ import annotations

import re
import sys
import tempfile
from io import BytesIO
from pathlib import Path

SKILL = Path(__file__).resolve().parents[2] / "src" / "forge" / "skills" / "ui-design-quality"
PAIRINGS = SKILL / "assets" / "font-pairing"
PREVIEW = SKILL / "assets" / "preview"

SAMPLES = {
    "pair-bengali": (
        "বাংলা ভাষায় পরিষ্কার লেখা",
        "একটি ভালো নকশায় অক্ষরের আকার, দূরত্ব এবং ওজন একসাথে কাজ করে, যাতে পাঠক কোনো কষ্ট ছাড়াই পড়তে পারেন।",
        "Settings · Orders · Help",
    ),
    "pair-hindi": (
        "हिंदी में साफ़ और पढ़ने योग्य लेखन",
        "अच्छे डिज़ाइन में अक्षरों का आकार, दूरी और मोटाई मिलकर काम करते हैं, ताकि पाठक बिना थके पढ़ सकें।",
        "Settings · Orders · Help",
    ),
}
DEFAULT_SAMPLE = (
    "Quiet pages read faster",
    "Good typography is the part of a design people never notice: size, spacing and weight work together so that the reader can simply read.",
    "Settings · Orders · Help",
)


def families(css: str) -> list[str]:
    """Family names in the order a CSS file declares them."""
    seen: list[str] = []
    for name in re.findall(r"font-family:\s*'([^']+)'", css):
        if name not in seen:
            seen.append(name)
    return seen


def pairing_fonts(markdown: str) -> list[Path]:
    """The bundled CSS files a pairing copies, as paths inside the skill's fonts folder."""
    return [SKILL / source for source in re.findall(r"from:\s*(fonts/[a-z0-9-]+/[a-z0-9-]+\.css)", markdown)]


def specimen_html(pair_id: str, css_files: list[Path]) -> tuple[str, Path]:
    """The page and the folder it must be saved in so that the CSS's /fonts/ urls resolve to the bundled files."""
    faces: list[str] = []
    names: list[str] = []
    for css_file in css_files:
        css = css_file.read_text(encoding="utf-8")
        faces.append(css.replace("url(/fonts/", f"url({css_file.parent.as_uri()}/"))
        names.extend(families(css))
    display, text = names[0], names[-1]
    headline, paragraph, label = SAMPLES.get(pair_id, DEFAULT_SAMPLE)
    stack = ", ".join(f"'{n}'" for n in dict.fromkeys(names))
    page = f"""<!doctype html><meta charset="utf-8"><style>{"".join(faces)}
body{{margin:0;padding:44px 52px;width:760px;background:#fbfaf7;color:#1c1b19}}
h1{{font-family:'{display}',{stack},sans-serif;font-size:48px;line-height:1.2;margin:0 0 18px;font-weight:700;letter-spacing:-.01em}}
p{{font-family:'{text}',{stack},sans-serif;font-size:19px;line-height:1.65;margin:0 0 22px;color:#3b3a36}}
.row{{font-family:'{text}',{stack},sans-serif;font-size:14px;color:#6d6b64;border-top:1px solid #dcd9d0;padding-top:14px}}
</style><h1>{headline}</h1><p>{paragraph}</p><div class="row">{label}</div>"""
    return page, PREVIEW


def main(argv: list[str]) -> int:
    from PIL import Image
    from playwright.sync_api import sync_playwright

    wanted = set(argv)
    PREVIEW.mkdir(parents=True, exist_ok=True)
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(channel="msedge", headless=True)
        for markdown_file in sorted(PAIRINGS.glob("pair-*.md")):
            pair_id = markdown_file.stem
            if wanted and pair_id not in wanted:
                continue
            markdown = markdown_file.read_text(encoding="utf-8")
            page_html, _ = specimen_html(pair_id, pairing_fonts(markdown))
            with tempfile.TemporaryDirectory() as folder:
                html_file = Path(folder) / "specimen.html"
                html_file.write_text(page_html, encoding="utf-8")
                page = browser.new_page(viewport={"width": 864, "height": 120})
                page.goto(html_file.as_uri())
                page.evaluate("document.fonts.ready")
                page.wait_for_timeout(300)
                image = Image.open(BytesIO(page.screenshot(full_page=True))).convert("RGB")
                page.close()
            target = PREVIEW / f"{pair_id}.jpg"
            image.save(target, "JPEG", quality=80, optimize=True)
            line = f"preview: assets/preview/{pair_id}.jpg"
            if "\npreview:" not in markdown:
                markdown = markdown.replace("\ntested:", f"\n{line}\ntested:", 1)
                markdown_file.write_text(markdown, encoding="utf-8", newline="\n")
            print("wrote", target.name)
        browser.close()
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
