"""D-379: the design ladder tells the model to import the winning candidate from .forge/candidates/<x>/DESIGN.md; the import tool refused every .forge path outside the image folders
(seen live: two refused calls, then a hand copy)."""

from __future__ import annotations

from pathlib import Path

from forge.toolkit.base import ToolContext
from forge.tools.design_inspire import DesignMdImport
from forge.workspace.create import create_workspace

DESIGN = """---
name: Pulse
colors:
  primary: "#B3261E"
  neutral: "#FFFFFF"
  ink: "#1A1A1A"
  muted: "#5B5B5B"
  surface: "#F7F3F0"
  border: "#E0D9D4"
typography:
  display:
    fontFamily: Fraunces
    fontSize: 48px
    fontWeight: 600
    lineHeight: 1.1
  body-md:
    fontFamily: Inter
    fontSize: 16px
    fontWeight: 400
    lineHeight: 1.5
rounded:
  md: 10px
spacing:
  md: 16px
---
## Overview
A calm, warm home for people who give blood.
"""


async def test_the_winning_candidate_can_be_imported_from_the_candidates_folder(
    original_repo: Path, tmp_path: Path
) -> None:
    workspace = create_workspace(original_repo, tmp_path / "ws", "backend")
    context = ToolContext(workspace=workspace, design_first=False)
    workspace.write_text(".forge/candidates/c/DESIGN.md", DESIGN, "a candidate")
    done = await DesignMdImport().run(
        DesignMdImport.Args(source=".forge/candidates/c/DESIGN.md", output="DESIGN.md", overwrite=True),
        context,
    )
    assert done.ok, done.content
    assert "Pulse" in workspace.path_of("DESIGN.md").read_text(encoding="utf-8")
    elsewhere = await DesignMdImport().run(
        DesignMdImport.Args(source=".forge/secrets/DESIGN.md", output="X.md", overwrite=True), context
    )
    assert not elsewhere.ok  # other .forge folders stay closed


async def test_a_candidate_without_a_composition_is_told_at_once_how_to_fix_it(
    original_repo: Path, tmp_path: Path
) -> None:
    """D-386: design_candidates refuses a candidate that names no composition, and the model rewrote all three files; the write result now says it in one line."""
    from forge.tools.files import WriteFile

    workspace = create_workspace(original_repo, tmp_path / "ws", "backend")
    context = ToolContext(workspace=workspace, design_first=False)
    bare = await WriteFile().run(
        WriteFile.Args(path=".forge/candidates/a/DESIGN.md", content=DESIGN), context
    )
    assert (
        bare.ok and "does not name its composition yet" in bare.content and "ONE small edit" in bare.content
    )
    named = DESIGN.replace("name: Pulse\n", "name: Pulse\ncomposition: lay-editorial-split\n", 1)
    fine = await WriteFile().run(WriteFile.Args(path=".forge/candidates/b/DESIGN.md", content=named), context)
    assert fine.ok and "composition yet" not in fine.content
    elsewhere = await WriteFile().run(WriteFile.Args(path="docs/DESIGN.md", content=DESIGN), context)
    assert elsewhere.ok and "composition yet" not in elsewhere.content  # only candidates are reminded
