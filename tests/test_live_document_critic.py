"""Live (real Azure model): the document critic scores a tidy report higher than a crowded, inconsistent one (D-347)."""

from __future__ import annotations

import io
import json
from pathlib import Path

import pytest

from forge.config import ForgeConfig, Secrets
from forge.toolkit.base import ToolContext
from forge.tools.document_preview import CritiqueDocument
from forge.workspace.create import create_workspace
from tests.test_live_llm import live, router_for  # noqa: F401  (the fixture and the router builder)

pytestmark = pytest.mark.live

docx = pytest.importorskip("docx")


def _good() -> bytes:
    from forge.documents.build import build_document
    from forge.documents.spec import parse_document

    outline = {
        "title": "Quarterly sales report",
        "author": "Finance",
        "blocks": [
            {"type": "heading", "level": 1, "text": "Summary"},
            {"type": "paragraph", "text": "Sales rose 12% to 4.2 million, led by the North region."},
            {"type": "heading", "level": 1, "text": "Results by region"},
            {
                "type": "table",
                "header": ["Region", "Q1", "Q2"],
                "rows": [["North", "100", "120"], ["South", "80", "90"]],
            },
            {"type": "heading", "level": 1, "text": "Next steps"},
            {"type": "bullets", "items": ["Open a second warehouse", "Hire two sales leads"]},
        ],
    }
    return build_document(parse_document(json.dumps(outline)), lambda name: b"")


def _bad() -> bytes:
    from docx.shared import Pt, RGBColor

    document = docx.Document()
    sizes = [7, 22, 9, 30, 8]
    colours = [
        RGBColor(0xFF, 0xFF, 0x99),
        RGBColor(0x00, 0x00, 0x00),
        RGBColor(0xCC, 0xCC, 0xCC),
        RGBColor(0xFF, 0x00, 0x00),
        RGBColor(0x88, 0x88, 0xFF),
    ]
    fonts = ["Comic Sans MS", "Times New Roman", "Impact", "Courier New", "Arial"]
    for number in range(40):
        paragraph = document.add_paragraph()
        run = paragraph.add_run(
            "Sales went up and down in the regions and we think that maybe it was because of many reasons that are hard to say. "
            * 2
        )
        run.font.size = Pt(sizes[number % 5])
        run.font.color.rgb = colours[number % 5]
        run.font.name = fonts[number % 5]
    out = io.BytesIO()
    document.save(out)
    return out.getvalue()


def _scores(content: str) -> dict[str, float]:
    return json.loads(content)["scores"]


async def test_a_tidy_report_beats_a_crowded_inconsistent_one(
    live: tuple[ForgeConfig, Secrets],  # noqa: F811
    tmp_path: Path,
    original_repo: Path,
) -> None:
    from forge.documents.preview import libreoffice, word_available

    if not (word_available() or libreoffice()):
        pytest.skip("no Word or LibreOffice to print the pages")
    config, secrets = live
    context = ToolContext(
        workspace=create_workspace(original_repo, tmp_path / "ws", "backend"),
        router=router_for(config, secrets),
    )
    context.workspace.write_bytes("docs/good.docx", _good(), "x")
    context.workspace.write_bytes("docs/bad.docx", _bad(), "x")
    good = await CritiqueDocument().run(
        CritiqueDocument.Args(path="docs/good.docx", purpose="a short sales report for managers"), context
    )
    bad = await CritiqueDocument().run(
        CritiqueDocument.Args(path="docs/bad.docx", purpose="a short sales report for managers"), context
    )
    assert good.ok and bad.ok, (good.content, bad.content)
    good_scores, bad_scores = _scores(good.content), _scores(bad.content)
    assert sum(good_scores.values()) > sum(bad_scores.values()), (good.content, bad.content)
    assert json.loads(bad.content)["verdict"] == "fix_first", bad.content
    assert json.loads(bad.content)["issues"], bad.content
