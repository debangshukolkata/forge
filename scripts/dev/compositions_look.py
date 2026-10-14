"""Renders every composition recipe at desktop and phone width, prints sideways scroll and the audit, writes pictures to test-artifacts/compositions/."""

from pathlib import Path

from playwright.sync_api import sync_playwright

from forge.tools.ui_audit import AUDIT_SCRIPT

folder = (
    Path(__file__).resolve().parents[2]
    / "src"
    / "forge"
    / "skills"
    / "ui-design-quality"
    / "recipes"
    / "compositions"
)
out = Path(__file__).resolve().parents[2] / "test-artifacts" / "compositions"
out.mkdir(parents=True, exist_ok=True)
with sync_playwright() as p:
    browser = p.chromium.launch(channel="msedge", headless=True)
    for file in sorted(folder.glob("*.html")):
        for name, width in (("desktop", 1280), ("phone", 375)):
            page = browser.new_page(viewport={"width": width, "height": 800})
            page.goto(file.resolve().as_uri())
            page.wait_for_timeout(300)
            wide = page.evaluate("document.documentElement.scrollWidth - window.innerWidth")
            findings = page.evaluate(AUDIT_SCRIPT)["findings"] if name == "desktop" else []
            page.screenshot(path=str(out / f"{file.stem}-{name}.png"), full_page=True)
            print(f"{file.stem:18} {name:8} sideways={wide:>4}  audit={[f[:70] for f in findings]}")
            page.close()
    browser.close()
