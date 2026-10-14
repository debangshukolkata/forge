"""D-343: PDF files are read, edited and created (W3)."""

from __future__ import annotations

import io
import json
from pathlib import Path

import pytest

pytest.importorskip("pypdf")
pytest.importorskip("reportlab")
from PIL import Image

from forge.pdfs.build import build_pdf, parse_pdf_spec
from forge.pdfs.edit import Operation, apply, extract_images, parse_pages, split_pdf
from forge.pdfs.read import PdfError, describe_pdf, open_pdf, read_pdf


def _png() -> bytes:
    out = io.BytesIO()
    Image.new("RGB", (60, 30), (30, 90, 200)).save(out, "PNG")
    return out.getvalue()


def _built(pages: int = 3) -> bytes:
    blocks: list[dict] = []
    for number in range(1, pages + 1):
        blocks += [
            {"type": "heading", "text": f"Section {number}"},
            {"type": "paragraph", "text": f"Body of page {number}.", "link": "https://example.com"},
            {"type": "table", "header": ["A", "B"], "rows": [["1", "2"]]},
            {"type": "page_break"},
        ]
    blocks.insert(2, {"type": "image", "path": "p.png", "caption": "Figure"})
    spec = parse_pdf_spec(json.dumps({"title": "Report", "author": "Me", "footer": "Acme", "blocks": blocks}))
    return build_pdf(spec, lambda name: _png())


def test_build_and_read_give_text_title_pictures_and_layout() -> None:
    data = _built()
    info = read_pdf(data)
    assert info.pages >= 3 and info.title == "Report" and info.author == "Me" and not info.scanned
    assert "Section 2" in "\n".join(info.texts) and "Acme" in info.texts[0] and info.pictures >= 1
    assert "[page 1]" in describe_pdf(info, "r.pdf")


def test_bad_link_outline_and_pages_are_clear_errors() -> None:
    with pytest.raises(PdfError):
        parse_pdf_spec("{no")
    bad = parse_pdf_spec(
        json.dumps({"title": "x", "blocks": [{"type": "paragraph", "text": "a", "link": "javascript:1"}]})
    )
    with pytest.raises(PdfError, match="only https"):
        build_pdf(bad, lambda n: b"")
    assert parse_pages("1-2,4", 5) == [0, 1, 3] and parse_pages("", 2) == [0, 1]
    with pytest.raises(PdfError, match="outside"):
        parse_pages("9", 3)
    with pytest.raises(PdfError, match="like 1-3,5"):
        parse_pages("a", 3)


def test_page_operations_merge_delete_extract_rotate_crop_and_split() -> None:
    data = _built()
    total = read_pdf(data).pages
    load = lambda name: data  # noqa: E731
    merged = apply(data, Operation(op="merge", paths=["x.pdf"]), load)
    assert read_pdf(merged).pages == total * 2
    assert read_pdf(apply(data, Operation(op="delete_pages", pages="1"), load)).pages == total - 1
    assert read_pdf(apply(data, Operation(op="extract_pages", pages="2-3"), load)).pages == 2
    rotated = open_pdf(apply(data, Operation(op="rotate", pages="1", degrees=90), load))
    assert rotated.pages[0].get("/Rotate") == 90 and not rotated.pages[1].get("/Rotate")
    cropped = open_pdf(apply(data, Operation(op="crop", pages="1", margins_in=(1, 1, 1, 1)), load))
    assert float(cropped.pages[0].mediabox.width) < float(cropped.pages[1].mediabox.width)
    with pytest.raises(PdfError, match="no pages"):
        apply(data, Operation(op="delete_pages"), load)
    parts = split_pdf(data, ["1-2", "3"])
    assert [read_pdf(p).pages for p in parts] == [2, 1]


def test_watermark_and_page_numbers_are_stamped_and_text_stays_readable() -> None:
    data = _built(2)
    load = lambda name: data  # noqa: E731
    stamped = apply(
        apply(data, Operation(op="watermark", text="DRAFT"), load),
        Operation(op="page_numbers", text="Page {n} of {total}"),
        load,
    )
    text = "\n".join(read_pdf(stamped).texts)
    assert "DRAFT" in text and "Page 1 of" in text and "Section 1" in text


def test_encrypt_decrypt_and_the_password_rules() -> None:
    data = _built(1)
    load = lambda name: data  # noqa: E731
    locked = apply(data, Operation(op="encrypt", password="pw"), load)
    with pytest.raises(PdfError, match="password-protected"):
        read_pdf(locked)
    with pytest.raises(PdfError, match="does not open"):
        read_pdf(locked, "wrong")
    assert read_pdf(locked, "pw").pages == read_pdf(data).pages
    plain = apply(locked, Operation(op="decrypt", password="pw"), load)
    assert not read_pdf(plain).encrypted


def test_metadata_and_images() -> None:
    data = _built(1)
    load = lambda name: data  # noqa: E731
    changed = apply(data, Operation(op="set_metadata", title="New", author="You"), load)
    assert read_pdf(changed).title == "New"
    assert extract_images(data)


def test_a_form_can_be_filled_and_unknown_fields_are_named() -> None:
    from reportlab.pdfgen import canvas

    buffer = io.BytesIO()
    sheet = canvas.Canvas(buffer)
    sheet.acroForm.textfield(name="full_name", x=50, y=700, width=200, height=20)
    sheet.showPage()
    sheet.save()
    data = buffer.getvalue()
    load = lambda name: data  # noqa: E731
    assert "full_name" in read_pdf(data).form_fields
    filled = apply(data, Operation(op="fill_form", fields={"full_name": "Asha"}), load)
    assert read_pdf(filled).form_fields["full_name"] == "Asha"
    with pytest.raises(PdfError, match="No such form field: nope"):
        apply(data, Operation(op="fill_form", fields={"nope": "x"}), load)


async def test_the_tools(original_repo: Path, tmp_path: Path) -> None:
    from forge.toolkit.base import ToolContext
    from forge.tools.pdf_toolkit import BuildPdf, EditPdf, ExtractPdfImages, ReadPdf, SplitPdf
    from forge.workspace.create import create_workspace

    workspace = create_workspace(original_repo, tmp_path / "ws", "backend")
    outline = {
        "title": "T",
        "blocks": [
            {"type": "heading", "text": "H"},
            {"type": "paragraph", "text": "hello world"},
            {"type": "page_break"},
            {"type": "paragraph", "text": "two"},
        ],
    }
    workspace.write_text("docs/o.json", json.dumps(outline), "x")
    context = ToolContext(workspace=workspace)
    built = await BuildPdf().run(BuildPdf.Args(outline="docs/o.json", output="docs/a.pdf"), context)
    assert built.ok
    read = await ReadPdf().run(ReadPdf.Args(path="docs/a.pdf"), context)
    assert read.ok and "hello world" in read.content
    edited = await EditPdf().run(
        EditPdf.Args(
            path="docs/a.pdf", output="docs/b.pdf", operations=[Operation(op="watermark", text="COPY")]
        ),
        context,
    )
    assert edited.ok
    split = await SplitPdf().run(
        SplitPdf.Args(path="docs/a.pdf", ranges=["1", "2"], output_prefix="docs/part"), context
    )
    assert split.ok and "docs/part-2.pdf" in split.content
    assert (
        await ExtractPdfImages().run(ExtractPdfImages.Args(path="docs/a.pdf", folder="docs/img"), context)
    ).ok
    assert not (await ReadPdf().run(ReadPdf.Args(path="docs/none.pdf"), context)).ok
