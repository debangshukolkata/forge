"""Renders the given application screens at 1280 and 375 px and prints scroll overflow and audit findings (a quick loop while authoring screens)."""

import sys
from pathlib import Path

from playwright.sync_api import sync_playwright

from forge.tools.ui_audit import AUDIT_SCRIPT

SKILL = Path(__file__).resolve().parents[2] / "src" / "forge" / "skills" / "ui-design-quality"
ids = sys.argv[1:]
with sync_playwright() as p:
    browser = p.chromium.launch(channel="msedge", headless=True)
    for screen in ids:
        file = SKILL / "recipes" / "app-screens" / f"{screen}.html"
        for width in (1280, 375):
            page = browser.new_page(viewport={"width": width, "height": 800})
            page.goto(file.resolve().as_uri())
            page.wait_for_timeout(200)
            over = page.evaluate("document.documentElement.scrollWidth - window.innerWidth")
            findings = []
            if width == 1280:
                findings = [
                    f for f in page.evaluate(AUDIT_SCRIPT)["findings"] if "system font stack" not in f
                ]
            print(f"{screen:20} {width:5} overflow={over:3}", ("OK" if not findings and over <= 1 else ""))
            for finding in findings:
                print("      -", finding[:230].encode("ascii", "replace").decode())
            page.close()
    browser.close()
