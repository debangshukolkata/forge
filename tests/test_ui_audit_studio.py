"""D-351: the audit finds the banned looks (generic gradients, grey placeholder boxes, too many accents) and missing interaction states."""

from __future__ import annotations

from pathlib import Path

import pytest

from forge.tools.ui_audit import audit_page, source_taste_problems

BAD = """<!doctype html><html><head><style>
body{margin:0;font-family:Arial;background:#fff;color:#222}
.hero{height:300px;background:linear-gradient(135deg,#7c3aed,#2563eb);color:#fff;padding:40px}
.ph{width:240px;height:200px;background:#d1d5db;margin:16px}
.a{display:inline-block;width:260px;height:120px;background:#dc2626}.b{display:inline-block;width:260px;height:120px;background:#16a34a}
.c{display:inline-block;width:260px;height:120px;background:#ca8a04}.d{display:inline-block;width:260px;height:120px;background:#2563eb}
.e{display:inline-block;width:260px;height:120px;background:#c026d3}
.tiny{font-size:11px}
</style></head><body><div class="hero"><h1>Launch week</h1></div><div class="ph"></div>
<div><div class="a"></div><div class="b"></div><div class="c"></div><div class="d"></div><div class="e"></div></div>
<p class="tiny">This small print is much too small to read comfortably on a desktop screen at all.</p>
<p class="tiny">Another block of running text that is also set far too small for comfortable reading.</p>
<p class="tiny">And a third block of text that is set in the same tiny size as the other two blocks.</p>
<button>Save</button> <a href="#x">More</a></body></html>"""

GOOD = """<!doctype html><html><head><style>
body{margin:0;font-family:Arial;background:#faf8f6;color:#1d1a17;font-size:16px}
.hero{padding:48px;background:#9f1d20;color:#fff}.card{margin:24px;padding:24px;background:#fff;border:1px solid #e7e1db}
button,a.btn{padding:10px 18px;border-radius:8px;border:0;background:#9f1d20;color:#fff;text-decoration:none}
button:hover,a.btn:hover{background:#7c1518}button:focus-visible,a.btn:focus-visible{outline:3px solid #1d1a17}
button:disabled{opacity:.5}
</style></head><body><div class="hero"><h1>Give blood this Saturday</h1></div>
<div class="card"><p>Nine to five at the community hall, with tea afterwards.</p><button>Book a slot</button> <a class="btn" href="#x">Directions</a></div></body></html>"""


async def _audit(html: str) -> str:
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
            await page.set_content(html)
            return await audit_page(page)
        finally:
            await browser.close()


async def test_the_audit_names_the_banned_looks_and_the_missing_states() -> None:
    report = await _audit(BAD)
    assert "purple-blue" in report
    assert "empty grey box" in report
    assert "different saturated colour families" in report
    assert "No hover style" in report and "No focus style" in report
    assert "under 13px" in report


async def test_a_calm_page_with_states_passes_the_new_checks() -> None:
    report = await _audit(GOOD)
    for phrase in (
        "purple-blue",
        "grey box",
        "saturated colour families",
        "No hover",
        "No focus",
        "under 13px",
    ):
        assert phrase not in report, report


def test_source_checks_find_forms_without_error_or_sending_states_and_purple_blue_gradients(
    tmp_path: Path,
) -> None:
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "Contact.tsx").write_text(
        "export const C = () => <form onSubmit={go}><input name='e'/><button>Send</button></form>;\n",
        encoding="utf-8",
    )
    (tmp_path / "src" / "Hero.tsx").write_text(
        "export const H = () => <div className='bg-gradient-to-r from-purple-500 to-blue-500'>x</div>;\n",
        encoding="utf-8",
    )
    text = " ".join(source_taste_problems(tmp_path))
    assert "no error state" in text and "no sending state" in text and "purple-to-blue" in text
    (tmp_path / "src" / "Contact.tsx").write_text(
        "export const C = () => <form onSubmit={go}><input aria-invalid={bad}/>{bad && <p role='alert'>Enter an email</p>}"
        "<button disabled={loading}>Send</button></form>;\n",
        encoding="utf-8",
    )
    assert "form with no" not in " ".join(source_taste_problems(tmp_path))


def _fraunces_css() -> str:
    from forge.designsystem.fonts import font_css

    css, missing = font_css(["Fraunces"])
    assert not missing
    return css


SYSTEM_FONTS_PAGE = (
    "<!doctype html><html lang='en'><head><style>body{font-family:system-ui,'Segoe UI',sans-serif;margin:0;padding:24px}</style></head><body>"
    + "<h1>Wonderworks</h1>"
    + "<p>A hands-on science museum for curious families, open every day of the week with daily workshops and events for children.</p>"
    * 3
    + "</body></html>"
)


async def test_a_page_set_entirely_in_the_system_font_stack_is_reported() -> None:
    report = await _audit(SYSTEM_FONTS_PAGE)
    assert "system font stack" in report and "find_font" in report


async def test_a_page_with_a_loaded_web_font_is_not() -> None:
    html = (
        "<!doctype html><html lang='en'><head><style>"
        + _fraunces_css()
        + "body{font-family:'Fraunces',serif;margin:0;padding:24px}</style></head><body><h1>Wonderworks</h1>"
        + "<p>A hands-on science museum for curious families, open every day of the week with daily workshops and events for children.</p>"
        * 3
        + "</body></html>"
    )
    assert "system font stack" not in await _audit(html)


