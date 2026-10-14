"""D3 and D6 (D-312): variants that must differ, and screens that must not change by accident."""

from __future__ import annotations

from pathlib import Path

import pytest

pytest.importorskip("PIL")
from PIL import Image, ImageDraw

from forge.toolkit.base import ToolContext
from forge.tools.visual_diff import (
    CompareDesigns,
    VisualBaseline,
    VisualCheck,
    design_tokens,
    diff_pictures,
    layout_similarity,
    palette,
    palette_overlap,
)
from forge.workspace.create import create_workspace

W, H = 640, 800


def page(kind: str, background: str = "#ffffff", accent: str = "#1f5fbf") -> Image.Image:
    image = Image.new("RGB", (W, H), background)
    draw = ImageDraw.Draw(image)
    if kind == "hero-then-cards":
        draw.rectangle((0, 0, W, 300), fill=accent)  # a tall hero
        for i in range(3):
            draw.rectangle((30 + i * 205, 340, 215 + i * 205, 560), fill="#dddddd")
    elif kind == "sidebar":
        draw.rectangle((0, 0, 200, H), fill=accent)  # a sidebar layout
        for i in range(5):
            draw.rectangle((230, 40 + i * 140, W - 30, 140 + i * 140), fill="#dddddd")
    elif kind == "split":
        draw.rectangle((0, 0, W // 2, H), fill=accent)
        draw.rectangle((W // 2 + 30, 200, W - 30, 260), fill="#999999")
    return image


def save(tmp: Path, name: str, image: Image.Image) -> Path:
    path = tmp / name
    image.save(path)
    return path


def test_the_same_layout_in_other_colours_is_still_the_same_design(tmp_path: Path) -> None:
    blue = page("hero-then-cards")
    red = page("hero-then-cards", background="#fff5f0", accent="#c0392b")
    assert layout_similarity(blue, red) > 0.75
    assert layout_similarity(blue, page("sidebar")) < 0.75
    assert layout_similarity(page("sidebar"), page("split")) < 0.75


def test_palettes_and_their_overlap() -> None:
    blue, red = palette(page("hero-then-cards")), palette(page("hero-then-cards", accent="#c0392b"))
    assert "#ffffff" in blue[0:2] or len(blue) >= 2
    assert palette_overlap(blue, blue) == 1.0
    assert palette_overlap(blue, red) < 1.0


def test_design_tokens_are_read_from_design_md(tmp_path: Path) -> None:
    (tmp_path / "DESIGN.md").write_text(
        "# Design\nAccent: #1F5FBF and #222222\nHeading font: Fraunces\nfont-family: Inter\n",
        encoding="utf-8",
    )
    colours, fonts = design_tokens(tmp_path)
    assert colours[0] == "#1f5fbf" and "fraunces" in fonts
    assert design_tokens(tmp_path / "missing") == ([], [])


async def test_compare_designs_flags_variants_that_are_one_design(
    original_repo: Path, tmp_path: Path
) -> None:
    workspace = create_workspace(original_repo, tmp_path / "ws", "backend")
    context = ToolContext(workspace=workspace)
    shots = workspace.forge_dir / "screenshots"
    shots.mkdir(parents=True, exist_ok=True)
    save(shots, "a.png", page("hero-then-cards"))
    save(shots, "b.png", page("hero-then-cards", background="#fff5f0", accent="#c0392b"))
    save(shots, "c.png", page("sidebar"))
    tool = CompareDesigns()

    alike = await tool.run(
        tool.Args(
            screenshots={
                "a": ".forge/screenshots/a.png",
                "b": ".forge/screenshots/b.png",
                "c": ".forge/screenshots/c.png",
            }
        ),
        context,
    )
    assert (
        alike.ok
        and "a vs b" in alike.content
        and "TOO SIMILAR" in alike.content
        and "BLOCKER" in alike.content
    )
    assert ("a vs c" in alike.content and "c vs b" not in alike.content) or "different" in alike.content

    different = await tool.run(
        tool.Args(screenshots={"a": ".forge/screenshots/a.png", "c": ".forge/screenshots/c.png"}), context
    )
    assert "The variants differ." in different.content
    few = await tool.run(tool.Args(screenshots={"a": ".forge/screenshots/a.png"}), context)
    assert not few.ok


async def test_compare_designs_also_reads_the_design_md_of_each_folder(
    original_repo: Path, tmp_path: Path
) -> None:
    workspace = create_workspace(original_repo, tmp_path / "ws", "backend")
    context = ToolContext(workspace=workspace)
    shots = workspace.forge_dir / "screenshots"
    shots.mkdir(parents=True, exist_ok=True)
    save(shots, "a.png", page("sidebar"))
    save(shots, "b.png", page("split"))
    for name in ("a", "b"):
        folder = workspace.repo_dir / "designs" / name
        folder.mkdir(parents=True)
        (folder / "DESIGN.md").write_text("Accent: #1f5fbf\nHeading font: Inter\n", encoding="utf-8")
    tool = CompareDesigns()
    result = await tool.run(
        tool.Args(
            screenshots={"a": ".forge/screenshots/a.png", "b": ".forge/screenshots/b.png"},
            folders={"a": "designs/a", "b": "designs/b"},
        ),
        context,
    )
    assert (
        "DESIGN.md names the same first colour and first font" in result.content
        and "BLOCKER" in result.content
    )


def test_a_diff_reports_where_the_page_changed_and_ignores_noise(tmp_path: Path) -> None:
    base = page("hero-then-cards")
    save(tmp_path, "base.png", base)
    same = save(tmp_path, "same.png", base.copy())
    noisy = base.copy()
    ImageDraw.Draw(noisy).point((10, 10), fill="#fefefe")
    save(tmp_path, "noisy.png", noisy)
    changed = base.copy()
    ImageDraw.Draw(changed).rectangle((30, 600, 600, 700), fill="#00aa00")  # a new block low on the page
    save(tmp_path, "changed.png", changed)

    assert diff_pictures(tmp_path / "base.png", same)[0] == 0
    assert diff_pictures(tmp_path / "base.png", tmp_path / "noisy.png")[0] < 0.002
    share, rows = diff_pictures(tmp_path / "base.png", tmp_path / "changed.png", tmp_path / "diff.png")
    assert 0.05 < share < 0.15 and rows and all(top >= 400 for top, _ in rows)
    assert (tmp_path / "diff.png").is_file()


async def test_baseline_then_check_catches_an_unplanned_change(original_repo: Path, tmp_path: Path) -> None:
    workspace = create_workspace(original_repo, tmp_path / "ws", "backend")
    context = ToolContext(workspace=workspace)
    shots = workspace.forge_dir / "screenshots"
    shots.mkdir(parents=True, exist_ok=True)
    save(shots, "shot-1.png", page("hero-then-cards"))

    approve, check = VisualBaseline(), VisualCheck()
    nothing = await check.run(check.Args(name="home"), context)
    assert not nothing.ok and "No baseline for 'home'" in nothing.content
    approved = await approve.run(
        approve.Args(name="Home Page"), context
    )  # the latest screenshot, a safe name
    assert approved.ok and "'home-page'" in approved.content

    unchanged = await check.run(check.Args(name="home-page"), context)
    assert unchanged.ok and "is unchanged" in unchanged.content

    broken = page("hero-then-cards")
    ImageDraw.Draw(broken).rectangle((0, 0, W, 300), fill="#000000")  # the hero went black
    save(shots, "shot-2.png", broken)
    regression = await check.run(check.Args(name="home-page"), context)
    assert regression.ok and "changed:" in regression.content and "regression" in regression.content
    assert (workspace.root / ".forge" / "visual" / "home-page-diff.png").is_file()

    await approve.run(approve.Args(name="home-page"), context)  # the change was meant: approve the new look
    assert "is unchanged" in (await check.run(check.Args(name="home-page"), context)).content


# --- D4: the first page or style file waits for a DESIGN.md ---


async def test_the_first_ui_file_without_a_design_md_is_refused_four_times_then_allowed(
    original_repo: Path, tmp_path: Path
) -> None:
    from forge.tools.files import WriteFile

    workspace = create_workspace(original_repo, tmp_path / "ws", "backend")
    context = ToolContext(workspace=workspace)
    tool = WriteFile()

    async def write(path: str, text: str = "x") -> object:
        return await tool.run(tool.Args(path=path, content=text), context)

    first = await write("site/index.html", "<h1>x</h1>")
    assert not first.ok and "DESIGN.md" in first.content and "ASCII wireframe" in first.content  # type: ignore[attr-defined]
    assert (await write("site/app.py", "x = 1\n")).ok  # not a UI file
    for _ in range(3):  # four refusals in all (no DESIGN.md yet)
        assert not (await write("site/style.css", "a{}")).ok
    assert (await write("site/style.css", "a{}")).ok  # never a trap: the fifth write goes through


async def test_a_design_md_in_the_folder_or_above_opens_the_gate(original_repo: Path, tmp_path: Path) -> None:
    from forge.tools.files import WriteFile

    workspace = create_workspace(original_repo, tmp_path / "ws", "backend")
    context = ToolContext(workspace=workspace)
    tool = WriteFile()
    workspace.write_text(
        "site/DESIGN.md", "# Design", "the user's own file"
    )  # a file the user supplied is never questioned
    assert (await tool.run(tool.Args(path="site/index.html", content="<h1>x</h1>"), context)).ok
    assert (
        await tool.run(tool.Args(path="site/pages/about/index.html", content="<h1>y</h1>"), context)
    ).ok  # found in a parent folder
    assert context.design_gate_rounds == 0


async def test_builders_and_the_switch_are_not_gated(original_repo: Path, tmp_path: Path) -> None:
    from forge.tools.files import WriteFile

    workspace = create_workspace(original_repo, tmp_path / "ws", "backend")
    tool = WriteFile()
    builder = ToolContext(workspace=workspace, write_only_under="designs/a/")
    assert (await tool.run(tool.Args(path="designs/a/index.html", content="<h1>x</h1>"), builder)).ok
    off = ToolContext(workspace=workspace, design_first=False)
    assert (await tool.run(tool.Args(path="other/index.html", content="<h1>x</h1>"), off)).ok
