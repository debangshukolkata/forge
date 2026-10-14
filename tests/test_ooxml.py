"""D-345: the shared package check and validator for Word, Excel and PowerPoint files (W4)."""

from __future__ import annotations

import io
import json
import zipfile
from pathlib import Path

import pytest

from forge.ooxml.check import PackageError, check_package
from forge.ooxml.validate import validate_package

docx = pytest.importorskip("docx")
openpyxl = pytest.importorskip("openpyxl")


def _docx() -> bytes:
    document = docx.Document()
    document.add_paragraph("hello")
    out = io.BytesIO()
    document.save(out)
    return out.getvalue()


def _xlsx() -> bytes:
    book = openpyxl.Workbook()
    book.active["A1"] = 1
    out = io.BytesIO()
    book.save(out)
    return out.getvalue()


def _rewrite(data: bytes, change: dict[str, bytes | None]) -> bytes:
    out = io.BytesIO()
    with (
        zipfile.ZipFile(io.BytesIO(data)) as source,
        zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as target,
    ):
        for info in source.infolist():
            if info.filename in change:
                if change[info.filename] is not None:
                    target.writestr(info.filename, change[info.filename])  # type: ignore[arg-type]
            else:
                target.writestr(info.filename, source.read(info.filename))
        for name, content in change.items():
            if content is not None and name not in source.namelist():
                target.writestr(name, content)
    return out.getvalue()


def test_good_files_pass_and_say_what_kind_they_are() -> None:
    assert check_package(_docx()).kind == "docx" and check_package(_xlsx()).kind == "xlsx"
    assert validate_package(_docx()) == [] and validate_package(_xlsx()) == []


def test_hostile_packages_are_refused() -> None:
    with pytest.raises(PackageError, match="not a valid Office package"):
        check_package(b"not a zip")
    evil_name = _rewrite(_docx(), {"../evil.xml": b"<a/>"})
    with pytest.raises(PackageError, match="unsafe entry name"):
        check_package(evil_name)
    doctype = _rewrite(
        _docx(), {"word/document.xml": b'<?xml version="1.0"?><!DOCTYPE x [<!ENTITY a "b">]><x/>'}
    )
    with pytest.raises(PackageError, match="DOCTYPE"):
        check_package(doctype)
    bomb = io.BytesIO()
    with zipfile.ZipFile(bomb, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("word/document.xml", b"0" * (300 * 1024 * 1024))
    with pytest.raises(PackageError, match=r"zip bomb|expands"):
        check_package(bomb.getvalue())


def test_macros_links_and_embedded_objects_are_reported_not_run() -> None:
    rels = (
        b'<?xml version="1.0"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
        b'<Relationship Id="rId9" Type="x" Target="https://example.com/a" TargetMode="External"/></Relationships>'
    )
    data = _rewrite(
        _docx(),
        {"word/vbaProject.bin": b"x", "word/embeddings/o.bin": b"x", "word/_rels/footer1.xml.rels": rels},
    )
    report = check_package(data)
    notes = " ".join(report.notes())
    assert report.macros and "macro project" in notes and "example.com" in notes and "embeds 1" in notes


def test_the_validator_names_structural_faults() -> None:
    no_types = _rewrite(_docx(), {"[Content_Types].xml": None})
    assert any("[Content_Types].xml is missing" in p for p in validate_package(no_types))
    broken = _rewrite(_docx(), {"word/document.xml": b"<w:document"})
    assert any("not well formed" in p for p in validate_package(broken))
    dangling = _rewrite(
        _docx(),
        {
            "word/_rels/document.xml.rels": b'<?xml version="1.0"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
            b'<Relationship Id="rId1" Type="x" Target="media/missing.png"/></Relationships>'
        },
    )
    assert any("media/missing.png" in p for p in validate_package(dangling))
    assert any("not a valid Office package" in p for p in validate_package(b"zzz"))


def test_tools_refuse_hostile_files_and_report_notes(original_repo: Path, tmp_path: Path) -> None:
    import asyncio

    from forge.toolkit.base import ToolContext
    from forge.tools.document import ReadDocument
    from forge.tools.workbook import ReadWorkbook
    from forge.workspace.create import create_workspace

    workspace = create_workspace(original_repo, tmp_path / "ws", "backend")
    workspace.write_bytes(
        "docs/evil.docx", _rewrite(_docx(), {"word/document.xml": b"<!DOCTYPE x><x/>"}), "x"
    )
    workspace.write_bytes("docs/macro.docx", _rewrite(_docx(), {"word/vbaProject.bin": b"x"}), "x")
    workspace.write_bytes("docs/book.xlsx", _xlsx(), "x")
    context = ToolContext(workspace=workspace)

    async def run() -> None:
        refused = await ReadDocument().run(ReadDocument.Args(path="docs/evil.docx"), context)
        assert not refused.ok and "DOCTYPE" in refused.content
        noted = await ReadDocument().run(ReadDocument.Args(path="docs/macro.docx"), context)
        assert noted.ok and "macro project" in noted.content
        assert (await ReadWorkbook().run(ReadWorkbook.Args(path="docs/book.xlsx"), context)).ok

    asyncio.run(run())


async def test_preview_file_makes_pictures_and_a_contact_sheet_for_pdf_and_excel(
    original_repo: Path, tmp_path: Path
) -> None:
    from forge.sheets import excel
    from forge.toolkit.base import ToolContext
    from forge.tools.document_preview import PreviewFile
    from forge.workspace.create import create_workspace

    pytest.importorskip("pypdf")
    pytest.importorskip("pypdfium2")
    from forge.pdfs.build import build_pdf, parse_pdf_spec

    workspace = create_workspace(original_repo, tmp_path / "ws", "backend")
    blocks = [{"type": "paragraph", "text": f"page {n}"} for n in range(1, 4)]
    pages = [b for block in blocks for b in (block, {"type": "page_break"})]
    workspace.write_bytes(
        "docs/a.pdf",
        build_pdf(parse_pdf_spec(json.dumps({"title": "T", "blocks": pages})), lambda n: b""),
        "x",
    )
    context = ToolContext(workspace=workspace)
    shown = await PreviewFile().run(PreviewFile.Args(path="docs/a.pdf"), context)
    assert shown.ok and "Contact sheet" in shown.content and "rendered" in shown.content
    assert not (await PreviewFile().run(PreviewFile.Args(path="docs/a.txt"), context)).ok
    if excel.available():
        workspace.write_bytes("docs/b.xlsx", _xlsx(), "x")
        sheet = await PreviewFile().run(PreviewFile.Args(path="docs/b.xlsx"), context)
        assert sheet.ok and "page(s)" in sheet.content
