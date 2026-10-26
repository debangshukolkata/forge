"""D-488: the brief is recognised as an application screen or a brand page, the closest ready-made screens are named, and the page is refused until the named screen is copied."""

from __future__ import annotations

from pathlib import Path

import pytest

from forge.designsystem.brief_kind import classify_brief
from forge.toolkit.base import ToolContext
from forge.tools.design_candidates import _closest_screens, _kind_notes
from forge.tools.files import COMPOSITION_REFUSALS, composition_copy_problem
from forge.workspace.create import create_workspace


@pytest.mark.parametrize(
    "brief",
    [
        "Build a web app where managers approve or reject expense claims and purchase orders.",
        "A stock screen for a bakery that shows what is running low and lets the manager order more.",
        "Screen where agents work through customer tickets and see which are close to missing the reply deadline.",
        "An admin panel for our back office: users, roles and an audit log.",
        "Import a CSV of customers and map its columns.",
    ],
)
def test_a_tool_brief_reads_as_an_application(brief: str) -> None:
    verdict = classify_brief(brief)
    assert verdict.kind == "application", (brief, verdict)
    assert verdict.reason.startswith("it talks about")


@pytest.mark.parametrize(
    "brief",
    [
        "Design a one-page landing page for Stillwater, a yoga studio in Lisbon, with a booking section.",
        "A portfolio website for a photographer.",
        "Marketing site for our CRM product with a hero and pricing.",
    ],
)
def test_a_page_that_introduces_something_reads_as_a_brand_page(brief: str) -> None:
    assert classify_brief(brief).kind == "brand", brief


def test_a_brief_with_no_clear_words_is_left_unclear() -> None:
    assert classify_brief("Make it look nice.").kind == "unclear"


@pytest.fixture
def context(original_repo: Path, tmp_path: Path) -> ToolContext:
    return ToolContext(workspace=create_workspace(original_repo, tmp_path / "ws", "backend"))


def test_the_closest_screens_for_a_brief_come_from_the_catalogue(context: ToolContext) -> None:
    assert _closest_screens(context, "stock levels with reorder alerts for a kitchen")[0].startswith(
        "app-inventory-levels"
    )
    assert _closest_screens(context, "approve expense claims and purchase orders")[0].startswith(
        "app-approval-queue"
    )
    assert all(
        not item.startswith("app-react-") for item in _closest_screens(context, "support ticket queue")
    )


def test_an_application_brief_is_told_so_and_a_brand_layout_is_pointed_at_the_screens(
    context: ToolContext,
) -> None:
    notes = _kind_notes(
        context,
        "Build a screen for support agents to work through tickets before reply deadlines.",
        {"a": "lay-editorial-split", "b": "app-helpdesk-queue"},
    )
    text = "\n".join(notes)
    assert (
        "READS AS AN APPLICATION SCREEN" in text
        and "app-helpdesk-queue" in text
        and "ds-office-polish" in text
    )
    assert (
        "a: `lay-editorial-split` is a layout for a brand page" in text
        and "b:" not in text.split("READS AS")[1].split("a:")[0] + "x"[:0]
    )
    brand = _kind_notes(
        context, "A landing page for a yoga studio.", {"a": "app-dashboard-kpi", "b": "lay-poster-hero"}
    )
    assert (
        any("a: `app-dashboard-kpi` is an application screen" in note for note in brand) and len(brand) == 1
    )


def test_the_page_is_refused_until_the_named_screen_is_copied_and_never_more_than_three_times(
    context: ToolContext,
) -> None:
    design = "---\nname: Signoff\ncomposition: app-approval-queue\n---\n"
    asked = composition_copy_problem(context, design)
    assert "add_asset" in asked and "`app-approval-queue`" in asked and "composition: custom" in asked
    context.assets_added.add("app-approval-queue")
    assert composition_copy_problem(context, design) == ""
    context.assets_added.clear()
    context.assets_added.add("app-react-approval-queue")  # the React version of the same screen counts too
    assert composition_copy_problem(context, design) == ""
    context.assets_added.clear()
    context.composition_refusals = COMPOSITION_REFUSALS
    assert composition_copy_problem(context, design) == ""  # a wrong refusal can never trap the model


def test_a_custom_unknown_or_brand_composition_is_never_refused(context: ToolContext) -> None:
    for line in (
        "composition: custom a split view for pickers",
        "composition: app-northline-invented",
        "composition: lay-editorial-split",
    ):
        assert composition_copy_problem(context, f"---\nname: X\n{line}\n---\n") == "", line
