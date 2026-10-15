"""DIE6: the user's own pictures in the project's brand folder are offered before any picture from the network."""

from __future__ import annotations

from pathlib import Path

import httpx
import pytest

from forge.tools.brand_pictures import project_candidates
from forge.tools.findimage import FetchImage, FindImage
from tests.test_findimage import _context, _use

SVG = '<svg xmlns="http://www.w3.org/2000/svg" width="10" height="10"><rect width="10" height="10" fill="#c9792b"/></svg>'


def test_matching_names_come_first_and_other_files_still_follow(tmp_path: Path) -> None:
    folder = tmp_path / "brand-assets"
    folder.mkdir()
    (folder / "studio-window.jpg").write_bytes(b"x")
    (folder / "undraw_team_work.svg").write_text(SVG, encoding="utf-8")
    (folder / "notes.txt").write_text("not a picture", encoding="utf-8")
    found = project_candidates(tmp_path, "studio window light", 5)
    assert [c.id for c in found] == [
        "project:brand-assets/studio-window.jpg",
        "project:brand-assets/undraw_team_work.svg",
    ]
    assert found[1].kind == "illustration" and found[0].licence == "supplied by the user"
    assert project_candidates(tmp_path / "nowhere", "anything", 5) == []


async def test_find_image_lists_the_users_files_first_and_fetch_copies_one_with_a_notice(
    original_repo: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    def down(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("getaddrinfo failed")

    _use(monkeypatch, down)
    context = _context(original_repo, tmp_path)
    context.workspace.write_text("brand/hero-kiln.svg", SVG, "the user's picture")
    result = await FindImage().run(FindImage.Args(query="kiln hero"), context)
    assert "project:brand/hero-kiln.svg" in result.content.splitlines()[1]
    saved = await FetchImage().run(
        FetchImage.Args(id="project:brand/hero-kiln.svg", path="public/hero.svg"), context
    )
    assert saved.ok and "No credit line is required" in saved.content
    assert context.workspace.path_of("public/hero.svg").read_text(encoding="utf-8") == SVG
    notices, _ = context.workspace.read_text("NOTICES.md")
    assert "public/hero.svg" in notices and "supplied by the user" in notices


async def test_an_svg_with_a_script_in_the_brand_folder_is_not_used(
    original_repo: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _use(monkeypatch, lambda request: httpx.Response(500))
    context = _context(original_repo, tmp_path)
    context.workspace.write_text("brand/bad.svg", "<svg><script>alert(1)</script></svg>", "bad")
    await FindImage().run(FindImage.Args(query="bad"), context)
    refused = await FetchImage().run(
        FetchImage.Args(id="project:brand/bad.svg", path="public/bad.svg"), context
    )
    assert not refused.ok and "script" in refused.content


def test_the_open_doodles_are_found_by_meaning_and_recoloured() -> None:
    from forge.tools.illustration_set import FOLDER, doodle_candidates, recoloured

    found = doodle_candidates("a person reading a book in the library", 3)
    assert (
        found
        and found[0].id.startswith("doodle:")
        and found[0].licence == "CC0"
        and found[0].kind == "illustration"
    )
    assert doodle_candidates("quarterly tax ledger", 3) == []
    svg = (FOLDER / "reading.svg").read_text(encoding="utf-8")
    assert "#FF5678" in svg.upper()
    out = recoloured(svg, "#2A6FDB", "#222222")
    assert (
        "#FF5678" not in out.upper()
        and "#2A6FDB" in out
        and "#CF536D" not in out.upper()
        and "#000000" not in out
    )


async def test_fetching_a_doodle_recolours_it_and_records_cc0(
    original_repo: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _use(monkeypatch, lambda request: httpx.Response(500))
    context = _context(original_repo, tmp_path)
    await FindImage().run(FindImage.Args(query="reading book", kind="illustration"), context)
    bad = await FetchImage().run(
        FetchImage.Args(id="doodle:reading", path="public/r.svg", accent="pink"), context
    )
    assert not bad.ok
    saved = await FetchImage().run(
        FetchImage.Args(id="doodle:reading", path="public/r.png", accent="#2A6FDB"), context
    )
    assert saved.ok and "No credit line is required" in saved.content
    assert "#2A6FDB" in context.workspace.path_of("public/r.svg").read_text(encoding="utf-8")
    notices, _ = context.workspace.read_text("NOTICES.md")
    assert "CC0" in notices and "opendoodles.com" in notices
