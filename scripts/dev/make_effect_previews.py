"""A still picture for every CSS effect of the ui-design-quality skill (TODO L0, D-517).

    python scripts/dev/make_effect_previews.py [effect-id ...]

Each effect is photographed on the demo markup that already proves it: the 40 micro-interactions (`mi-*`) use the `demo` snippet of their definition in
scripts/dev/micro_effects/ and are photographed in the state their test uses (hovered, focused, checked, pressed or running); the motion-kit effects (`fx-*`)
use the element that carries their class in the demo pages of tests/test_motion_more.py and tests/test_motion_fancy.py, or, for the first kit
(motion.css), the snippet in DEMOS below. The picture is a still frame of something that moves: it shows the look, not the motion. An effect with no demo
(React components, which need a build) is listed and skipped. Writes assets/preview/<id>.jpg and a `preview:` line in the asset. Needs Edge and Playwright;
run scripts/build_asset_catalogue.py afterwards."""

from __future__ import annotations

import importlib
import re
import sys
from html.parser import HTMLParser
from io import BytesIO
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(REPO / "scripts" / "dev"))

SKILL = REPO / "src" / "forge" / "skills" / "ui-design-quality"
EFFECTS = SKILL / "assets" / "effect"
PREVIEW = SKILL / "assets" / "preview"
RECIPES = SKILL / "recipes"
FRONT = re.compile(r"\A---\s*\n(.*?)\n---\s*\n", re.S)
BASE = (
    "body{margin:0;padding:36px;font:16px system-ui;background:#f8fafc;color:#0f172a;display:flex;align-items:center;justify-content:center;min-height:228px}"
    ".row{display:flex;flex-wrap:wrap;gap:24px;align-items:center;justify-content:center}"
    ".box{padding:14px 18px;background:#eef2ff;border-radius:10px}.bg{height:140px;width:260px;border-radius:10px;border:1px solid #e2e8f0}"
    ".tall{height:130px}"
    ":root{--color-brand-50:#eef2ff;--color-brand-100:#e0e7ff;--color-brand-200:#c7d2fe;--color-brand-500:#6366f1;--color-brand-600:#4f46e5;--color-brand-700:#3730a3;"
    "--color-ink-100:#f4f4f5;--color-ink-200:#e4e4e7;--color-ink-500:#71717a;--color-ink-700:#3f3f46;--color-ink-900:#18181b}"
)
# Demo snippets for the first motion kit (motion.css), which has no demo page of its own. The key is the effect id.
DEMOS: dict[str, str] = {
    "fx-bg-fade-edges": '<div class="bg-grid bg-fade-edges" style="width:340px;height:170px;border-radius:10px"></div>',
    "fx-button-shine": '<a href="#" class="btn-primary btn-shine" style="display:inline-block;padding:14px 26px;border-radius:999px;background:#4f46e5;color:#fff;text-decoration:none;font-weight:600">Book now</a>',
    "fx-float": '<svg class="float" width="120" height="120" viewBox="0 0 120 120" aria-hidden="true"><circle cx="60" cy="60" r="44" fill="#6366f1"/><circle cx="60" cy="60" r="22" fill="#e0e7ff"/></svg>',
    "fx-glass-surface": '<div style="position:relative;width:340px;height:170px;border-radius:14px;background:linear-gradient(135deg,#6366f1,#ec4899);display:grid;place-items:center"><div class="glass" style="padding:22px 30px;border-radius:14px">Frosted glass</div></div>',
    "fx-grain": '<div class="grain" style="position:relative;width:340px;height:170px;border-radius:14px;background:#6366f1"></div>',
    "fx-grid-pulse": '<div class="bg-grid grid-pulse" style="width:340px;height:170px;border-radius:10px;background-color:#fff"></div>',
    "fx-in-slide": '<div class="row"><div class="box in-left">slides in from the left</div><div class="box in-right">and from the right</div></div>',
    "fx-link-underline": '<a href="#" class="link-underline" style="font-size:22px;color:#1e1b4b;text-decoration:none">Read the full story</a>',
    "fx-page-entrance": '<div style="text-align:center"><h2 class="enter" style="--i:0;margin:0 0 8px">A page that arrives</h2><p class="enter" style="--i:1;margin:0">one element after the other</p></div>',
    "fx-pop": '<div class="pop" style="display:inline-grid;place-items:center;width:84px;height:84px;border-radius:50%;background:#4f46e5;color:#fff;font:700 28px system-ui">12</div>',
    "fx-scroll-reveal": '<div class="row"><div class="box reveal is-visible">reveal</div><div class="box reveal-left is-visible">reveal left</div><div class="box reveal-scale is-visible">reveal scale</div></div>',
    "fx-shake": '<input class="shake" value="not an e-mail" aria-label="E-mail" style="padding:12px 14px;border:2px solid #dc2626;border-radius:10px;font-size:16px;width:240px">',
    "fx-shimmer-text": '<h2 class="text-shimmer-light" style="margin:0;font-size:44px">Shimmering words</h2>',
    "fx-skeleton": '<div style="width:300px"><div class="skeleton" style="height:18px;border-radius:6px;width:60%"></div><div class="skeleton" style="height:14px;border-radius:6px;margin-top:12px"></div><div class="skeleton" style="height:14px;border-radius:6px;margin-top:10px;width:85%"></div></div>',
    "fx-toast-in": '<div class="toast-in" style="padding:14px 18px;border-radius:12px;background:#18181b;color:#fff;box-shadow:0 12px 30px -12px rgba(0,0,0,.5)">Saved. Your changes are live.</div>',
    "fx-aurora": '<div style="position:relative;isolation:isolate;width:420px;height:200px;overflow:hidden;border-radius:14px;background:#fff;display:grid;place-items:center"><div class="aurora"><i></i><i></i></div><b>Hero section</b></div>',
    "fx-border-beam": '<div class="beam" style="width:300px;height:130px;border-radius:16px;background:#0f172a;color:#fff;display:grid;place-items:center">Beam</div>',
}


