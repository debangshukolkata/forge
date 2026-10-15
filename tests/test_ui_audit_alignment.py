"""D-419: the audit finds the defects the user pointed at on the night-2 pages: controls in the browser font, text running into its neighbour, cards of uneven height,
a grooved fieldset, and a booking form that has no pictures (a form is not an application)."""

from __future__ import annotations

import pytest

from forge.tools.ui_audit import audit_page

STYLE = """<style>
body{margin:0;font-family:Georgia,serif;background:#faf8f6;color:#1d1a17;font-size:16px;line-height:1.5}
h1{font-size:44px;margin:24px}p{margin:8px 24px}
.row{display:flex;margin:16px 24px;width:320px}
.card{background:#fff;border:1px solid #ddd;border-radius:12px;padding:16px;width:200px;margin:8px}
.cards{display:flex;align-items:flex-start;margin:16px}
</style>"""

HEAD = "<!doctype html><html><head>" + STYLE + "</head><body>"
TEXT = "<h1>Kestrel Studio</h1><p>Light-filled photography studio rental by the hour, in the old mill building by the river.</p>"
PICTURE = (
    '<svg width="400" height="260" viewBox="0 0 400 260" role="img" aria-label="The studio"><rect width="400" height="260" fill="#e9d8c4"/>'
    '<circle cx="90" cy="80" r="40" fill="#c9792b"/><rect x="150" y="120" width="180" height="90" fill="#7a5a3a"/><path d="M0 220 L400 200 L400 260 L0 260Z" fill="#4f3b27"/></svg>'
)


async def audit(body: str, root: object = None) -> str:
    pytest.importorskip("playwright.async_api")
    from playwright.async_api import async_playwright

    from forge.tools.web_render import RenderUnavailable, _launch

    async with async_playwright() as playwright:
        try:
            browser = await _launch(playwright)
        except RenderUnavailable as error:
            pytest.skip(str(error))
        try:
            page = await browser.new_page(viewport={"width": 1280, "height": 900})
            await page.set_content(HEAD + body + "</body></html>")
            return await audit_page(page, root)  # type: ignore[arg-type]
        finally:
            await browser.close()


async def test_controls_in_the_browser_font_are_found_and_font_inherit_fixes_them() -> None:
    form = (
        "<form><fieldset style='border:1px solid #ddd;margin:16px 24px'><legend>Studio space</legend>"
        "<input placeholder='Your name'><select><option>Loft</option></select><button>Book now</button></fieldset></form>"
    )
    found = await audit(TEXT + PICTURE + form)
    assert "use the browser font instead of the page font" in found and "font: inherit" in found
    fixed = await audit(
        TEXT + PICTURE + "<style>button,input,select,textarea,legend{font:inherit}</style>" + form
    )
    assert "browser font" not in fixed


async def test_a_name_and_its_price_with_no_space_are_found() -> None:
    crowded = (
        "<div class='row'><span style='width:40px;overflow:visible;white-space:nowrap'>Cyclorama</span>"
        "<span>&pound;80 per hour</span></div>"
    )
    spaced = "<div class='row' style='gap:16px'><span>Cyclorama</span><span>&pound;80 per hour</span></div>"
    assert "Text runs into its neighbour" in await audit(TEXT + PICTURE + crowded)
    assert "Text runs into its neighbour" not in await audit(TEXT + PICTURE + spaced)


async def test_cards_of_one_row_with_different_heights_are_found() -> None:
    uneven = (
        "<div class='cards'><div class='card'><h3>Term time</h3><p>Wednesday to Sunday</p><p>Morning</p><p>Afternoon</p></div>"
        "<div class='card'><h3>School holidays</h3><p>Every single day of the week</p></div><div class='card'><h3>Quiet sessions</h3><p>First Sunday of each month</p></div></div>"
    )
    even = uneven.replace("align-items:flex-start", "")
    assert "not aligned: their tops or heights differ" in await audit(TEXT + PICTURE + uneven)
    assert "not aligned: their tops or heights differ" not in await audit(
        TEXT + PICTURE + even.replace("class='cards'", "class='cards' style='align-items:stretch'")
    )


async def test_a_fieldset_with_the_browser_border_is_found() -> None:
    grooved = "<form><fieldset style='margin:16px 24px'><legend>Space</legend><label>Name <input></label></fieldset></form>"
    assert "default fieldset border" in await audit(TEXT + PICTURE + grooved)