async def test_a_page_of_only_text_and_boxes_is_reported_as_having_no_imagery() -> None:
    cards = "".join(
        f"<div class='c'><h3>Card {n}</h3><p>Some words about this card for the page.</p></div>"
        for n in range(12)
    )
    page = f"<!doctype html><html lang='en'><head><style>body{{font-family:Georgia;margin:24px}}.c{{padding:12px;border:1px solid #ccc;margin:8px}}</style></head><body><h1>Title</h1>{cards}<p>{'Plenty of copy. ' * 60}</p></body></html>"
    assert "no imagery at all" in await _audit(page)
    with_svg = page.replace(
        "<h1>Title</h1>",
        "<h1>Title</h1><svg width='300' height='200'><circle cx='50' cy='50' r='30'/><rect x='90' y='20' width='60' height='60'/><path d='M0 150 L300 120'/><line x1='0' y1='10' x2='300' y2='10'/></svg>",
    )
    assert "no imagery at all" not in await _audit(with_svg)


def test_a_brand_guide_that_requires_system_fonts_lifts_the_typography_blocker(tmp_path: Path) -> None:
    from forge.tools.ui_audit import _system_fonts_required

    assert not _system_fonts_required(tmp_path)
    (tmp_path / "DESIGN.md").write_text(
        "## Known Gaps\nThe company standard says system fonts are required for all intranet pages.\n",
        encoding="utf-8",
    )
    assert _system_fonts_required(tmp_path)


async def test_the_system_font_finding_is_a_blocker() -> None:
    assert "BLOCKER: All the text is set in the system font stack" in await _audit(SYSTEM_FONTS_PAGE)


def _text_page(extra: str, sections: int) -> str:
    body = "".join(
        f"<section><h2>Part {n}</h2><p>{'Some honest copy about this part of the page. ' * 12}</p></section>"
        for n in range(sections)
    )
    return f"<!doctype html><html lang='en'><head><style>body{{font-family:Georgia;margin:24px}}</style></head><body><header><h1>Title</h1></header>{extra}{body}<footer>Footer</footer></body></html>"


async def test_a_marketing_page_without_imagery_is_a_blocker_and_an_app_page_is_not() -> None:
    assert "BLOCKER: The page has no imagery" in await _audit(_text_page("", 12))
    table = "<table><tr><th>A</th></tr><tr><td>1</td></tr></table>"
    report = await _audit(_text_page(table, 12))
    assert "no imagery at all" in report and "BLOCKER: The page has no imagery" not in report


def test_a_design_md_that_says_imagery_is_not_wanted_lifts_the_imagery_blocker(tmp_path: Path) -> None:
    from forge.tools.ui_audit import _imagery_not_wanted

    assert not _imagery_not_wanted(tmp_path)
    (tmp_path / "DESIGN.md").write_text(
        "## Known Gaps\nNo imagery by design: this is a text-only reading page.\n", encoding="utf-8"
    )
    assert _imagery_not_wanted(tmp_path)


async def test_a_font_that_is_named_but_not_loaded_counts_as_the_system_stack() -> None:
    page = SYSTEM_FONTS_PAGE.replace(
        "font-family:system-ui,'Segoe UI',sans-serif", "font-family:'Totally Missing Display',sans-serif"
    )
    assert "BLOCKER: All the text is set in the system font stack" in await _audit(page)


def _app_page(buttons: int, h1_size: str = "1.6rem", chart: bool = False) -> str:
    controls = "".join(f"<button class='b'>Action {n}</button>" for n in range(buttons))
    picture = (
        "<div role='img' aria-label='Chart' style='width:300px;height:120px;background:#ddd'></div>"
        if chart
        else ""
    )
    paragraphs = "".join(
        f"<div class='c'><h3>Card {n}</h3><p>Some words about this card for the page.</p></div>"
        for n in range(10)
    )
    return (
        "<!doctype html><html lang='en'><head><style>body{font-family:Georgia;margin:0;display:flex}aside{width:200px;padding:16px;border-right:1px solid #ccc}"
        f"main{{padding:24px}}h1{{font-size:{h1_size}}}.c{{padding:12px;border:1px solid #ccc;margin:8px}}.b{{padding:6px 12px;border:1px solid #888;background:#fff;margin:4px}}</style></head>"
        f"<body><aside><nav><a href='#'>Home</a></nav>{controls}</aside><main><h1>Orders</h1>{picture}{paragraphs}<p>{'Plenty of copy. ' * 60}</p></main></body></html>"
    )


async def test_an_application_screen_is_not_asked_for_pictures_or_a_landing_page_headline() -> None:
    """D-366: dashboards and tables show data; a chart counts as their picture, and an app shell with controls is not a landing page."""
    report = await _audit(_app_page(4))
    assert "no imagery at all" not in report and "h1 is only" not in report
    assert "no imagery at all" not in await _audit(_app_page(0, chart=True))
    plain = await _audit(_app_page(0, h1_size="1.4rem"))
    assert "h1 is only" in plain  # without controls it is a content page and the headline rule applies


async def test_the_audit_names_what_sticks_out_and_which_images_lack_alt_text() -> None:
    """D-369: findings that carry the patch (the outermost overflowing element with its likely cause; the image files without alt)."""
    page = (
        "<!doctype html><html lang='en'><head><style>body{margin:0;font-family:Georgia}h1{font-size:2rem}</style></head><body>"
        "<h1>Report</h1><div id='big' style='width:1900px;background:#eee'>A wide block with some words in it for the page.</div>"
        "<img src='data:image/gif;base64,R0lGODlhAQABAAAAACH5BAEKAAEALAAAAAABAAEAAAICTAEAOw==' width='40' height='40'>"
        "</body></html>"
    )
    report = await _audit(page)
    assert "Sticking out: div" in report and "a fixed width" in report
    assert "without alt text (accessibility): an inline image" in report and 'alt=""' in report