class _First(HTMLParser):
    """Collects the outer HTML of the first element that has a given class."""

    def __init__(self, wanted: str) -> None:
        super().__init__()
        self.wanted, self.depth, self.parts, self.found = wanted, 0, [], False

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        classes = dict(attrs).get("class") or ""
        if not self.found and self.wanted in classes.split():
            self.found, self.depth = True, 0
        if self.found and self.depth >= 0:
            self.parts.append(self.get_starttag_text() or "")
            if tag not in ("br", "img", "input", "hr"):
                self.depth += 1

    def handle_endtag(self, tag: str) -> None:
        if self.found and self.depth > 0:
            self.parts.append(f"</{tag}>")
            self.depth -= 1
            if self.depth == 0:
                self.found, self.done = False, True
                self.wanted = "\0"  # stop matching

    def handle_data(self, data: str) -> None:
        if self.found and self.depth > 0:
            self.parts.append(data)


def element_with_class(html: str, name: str) -> str | None:
    parser = _First(name)
    parser.feed(html)
    return "".join(parser.parts) or None


def main_class(body: str) -> str | None:
    named = re.search(r'class="([a-z][\w-]*)', body) or re.search(r"`\.([a-z][\w-]*)`", body)
    return named.group(1) if named else None


def stylesheet_of(front: str) -> Path | None:
    for match in re.finditer(r"from:\s*(\S+?\.css)\b", front):
        path = SKILL / match.group(1).strip(",}")
        if path.is_file():
            return path
    return None


def demo_pages() -> list[tuple[str, str]]:
    """The demo pages of the motion tests: (the page's own <style> text, the page body markup)."""
    pages = []
    for module in ("tests.test_motion_more", "tests.test_motion_fancy"):
        text = str(importlib.import_module(module).PAGE).replace("{{", "{").replace("}}", "}")
        text = text.replace("{CELLS}", "<i></i>" * 24)
        style = "".join(re.findall(r"<style>(.*?)</style>", text, re.S))
        body = re.sub(r"<style>.*?</style>|<link[^>]*>|<title>.*?</title>", "", text, flags=re.S)
        pages.append((style, body))
    return pages


def micro_demos() -> dict[str, tuple[str, str, str]]:
    from micro_effects.defs_controls import CONTROLS
    from micro_effects.defs_surfaces import SURFACES

    return {e.id: (e.demo, e.action, e.probe) for e in [*CONTROLS, *SURFACES]}


def photograph(page: object, html: str, action: str = "none", probe: str = "") -> bytes:
    page.set_content(html)  # type: ignore[attr-defined]
    page.wait_for_timeout(250)  # type: ignore[attr-defined]
    root = (
        page.locator("main#demo > *").first
        if page.locator("main#demo").count()
        else page.locator("body > *").first
    )  # type: ignore[attr-defined]
    try:
        if action == "hover":
            root.hover()
        elif action == "focus":
            (root.locator(probe).first if probe else root).focus()
        elif action == "check":
            root.locator("input").first.check(force=True)
        elif action == "press":
            root.hover()
            page.mouse.down()  # type: ignore[attr-defined]
    except Exception:  # an action that cannot be done still gives the resting picture
        pass
    page.wait_for_timeout(700)  # type: ignore[attr-defined]
    return page.screenshot(clip={"x": 0, "y": 0, "width": 640, "height": 360})  # type: ignore[attr-defined, no-any-return]


def main(wanted: list[str]) -> None:
    from PIL import Image
    from playwright.sync_api import sync_playwright

    pages = demo_pages()
    micro = micro_demos()
    made, skipped = 0, []
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(channel="msedge", headless=True)
        page = browser.new_page(viewport={"width": 640, "height": 360})
        for path in sorted(EFFECTS.glob("*.md")):
            if wanted and path.stem not in wanted:
                continue
            text = path.read_text(encoding="utf-8")
            front = FRONT.match(text)
            if front is None or re.search(r"^preview:", front.group(1), re.M):
                continue
            sheet = stylesheet_of(front.group(1))
            if sheet is None:
                skipped.append(path.stem)
                continue
            css = sheet.read_text(encoding="utf-8")
            action, probe = "none", ""
            if path.stem in micro:
                demo, action, probe = micro[path.stem]
                html = f'<style>{css}</style><style>{BASE}</style><main id="demo" style="width:320px">{demo}</main>'
            else:
                snippet = DEMOS.get(path.stem)
                style = ""
                if snippet is None:
                    cls = main_class(text[front.end() :])
                    for page_style, body in pages:
                        if cls and (snippet := element_with_class(body, cls)):
                            style = page_style
                            break
                if not snippet:
                    skipped.append(path.stem)
                    continue
                html = f'<style>{css}</style><style>{BASE}</style><style>{style}</style><div class="row">{snippet}</div>'
            picture = Image.open(BytesIO(photograph(page, html, action, probe))).convert("RGB")
            PREVIEW.mkdir(parents=True, exist_ok=True)
            picture.save(PREVIEW / f"{path.stem}.jpg", quality=85)
            path.write_text(
                text[: front.end(1)] + f"\npreview: assets/preview/{path.stem}.jpg" + text[front.end(1) :],
                encoding="utf-8",
                newline="\n",
            )
            made += 1
        browser.close()
    print(f"{made} effect pictures made; no demo for: {', '.join(skipped) or 'none'}")


if __name__ == "__main__":
    main(sys.argv[1:])
