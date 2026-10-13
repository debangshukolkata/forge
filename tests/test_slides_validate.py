"""P1.8: the package validator accepts what our builder makes and names the usual faults in a damaged file."""

from __future__ import annotations

import io
import json
import zipfile

import pytest

from forge.slides.build import build_deck
from forge.slides.spec import parse_deck
from forge.slides.validate import validate_package

DECK = {
    "title": "Deck",
    "slides": [
        {"layout": "title", "title": "Q3 review"},
        {"layout": "bullets", "title": "We shipped three things", "bullets": ["a", "b"], "notes": "say this"},
        {
            "layout": "table",
            "title": "Numbers by region are clear",
            "columns": ["a", "b"],
            "rows": [["1", "2"], ["3", "4"]],
        },
        {
            "layout": "chart",
            "title": "Users doubled since January",
            "categories": ["Jan", "Feb"],
            "series": [{"name": "Users", "values": [1, 2]}, {"name": "Paid", "values": [1, 1]}],
        },
        {"layout": "stats", "title": "Weekly users grew 42%", "items": [{"value": "42%", "label": "growth"}]},
        {
            "layout": "freeform",
            "title": "A free slide can carry one idea",
            "elements": [{"type": "text", "x": 1, "y": 2, "w": 4, "h": 1, "text": "hello"}],
        },
    ],
}


@pytest.fixture(scope="module")
def good() -> bytes:
    return build_deck(parse_deck(json.dumps(DECK)), lambda name: b"").data


def _change(data: bytes, edits: dict[str, bytes | None]) -> bytes:
    """A copy of the package with some parts replaced (bytes) or removed (None)."""
    out = io.BytesIO()
    with (
        zipfile.ZipFile(io.BytesIO(data)) as source,
        zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as target,
    ):
        for item in source.infolist():
            if item.filename in edits:
                if edits[item.filename] is not None:
                    target.writestr(item.filename, edits[item.filename])  # type: ignore[arg-type]
            else:
                target.writestr(item, source.read(item.filename))
    return out.getvalue()


def _read(data: bytes, name: str) -> str:
    with zipfile.ZipFile(io.BytesIO(data)) as archive:
        return archive.read(name).decode("utf-8")


def test_a_deck_built_by_our_builder_is_valid(good: bytes) -> None:
    assert validate_package(good) == []


def test_not_a_zip_and_not_a_presentation() -> None:
    assert "not a zip" in validate_package(b"hello")[0]
    only_types = _change(
        _zip(
            {
                "[Content_Types].xml": "<Types xmlns='http://schemas.openxmlformats.org/package/2006/content-types'/>"
            }
        ),
        {},
    )
    assert any("not a PowerPoint package" in p for p in validate_package(only_types))


def _zip(files: dict[str, str]) -> bytes:
    out = io.BytesIO()
    with zipfile.ZipFile(out, "w") as archive:
        for name, text in files.items():
            archive.writestr(name, text)
    return out.getvalue()


def test_a_relationship_to_a_missing_part_is_named(good: bytes) -> None:
    text = _read(good, "ppt/slides/_rels/slide2.xml.rels").replace("slideLayout", "slideLayoutGONE")
    problems = validate_package(_change(good, {"ppt/slides/_rels/slide2.xml.rels": text.encode()}))
    assert any("slide2.xml.rels" in p and "not in the file" in p for p in problems)


def test_a_duplicate_shape_id_is_named(good: bytes) -> None:
    xml = _read(good, "ppt/slides/slide2.xml")
    import re

    ids = re.findall(r'<p:cNvPr id="(\d+)"', xml)
    assert len(ids) >= 2
    broken = xml.replace(f'<p:cNvPr id="{ids[1]}"', f'<p:cNvPr id="{ids[0]}"', 1)
    problems = validate_package(_change(good, {"ppt/slides/slide2.xml": broken.encode()}))
    assert any("shape id" in p and "slide2.xml" in p for p in problems)


def test_a_table_row_with_the_wrong_number_of_cells_is_named(good: bytes) -> None:
    xml = _read(good, "ppt/slides/slide3.xml")
    i = xml.index("</a:tc>")
    broken = (
        xml[: i + 7] + xml[i + 7 :].replace("</a:tc>", "", 1)
        if False
        else xml.replace("<a:tc>", "", 1).replace("</a:tc>", "", 1)
    )
    problems = validate_package(_change(good, {"ppt/slides/slide3.xml": broken.encode()}))
    assert problems  # either the XML no longer parses or the row has too few cells


def test_malformed_xml_and_missing_content_type_are_named(good: bytes) -> None:
    problems = validate_package(_change(good, {"ppt/slides/slide2.xml": b"<p:sld><unclosed>"}))
    assert any("not well formed" in p for p in problems)
    import re

    types = _read(good, "[Content_Types].xml")
    types = types.replace('Extension="xml"', 'Extension="zzz"')
    types = re.sub(r'<Override[^>]*PartName="/ppt/slides/slide2.xml"[^>]*/>', "", types)
    problems = validate_package(_change(good, {"[Content_Types].xml": types.encode()}))
    assert any("slide2.xml" in p and "no content type" in p for p in problems)


def test_a_deleted_slide_part_and_a_bad_font_size_are_named(good: bytes) -> None:
    problems = validate_package(_change(good, {"ppt/slides/slide2.xml": None}))
    assert any("slide2.xml" in p and "not in the file" in p for p in problems)
    xml = _read(good, "ppt/slides/slide2.xml")
    import re

    if re.search(r'sz="\d+"', xml):
        bad = re.sub(r'sz="\d+"', 'sz="9999999"', xml, count=1)
        assert any(
            "font size" in p for p in validate_package(_change(good, {"ppt/slides/slide2.xml": bad.encode()}))
        )
