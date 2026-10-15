"""DIE2: the DESIGN.md linter notes missing blueprint parts and decisions with no stated reason, as notes only."""

from __future__ import annotations

from forge.designsystem.lint import lint_text

NL = chr(10)
FRONT = "---" + NL + "name: Kestrel" + NL + "colors:" + NL + '  primary: "#aa3300"' + NL + "---" + NL


def rules(body: str) -> dict[str, str]:
    return {f.rule + ":" + f.path: f.severity for f in lint_text(FRONT + body)}


def test_missing_blueprint_parts_are_notes_not_errors() -> None:
    found = rules("# Kestrel" + NL + "## Overview" + NL + "Calm." + NL)
    assert found["blueprint-missing:Page Composition"] == "info"
    assert found["blueprint-missing:Accessibility"] == "info"
    assert not any(severity == "error" for key, severity in found.items() if key.startswith("blueprint"))


def test_a_present_section_is_not_reported_and_omitted_with_a_reason_is_skipped() -> None:
    body = "## Page Composition" + NL + "- Hero: a split, because the studio must be seen first" + NL
    found = rules(body)
    assert "blueprint-missing:Page Composition" not in found
    omitted = FRONT.replace("name: Kestrel", "name: Kestrel" + NL + "omitted: [motion]")
    assert "blueprint-missing:Motion and Interaction" not in {
        f.rule + ":" + f.path for f in lint_text(omitted + "# K" + NL)
    }


def test_decisions_without_a_reason_are_found() -> None:
    bare = "## Motion and Interaction" + NL + "- Fade in" + NL + "- Slide up" + NL + "- Pulse" + NL
    assert "decision-without-purpose:Motion and Interaction" in rules(bare)
    reasoned = (
        "## Motion and Interaction"
        + NL
        + "- Fade in, because it shows the page is alive"
        + NL
        + "- Slide up: so the eye follows the order"
        + NL
    )
    assert "decision-without-purpose:Motion and Interaction" not in rules(reasoned)


def test_a_drafted_design_md_has_every_blueprint_heading() -> None:
    from forge.designsystem.extract import Extracted, draft_design_md

    draft = draft_design_md(Extracted(colors={"primary": "#aa3300", "neutral": "#ffffff"}), "Kiln", "a page")
    assert [f for f in lint_text(draft) if f.rule.startswith("blueprint")] == []


def test_a_brand_composition_gets_a_brand_specimen_and_an_application_gets_the_dashboard_one() -> None:
    from forge.designsystem.spec import parse_design_md
    from forge.designsystem.specimen import specimen_html

    brand = parse_design_md(
        FRONT.replace("name: Kestrel", "name: Kestrel" + NL + "composition: lay-editorial-split")
    )
    app = parse_design_md(
        FRONT.replace("name: Kestrel", "name: Kestrel" + NL + "composition: app-form-wizard")
    )
    assert 'class="facts"' in specimen_html(brand, "A real headline") and "<table" not in specimen_html(brand)
    assert "<table" in specimen_html(app) and 'class="facts"' not in specimen_html(app)


def test_experience_and_story_are_noted_when_missing_and_the_story_needs_rhythm() -> None:
    found = rules("# K" + NL + "## Overview" + NL + "Calm." + NL)
    assert found["blueprint-missing:Experience"] == "info" and found["blueprint-missing:Story"] == "info"
    flat = "## Story" + NL + "1. Hero, rich" + NL + "2. Facts, rich" + NL + "3. Menu, rich" + NL
    assert "story-without-rhythm:Story" in rules(flat)  # three steps but one density level
    good = (
        "## Story"
        + NL
        + "1. Desire: the loaf, rich"
        + NL
        + "2. Trust: hours, quiet"
        + NL
        + "3. Craft: the hands, dramatic"
        + NL
    )
    assert "story-without-rhythm:Story" not in rules(good)
    app = FRONT.replace("name: Kestrel", "name: Kestrel" + NL + "composition: app-form-wizard")
    assert "blueprint-missing:Story" not in {f.rule + ":" + f.path for f in lint_text(app + "# K" + NL)}
