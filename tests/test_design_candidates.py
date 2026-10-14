"""D-350: how different two designs are, the specimen page, and choosing the best of three."""

from __future__ import annotations

from pathlib import Path

import pytest

from forge.designsystem.lint import lint_text
from forge.designsystem.novelty import differences, fingerprint, is_different_enough
from forge.designsystem.spec import parse_design_md
from forge.designsystem.specimen import specimen_html
from forge.toolkit.base import ToolContext
from forge.tools.design_candidates import DesignCandidates, DesignSpecimen
from forge.workspace.create import create_workspace


def system_text(
    name: str,
    neutral: str,
    ink: str,
    primary: str,
    font: str,
    radius: int,
    density: int,
    variance: int,
    pill: bool = False,
    on_primary: str = "#FFFFFF",
) -> str:
    rounded = f"  sm: {max(radius // 2, 2)}px\n  md: {radius}px\n" + ("  pill: 9999px\n" if pill else "")
    return f"""---
version: alpha
name: {name}
dials:
  density: {density}
  variance: {variance}
colors:
  primary: "{primary}"
  neutral: "{neutral}"
  ink: "{ink}"
  muted: "{ink}"
  surface: "{neutral}"
  border: "#888888"
typography:
  display:
    fontFamily: {font}
    fontSize: 56px
    fontWeight: 700
    lineHeight: 1.1
  body-md:
    fontFamily: Inter
    fontSize: 16px
    fontWeight: 400
    lineHeight: 1.6
rounded:
{rounded}spacing:
  sm: 8px
  md: 16px
components:
  button-primary:
    backgroundColor: "{{colors.primary}}"
    textColor: "{on_primary}"
---

## Overview
A test system.

## Do's and Don'ts
- Keep it simple.
"""


BLUE = system_text("Blue", "#FFFFFF", "#111827", "#1D4ED8", "Inter", 8, 5, 4)
AMBER = system_text(
    "Amber", "#0B0D12", "#F5F5F4", "#F59E0B", "Space Grotesk", 24, 8, 8, pill=True, on_primary="#111111"
)
GREEN = system_text("Green", "#FAF8F6", "#1D1A17", "#166534", "Fraunces", 2, 2, 2)


def test_two_systems_differ_when_three_dimensions_differ() -> None:
    blue, amber, green = (fingerprint(parse_design_md(t)) for t in (BLUE, AMBER, GREEN))
    assert (
        blue.tone == "light"
        and amber.tone == "dark"
        and blue.accent_hue == "blue"
        and amber.accent_hue == "orange"
    )
    assert (blue.corner_style == "soft" and amber.corner_style == "round") or amber.corner_style == "pill"
    assert (
        is_different_enough(blue, amber)
        and is_different_enough(blue, green)
        and is_different_enough(amber, green)
    )
    only_colour = fingerprint(parse_design_md(BLUE.replace("#1D4ED8", "#DC2626")))
    assert differences(blue, only_colour) == ["accent hue"] and not is_different_enough(blue, only_colour)


def test_a_specimen_page_uses_the_tokens_and_survives_a_half_written_system() -> None:
    html = specimen_html(parse_design_md(AMBER), headline="Fresh bread at dawn")
    assert (
        "--color-primary: #F59E0B" in html
        and "Fresh bread at dawn" in html
        and "Space Grotesk" in html
        and "<script" not in html
    )
    assert "<body" in specimen_html(parse_design_md("---\nname: Bare\n---\n"))


async def test_the_specimen_is_drawn_and_candidates_are_compared(original_repo: Path, tmp_path: Path) -> None:
    pytest.importorskip("playwright.async_api")
    workspace = create_workspace(original_repo, tmp_path / "ws", "backend")
    context = ToolContext(workspace=workspace)
    for letter, text in (("a", BLUE), ("b", AMBER), ("c", GREEN)):
        workspace.write_text(f".forge/candidates/{letter}/DESIGN.md", text, "x")
    workspace.write_text(".forge/candidates/similar/DESIGN.md", BLUE.replace("#1D4ED8", "#0E7490"), "x")
    shot = await DesignSpecimen().run(
        DesignSpecimen.Args(path=".forge/candidates/b/DESIGN.md", headline="Fresh bread"), context
    )
    if not shot.ok and "browser" in shot.content:
        pytest.skip(shot.content)
    assert shot.ok, shot.content
    assert (workspace.root / ".forge" / "candidates" / "b-specimen.png").stat().st_size > 5000

    chosen = await DesignCandidates().run(
        DesignCandidates.Args(
            brief="A bakery site that feels warm",
            candidates=[f".forge/candidates/{x}/DESIGN.md" for x in "abc"],
        ),
        context,
    )
    assert chosen.ok and "No score was available" in chosen.content and "TOO SIMILAR" not in chosen.content
    assert (workspace.root / ".forge" / "candidates" / "specimen-A.png").is_file()

    again = await DesignCandidates().run(
        DesignCandidates.Args(
            brief="A bakery site",
            candidates=[".forge/candidates/a/DESIGN.md", ".forge/candidates/similar/DESIGN.md"],
            rejected=[".forge/candidates/a/DESIGN.md"],
            rejected_reason="too corporate",
        ),
        context,
    )
    assert "TOO SIMILAR" in again.content and "TOO CLOSE TO THE REJECTED DESIGN" in again.content
    rounds = (workspace.root / ".forge" / "design-rounds.json").read_text(encoding="utf-8")
    assert "too corporate" in rounds and "bakery" in rounds
    assert not (
        await DesignCandidates().run(
            DesignCandidates.Args(brief="x", candidates=["nope.md", "nope2.md"]), context
        )
    ).ok


def test_the_candidates_used_here_are_valid_design_files() -> None:
    for text in (BLUE, AMBER, GREEN):
        assert [f for f in lint_text(text) if f.severity == "error"] == []
