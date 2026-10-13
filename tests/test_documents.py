"""D-342: Word documents are built from an outline, read, edited and checked (W1)."""

from __future__ import annotations

import io
import json
from pathlib import Path

import pytest

docx = pytest.importorskip("docx")
from PIL import Image  # noqa: E402

from forge.documents.build import build_document  # noqa: E402
from forge.documents.check import check_document, describe_problems  # noqa: E402
from forge.documents.edit import Operation, edit_document, replace_in_paragraph  # noqa: E402
from forge.documents.read import read_document  # noqa: E402
from forge.documents.spec import DocumentError, parse_document  # noqa: E402


def _png() -> bytes:
    out = io.BytesIO()
    Image.new("RGB", (40, 20), (200, 30, 30)).save(out, "PNG")
    return out.getvalue()


OUTLINE = {
    "title": "Quarterly report",
    "author": "Finance",
    "toc": True,
    "header": "Confidential",
    "footer": "Acme",
    "blocks": [
        {"type": "heading", "level": 1, "text": "Summary"},
        {
            "type": "paragraph",
            "runs": [
                {"text": "Sales rose "},
                {"text": "12%", "bold": True},
                {"text": ". See "},
                {"text": "the site", "link": "https://example.com"},
            ],
        },
        {"type": "bullets", "items": ["one", "two"]},
        {"type": "numbered", "items": ["first", "second"]},
        {"type": "heading", "level": 2, "text": "Detail"},
        {
            "type": "table",
            "header": ["Region", "Q1"],
            "rows": [["North", "100"], ["South", "80"]],
            "caption": "Table 1",
        },
        {"type": "image", "path": "p.png", "alt": "A red box", "caption": "Figure 1"},
        {"type": "quote", "text": "Good work."},
    ],
}


def _built(outline: dict | None = None) -> bytes:
    return build_document(parse_document(json.dumps(outline or OUTLINE)), lambda name: _png())


def test_build_has_structure_fields_links_alt_text_and_header_row() -> None:
    data = _built()
    info = read_document(data)
    assert info.title == "Quarterly report" and info.language == "en-GB"
    assert "# Quarterly report" in info.markdown and "## Detail" in info.markdown
    assert "- one" in info.markdown and "1. first" in info.markdown and "| North | 100 |" in info.markdown
    assert info.pictures == 1 and info.pictures_without_alt == 0
    assert describe_problems(check_document(data)).startswith("No structure")
    built = docx.Document(io.BytesIO(data))
    xml = built.element.xml
    assert "TOC" in xml and "w:hyperlink" in xml and "w:tblHeader" in xml
    assert "PAGE" in built.sections[0].footer._element.xml


def test_bad_links_and_outlines_are_clear_errors() -> None:
    with pytest.raises(DocumentError):
        parse_document("{no")
    bad = {
        "title": "x",
        "blocks": [{"type": "paragraph", "runs": [{"text": "a", "link": "javascript:alert(1)"}]}],
    }
    with pytest.raises(DocumentError, match="only https"):
        _built(bad)
    with pytest.raises(DocumentError):
        parse_document(
            json.dumps({"title": "x", "blocks": [{"type": "image", "path": "p.png"}]})
        )  # alt text is required


def test_check_finds_skipped_heading_levels_faked_headings_and_missing_title() -> None:
    document = docx.Document()
    document.add_heading("Top", level=1)
    document.add_heading("Deep", level=3)
    fake = document.add_paragraph()
    fake.add_run("Looks like a heading").bold = True
    out = io.BytesIO()
    document.save(out)
    text = describe_problems(check_document(out.getvalue()))
    assert "jumps from level 1 to 3" in text and "bold text" in text and "no title" in text


def test_replace_text_works_across_runs_and_keeps_the_formatting() -> None:
    document = docx.Document()
    paragraph = document.add_paragraph()
    paragraph.add_run("Hello Wo")
    paragraph.add_run("rld and Wor").bold = True
    paragraph.add_run("ld")
    assert replace_in_paragraph(paragraph, "World", "There") == 2
    assert paragraph.text == "Hello There and There"

    data = _built()
    edited, _ = edit_document(
        data,
        [
            Operation(op="replace_text", find="Sales rose", replace="Revenue grew"),
            Operation(op="append_paragraph", text="Appendix note"),
            Operation(op="delete_paragraph", index=3),
        ],
    )
    markdown = read_document(edited).markdown
    assert (
        "Revenue grew" in markdown
        and "Appendix note" in markdown
        and "- one" not in markdown.split("\n")[2:3]
    )
    with pytest.raises(DocumentError, match="not in the document"):
        edit_document(data, [Operation(op="replace_text", find="zzzzqq", replace="x")])
    with pytest.raises(DocumentError, match="index must be"):
        edit_document(data, [Operation(op="delete_paragraph", index=999)])


def test_a_template_keeps_its_header_and_drops_its_sample_text() -> None:
    base = docx.Document()
    base.add_paragraph("SAMPLE TEXT FROM THE TEMPLATE")
    base.sections[0].header.paragraphs[0].text = "Company header"
    out = io.BytesIO()
    base.save(out)
    data = build_document(
        parse_document(json.dumps(OUTLINE | {"header": ""})), lambda n: _png(), out.getvalue()
    )
    built = docx.Document(io.BytesIO(data))
    assert "SAMPLE TEXT" not in read_document(data).markdown
    assert built.sections[0].header.paragraphs[0].text == "Company header"


async def test_the_tools(original_repo: Path, tmp_path: Path) -> None:
    from forge.toolkit.base import ToolContext
    from forge.tools.document import BuildDocument, CheckDocument, EditDocument, ReadDocument
    from forge.workspace.create import create_workspace

    workspace = create_workspace(original_repo, tmp_path / "ws", "backend")
    workspace.write_text("docs/outline.json", json.dumps(OUTLINE), "x")
    workspace.write_bytes("p.png", _png(), "x")
    context = ToolContext(workspace=workspace)
    built = await BuildDocument().run(
        BuildDocument.Args(outline="docs/outline.json", output="docs/r.docx"), context
    )
    assert built.ok and "Wrote docs/r.docx" in built.content
    read = await ReadDocument().run(ReadDocument.Args(path="docs/r.docx"), context)
    assert read.ok and "Summary" in read.content
    edited = await EditDocument().run(
        EditDocument.Args(
            path="docs/r.docx", operations=[Operation(op="replace_text", find="Detail", replace="Details")]
        ),
        context,
    )
    assert edited.ok
    assert (await CheckDocument().run(CheckDocument.Args(path="docs/r.docx"), context)).ok
    assert not (await ReadDocument().run(ReadDocument.Args(path="docs/none.docx"), context)).ok
