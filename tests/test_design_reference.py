"""DIE1: the browser read measures the type scale and the sections, and the reference note names the two lists to fill."""

from __future__ import annotations

import pytest

from forge.designsystem.reference import reference_note, rhythm
from forge.tools.design_inspire import COMPUTED_STYLES_SCRIPT

PAGE = (
    "<!doctype html><html><head><title>Kiln &amp; Co</title><style>"
    "body{margin:0;font-family:Georgia,serif;font-size:16px}h1{font-size:56px;font-weight:700}h2{font-size:32px}"
    "section{padding:80px 40px;min-height:160px}.cols{display:grid;grid-template-columns:1fr 1fr 1fr;gap:20px}"
    "</style></head><body><main>"
    "<section><h1>Hand-thrown pots</h1><p>Made in the old mill.</p><a class='btn' href='#'>Book</a></section>"
    "<section><h2>Classes</h2><div class='cols'><div>One</div><div>Two</div><div>Three</div></div></section>"
    "</main></body></html>"
)


def test_the_note_lists_the_measurements_and_the_two_empty_lists() -> None:
    data = {
        "title": "Kiln",
        "scale": {
            "h1": {
                "size": 56,
                "weight": "700",
                "lineHeight": "60px",
                "letterSpacing": "normal",
                "family": "Georgia",
            },
            "body": {"size": 16},
        },
        "sections": [
            {
                "tag": "section",
                "heading": "Pots",
                "height": 400,
                "paddingTop": 80,
                "columns": 3,
                "pictures": 2,
                "buttons": 1,
            }
        ],
        "images": 2,
        "maxWidth": 1100,
    }
    note = reference_note(data, "https://example.com", "layout")
    assert "h1: 56px" in note and "ratio of the largest heading to the body text: 3.5" in note
    assert '1. section "Pots": 400px high, 3 column(s), 2 picture(s), 1 button(s)' in note
    assert "## Principles to reuse" in note and "do not copy" in note
    assert rhythm(data["sections"]).startswith("section padding 80 to 80px")


async def test_the_browser_read_finds_the_scale_and_the_sections() -> None:
    pytest.importorskip("playwright.async_api")
    from playwright.async_api import async_playwright

    from forge.tools.web_render import RenderUnavailable, _launch

    async with async_playwright() as playwright:
        try:
            browser = await _launch(playwright)
        except RenderUnavailable as error:
            pytest.skip(str(error))
        try:
            page = await browser.new_page(viewport={"width": 1440, "height": 900})
            await page.set_content(PAGE)
            data = await page.evaluate(COMPUTED_STYLES_SCRIPT)
        finally:
            await browser.close()
    assert data["scale"]["h1"]["size"] == 56 and data["scale"]["h2"]["size"] == 32
    assert [s["heading"] for s in data["sections"]] == ["Hand-thrown pots", "Classes"]
    assert data["sections"][1]["columns"] == 3 and data["sections"][0]["buttons"] == 1
    assert data["sections"][0]["paddingTop"] == 80
