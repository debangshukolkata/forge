"""D-486: a brand page's DESIGN.md opens with its Concept (idea and signature visual); candidates need their own; applications are exempt."""

from __future__ import annotations

from pathlib import Path

import pytest

from forge.designsystem.concept import concept_fields, concept_problem, same_idea
from forge.toolkit.base import ToolContext
from forge.tools.files import WriteFile, design_gate
from forge.workspace.create import create_workspace

GOOD = """---
version: alpha
name: Stillwater
composition: lay-editorial-split
---

## Concept
Idea: A yoga studio above a river, where the whole page is the hour before the city wakes up.
Signature visual: A drawn SVG scene of rooftops, a rising sun and the river, filling the hero.
Why not generic: not a headline with a card and three columns.

## Overview
Calm.
"""


def test_a_complete_concept_passes_and_its_fields_are_read() -> None:
    assert concept_problem(GOOD) == ""
    fields = concept_fields(GOOD)
    assert (
        fields["idea"].startswith("A yoga studio above a river")
        and "drawn SVG scene" in fields["signature visual"]
    )
    assert fields["why not generic"].startswith("not a headline")


@pytest.mark.parametrize(
    ("change", "expected"),
    [
        (lambda t: t.replace("## Concept", "## Notes"), "No Concept yet"),
        (
            lambda t: t.replace(
                "Idea: A yoga studio above a river, where the whole page is the hour before the city wakes up.",
                "Idea: clean and modern",
            ),
            "`Idea:`",
        ),
        (
            lambda t: t.replace(
                "A drawn SVG scene of rooftops, a rising sun and the river, filling the hero.",
                "<what it shows>",
            ),
            "`Signature visual:`",
        ),
        (
            lambda t: t.replace(
                "A drawn SVG scene of rooftops, a rising sun and the river, filling the hero.",
                "Something calming and nice across the top of the page",
            ),
            "does not say how",
        ),
    ],
)
def test_a_missing_or_empty_concept_says_what_to_add(change, expected: str) -> None:  # type: ignore[no-untyped-def]
    problem = concept_problem(change(GOOD))
    assert expected in problem and "ONE edit" in problem


def test_an_application_screen_needs_no_concept() -> None:
    assert (
        concept_problem(
            GOOD.replace("composition: lay-editorial-split", "composition: app-dashboard").replace(
                "## Concept", "## Notes"
            )
        )
        == ""
    )


def test_candidates_with_the_same_idea_are_one_design() -> None:
    assert same_idea(GOOD, GOOD)
    assert not same_idea(GOOD, GOOD.replace("A yoga studio above a river", "A bakery that starts at four"))
    assert not same_idea(GOOD.replace("## Concept", "## Notes"), GOOD.replace("## Concept", "## Notes"))


async def test_the_page_gate_asks_for_the_concept_of_the_models_own_design_md(
    original_repo: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(
        "forge.tools.files._design_md_errors", lambda path: ""
    )  # the token lint is not what this test is about
    workspace = create_workspace(original_repo, tmp_path / "ws", "backend")
    context = ToolContext(workspace=workspace)
    context.design_md_written = True
    context.design_candidates_refusals = 3  # the candidates step is not what this test is about
    workspace.write_text("DESIGN.md", GOOD.replace("## Concept", "## Notes"), "x")
    asked = design_gate(context, "site/index.html")
    assert "needs its Concept" in asked and "Signature visual" in asked
    workspace.write_text("DESIGN.md", GOOD, "x")
    context.design_gate_rounds = 0
    assert design_gate(context, "site/index.html") == ""
    # a DESIGN.md the user supplied is never questioned
    workspace.write_text("DESIGN.md", GOOD.replace("## Concept", "## Notes"), "x")
    context.design_md_written = False
    context.design_gate_rounds = 0
    assert design_gate(context, "site/index.html") == ""


async def test_writing_a_candidate_without_a_concept_says_so_at_once(
    original_repo: Path, tmp_path: Path
) -> None:
    workspace = create_workspace(original_repo, tmp_path / "ws", "backend")
    context = ToolContext(workspace=workspace)
    result = await WriteFile().run(
        WriteFile.Args(path=".forge/candidates/a/DESIGN.md", content=GOOD.replace("## Concept", "## Notes")),
        context,
    )
    assert result.ok and "No Concept yet" in result.content
    result = await WriteFile().run(
        WriteFile.Args(path=".forge/candidates/b/DESIGN.md", content=GOOD), context
    )
    assert "No Concept yet" not in result.content
