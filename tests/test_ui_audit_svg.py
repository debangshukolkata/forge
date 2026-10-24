"""D-484: the audit finds labels crossing a box edge, labels on top of each other and drawing cut off by its <svg>."""

from __future__ import annotations

from collections.abc import Iterator
from typing import Any

import playwright.sync_api as playwright_api
import pytest

from forge.tools.ui_audit_svg import SVG_SCRIPT

CLEAN = """<svg width="600" height="300" viewBox="0 0 600 300" style="font:14px sans-serif">
<rect x="40" y="40" width="200" height="70" fill="none" stroke="#000"/><text x="60" y="80">Copy to workspace</text>
<rect x="340" y="40" width="200" height="70" fill="none" stroke="#000"/><text x="360" y="80">Run checks</text>
<line x1="240" y1="75" x2="340" y2="75" stroke="#000"/><text x="40" y="200">Legend: step</text></svg>"""

STRADDLING = CLEAN.replace(
    '<text x="360" y="80">Run checks</text>', '<text x="440" y="80">Run checks and more</text>'
)
HIDDEN = CLEAN.replace(
    "<line", '<rect x="40" y="60" width="200" height="40" fill="#eee"/><line'
)  # a filled box drawn after the first label
STACKED = CLEAN.replace('<text x="40" y="200">Legend: step</text>', '<text x="62" y="82">Legend: step</text>')
CUT_OFF = CLEAN.replace(
    '<text x="40" y="200">Legend: step</text>', '<text x="40" y="310">Legend: step</text>'
)


@pytest.fixture(scope="module")
def tab() -> Iterator[Any]:
    with playwright_api.sync_playwright() as p:
        try:
            browser = p.chromium.launch(channel="msedge", headless=True)
        except Exception as error:
            pytest.skip(f"headless Edge not available: {error}")
        yield browser.new_page(viewport={"width": 900, "height": 600})
        browser.close()


def findings_for(tab: Any, svg: str) -> list[str]:
    tab.set_content(f"<!doctype html><body style='margin:0'>{svg}</body>")
    return list(tab.evaluate(SVG_SCRIPT))


def test_a_clean_drawing_has_no_findings(tab: Any) -> None:
    assert findings_for(tab, CLEAN) == []


def test_a_label_behind_a_filled_shape_is_found(tab: Any) -> None:
    found = findings_for(tab, HIDDEN)
    assert any("hidden behind a shape" in item and "Copy to workspace" in item for item in found)


def test_a_label_that_only_straddles_a_box_edge_is_left_alone(tab: Any) -> None:
    assert findings_for(tab, STRADDLING) == []


def test_labels_on_top_of_each_other_are_found(tab: Any) -> None:
    assert any("overlap each other" in item for item in findings_for(tab, STACKED))


def test_text_outside_the_svg_is_found(tab: Any) -> None:
    assert any("outside its <svg>" in item for item in findings_for(tab, CUT_OFF))


def test_small_icons_and_pages_without_drawings_are_left_alone(tab: Any) -> None:
    assert (
        findings_for(
            tab, '<svg width="24" height="24"><text x="0" y="12">a</text><text x="0" y="12">b</text></svg>'
        )
        == []
    )
    assert findings_for(tab, "<p>no drawing here</p>") == []
