"""D-419: the imagery rule follows the DESIGN.md composition. A brand page (a `lay-...` or `custom` composition) needs its pictures even when it holds a form (a booking page for a
photography studio); an application screen (`app-...`) does not; a page with no DESIGN.md is judged as before."""

from __future__ import annotations

from pathlib import Path

import pytest

from forge.tools.ui_audit import _brand_page, audit_page
from tests.test_ui_audit_alignment import HEAD, PICTURE, TEXT

NL = chr(10)


def design(composition: str) -> str:
    return "---" + NL + "composition: " + composition + NL + "---" + NL + "# Kestrel" + NL


def form_page() -> str:
    inputs = "".join(f"<label>Field {n} <input></label> " for n in range(9))
    return (
        TEXT
        + "<form>"
        + inputs
        + "<button>Pay</button></form><p>"
        + "More text about the studio. " * 30
        + "</p>"
        + "<hr>" * 12
    )


async def audit(body: str, root: Path | None = None) -> str:
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
            return await audit_page(page, root)
        finally:
            await browser.close()


def test_only_a_page_composition_makes_a_brand_page(tmp_path: Path) -> None:
    assert not _brand_page(None) and not _brand_page(tmp_path)
    (tmp_path / "DESIGN.md").write_text(design("lay-editorial-split"), encoding="utf-8")
    assert _brand_page(tmp_path)
    (tmp_path / "DESIGN.md").write_text(design("custom a ticket stub layout"), encoding="utf-8")
    assert _brand_page(tmp_path)
    (tmp_path / "DESIGN.md").write_text(design("app-form-wizard"), encoding="utf-8")
    assert not _brand_page(tmp_path)


async def test_a_brand_page_with_a_form_needs_pictures_and_an_application_screen_does_not(
    tmp_path: Path,
) -> None:
    assert "no imagery at all" not in await audit(
        form_page()
    )  # no DESIGN.md: nine controls make it an application, as before
    (tmp_path / "DESIGN.md").write_text(design("lay-editorial-split"), encoding="utf-8")
    assert "BLOCKER: The page has no imagery at all" in await audit(form_page(), tmp_path)
    (tmp_path / "DESIGN.md").write_text(design("app-form-wizard"), encoding="utf-8")
    assert "no imagery at all" not in await audit(form_page(), tmp_path)
    (tmp_path / "DESIGN.md").write_text(design("custom a studio page"), encoding="utf-8")
    assert "no imagery at all" not in await audit(PICTURE + form_page(), tmp_path)
