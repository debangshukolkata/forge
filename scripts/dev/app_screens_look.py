"""Renders every application-screen recipe at desktop and phone width: prints sideways scroll and the style audit, writes pictures to test-artifacts/app-screens/ (D-366).

python scripts/dev/app_screens_look.py [id ...]"""

from __future__ import annotations

import sys
from pathlib import Path

from playwright.sync_api import sync_playwright

from forge.tools.ui_audit import AUDIT_SCRIPT

REPO = Path(__file__).resolve().parents[2]
folder = REPO / "src" / "forge" / "skills" / "ui-design-quality" / "recipes" / "app-screens"
out = REPO / "test-artifacts" / "app-screens"
out.mkdir(parents=True, exist_ok=True)
wanted = set(sys.argv[1:])
with sync_playwright() as p:
    browser = p.chromium.launch(channel="msedge", headless=True)
    for file in sorted(folder.glob("*.html")):
        if wanted and file.stem not in wanted:
            continue
        for name, width in (("desktop", 1280), ("phone", 375)):
            page = browser.new_page(viewport={"width": width, "height": 800})
            page.goto(file.resolve().as_uri())
            page.wait_for_timeout(300)
            wide = page.evaluate("document.documentElement.scrollWidth - window.innerWidth")
            findings = (
                [f for f in page.evaluate(AUDIT_SCRIPT)["findings"] if "system font stack" not in f]
                if name == "desktop"
                else []
            )
            page.screenshot(path=str(out / f"{file.stem}-{name}.png"), full_page=True)
            print(f"{file.stem:24} {name:8} sideways={wide:>4}  audit={[f[:200] for f in findings]}")
            page.close()
    browser.close()
