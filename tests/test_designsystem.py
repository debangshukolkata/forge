"""D-348: DESIGN.md files are parsed, linted, diffed and exported to code (DS1)."""

from __future__ import annotations

import json

import pytest

from forge.designsystem.colour import contrast, parse
from forge.designsystem.diff import describe_diff, diff_systems
from forge.designsystem.export import export
from forge.designsystem.lint import describe_findings, lint_text
from forge.designsystem.spec import DesignMdError, parse_design_md

GOOD = """---
version: alpha
name: Daylight Prestige
colors:
  primary: "#1A1C1E"
  secondary: "#6C7278"
  tertiary: "#B8422E"
  neutral: "#F7F5F2"
typography:
  h1:
    fontFamily: Public Sans
    fontSize: 48px
    fontWeight: 600
    lineHeight: 1.1
    letterSpacing: -0.02em
  body-md:
    fontFamily: Public Sans
    fontSize: 16px
    fontWeight: 400
    lineHeight: 1.6
rounded:
  sm: 4px
  md: 8px
spacing:
  sm: 8px
  md: 16px
  lg: 32px
omitted:
  - section: elevation
    reason: "Flat design; hierarchy conveyed by color contrast"
components:
  button-primary:
    backgroundColor: "{colors.tertiary}"
    textColor: "{colors.neutral}"
    rounded: "{rounded.md}"
    padding: 12px
  button-primary-hover:
    backgroundColor: "#9A3725"
    textColor: "{colors.neutral}"
---

# Daylight Prestige

## Overview
A calm, institutional brand with a single warm accent for action.

## Colors
- **Primary (#1A1C1E):** Deep ink for headlines and core text.

## Typography
Public Sans carries the narrative.

## Layout
A strict 8px spacing scale.

## Shapes
A minimal 4px corner radius.

## Components
Buttons use the tertiary colour.

## Do's and Don'ts
- Do use the tertiary colour only for the single most important action per screen.
"""


def _rules(text: str) -> list[tuple[str, str]]:
    return [(f.severity, f.rule) for f in lint_text(text)]


def test_the_specifications_own_example_is_valid() -> None:
    findings = lint_text(GOOD)
    assert [f for f in findings if f.severity in ("error", "warning")] == [], describe_findings(findings)
    system = parse_design_md(GOOD)
    assert system.name == "Daylight Prestige" and system.version == "alpha"
    assert [s.canonical for s in system.sections][:3] == ["overview", "colors", "typography"]
    assert system.resolve("{colors.tertiary}") == "#B8422E" and system.omitted == ["elevation"]


def test_colours_are_parsed_in_the_usual_forms_and_contrast_is_measured() -> None:
    assert parse("#fff") == (255, 255, 255, 1.0) and parse("rgb(10, 20, 30)") == (10, 20, 30, 1.0)
    assert parse("hsl(0, 100%, 50%)") == (255, 0, 0, 1.0) and parse("oklch(0.5 0.1 200)") is None
    assert parse("#00000080")[3] == pytest.approx(0.5, abs=0.01)  # type: ignore[index]
    assert contrast("#000000", "#ffffff") == pytest.approx(21.0, abs=0.1)
    assert contrast("#ffffff", "rgba(0,0,0,0.5)") is None


def test_structural_problems_are_reported_with_stable_rule_names() -> None:
    assert ("error", "no-front-matter") in _rules("# Only prose\n\n## Overview\nhello")
    assert ("error", "bad-front-matter") in _rules("---\nname: [unclosed\n---\n")
    assert ("error", "missing-name") in _rules("---\ncolors:\n  primary: '#111111'\n---\n")
    assert ("error", "missing-primary") in _rules("---\nname: x\ncolors:\n  accent: '#111111'\n---\n")
    duplicate = GOOD + "\n## Colors\nagain\n"
    assert ("error", "duplicate-section") in _rules(duplicate)
    shuffled = GOOD.replace("## Overview", "## Typography", 1)
    assert any(rule in ("duplicate-section", "section-order") for _, rule in _rules(shuffled))
    assert ("warning", "missing-section") in _rules(
        "---\nname: x\ncolors:\n  primary: '#111111'\n---\n## Overview\nx\n"
    )


def test_references_units_and_unknown_properties() -> None:
    broken = GOOD.replace('"{colors.tertiary}"', '"{colors.nope}"')
    assert ("error", "broken-reference") in _rules(broken)
    group = GOOD.replace('"{colors.tertiary}"', '"{colors}"')
    assert ("error", "reference-to-group") in _rules(group) or ("error", "bad-colour") in _rules(group)
    assert ("error", "bad-dimension") in _rules(GOOD.replace("sm: 4px", "sm: 4pt"))
    assert ("warning", "unknown-component-property") in _rules(GOOD.replace("padding: 12px", "shadow: big"))
    assert ("error", "bad-colour") in _rules(GOOD.replace('"#B8422E"', '"notacolour"'))
    assert ("info", "bad-colour") in _rules(GOOD.replace('"#B8422E"', '"oklch(0.6 0.2 30)"'))


def test_low_contrast_pairs_are_errors() -> None:
    low = GOOD.replace('textColor: "{colors.neutral}"\n    rounded', 'textColor: "#C9C9C9"\n    rounded', 1)
    findings = lint_text(low)
    assert any(f.rule == "low-contrast" and "button-primary" in f.path for f in findings)
    page = GOOD.replace('primary: "#1A1C1E"', 'primary: "#F4F1EE"')
    assert ("error", "low-contrast") in _rules(page)


def test_palette_problems_are_warnings() -> None:
    one_note = (
        "---\nname: x\ncolors:\n  primary: '#1E40AF'\n  a: '#2563EB'\n  b: '#3B82F6'\n  c: '#1D4ED8'\n  d: '#2F5FD0'\n---\n"
        "## Overview\nx\n## Do's and Don'ts\ny\n"
    )
    assert ("warning", "one-note-palette") in _rules(one_note)
    many = (
        "---\nname: x\ncolors:\n  primary: '#1E40AF'\n"
        + "".join(
            f"  c{i}: '{c}'\n"
            for i, c in enumerate(["#DC2626", "#16A34A", "#EAB308", "#9333EA", "#0891B2", "#EA580C"])
        )
        + "---\n## Overview\nx\n## Do's and Don'ts\ny\n"
    )
    assert ("warning", "too-many-accents") in _rules(many)


def test_export_formats_resolve_references_and_add_font_fallbacks() -> None:
    system = parse_design_md(GOOD)
    css = export(system, "css-tailwind")
    assert css.startswith("/* Generated from DESIGN.md") and "@theme {" in css
    assert "--color-tertiary: #B8422E;" in css and '--font-h1: "Public Sans", sans-serif;' in css
    assert (
        "--text-h1: 48px;" in css
        and "--text-h1--line-height: 1.1;" in css
        and "--radius-md: 8px;" in css
        and "--spacing-lg: 32px;" in css
    )
    assert export(system, "css-variables").count(":root {") == 1
    tokens = json.loads(export(system, "dtcg"))
    assert (
        tokens["color"]["primary"] == {"$type": "color", "$value": "#1A1C1E"}
        and tokens["radius"]["md"]["$value"] == "8px"
    )
    tailwind = json.loads(export(system, "tailwind"))["theme"]["extend"]
    assert tailwind["colors"]["tertiary"] == "#B8422E" and tailwind["borderRadius"]["sm"] == "4px"
    assert (
        tailwind["fontSize"]["body-md"][0] == "16px"
        and tailwind["fontSize"]["body-md"][1]["lineHeight"] == 1.6
    )
    with pytest.raises(DesignMdError, match="Unknown format"):
        export(system, "figma")
    with pytest.raises(DesignMdError, match="does not exist"):
        export(
            parse_design_md(
                GOOD.replace('"{colors.tertiary}"', '"{colors.nope}"').replace(
                    'tertiary: "#B8422E"', 'tertiary: "{colors.nope}"'
                )
            ),
            "css-tailwind",
        )


def test_our_extensions_and_the_shadcn_style_extras_are_kept_not_rejected() -> None:
    extended = GOOD.replace(
        "version: alpha\n", "version: alpha\nwebsite: https://example.com\nseo:\n  tags: [a, b]\n"
    ).replace(
        "## Do's and Don'ts",
        "## Responsive Behavior\nCollapse to one column.\n\n## Known Gaps\nThe display font is licensed.\n\n## Do's and Don'ts",
    )
    findings = lint_text(extended)
    assert [f for f in findings if f.severity in ("error",)] == []
    system = parse_design_md(extended)
    assert system.extra["website"] == "https://example.com" and any(
        s.heading == "Known Gaps" for s in system.sections
    )
    assert not any(
        f.rule == "extra-section" and f.path in ("Known Gaps", "Responsive Behavior") for f in findings
    )


def test_diff_lists_token_changes_and_flags_regressions() -> None:
    before = parse_design_md(GOOD)
    after = parse_design_md(
        GOOD.replace('tertiary: "#B8422E"', 'tertiary: "#C0C0C0"').replace("lg: 32px", "lg: 40px")
    )
    result = diff_systems(before, after)
    assert {(c.kind, c.path) for c in result.changes} == {
        ("changed", "colors.tertiary"),
        ("changed", "spacing.lg"),
    }
    assert result.regression and any(f.rule == "low-contrast" for f in result.new_findings)
    assert "REGRESSION" in describe_diff(result)
    assert describe_diff(diff_systems(before, before)) == "No token changes and no new findings."


def test_a_system_font_in_a_design_md_is_a_warning_and_the_specimen_embeds_bundled_fonts() -> None:
    from forge.designsystem.fonts import font_css
    from forge.designsystem.specimen import families_of, specimen_html

    system_font = GOOD.replace("fontFamily: Public Sans", "fontFamily: system-ui")
    assert ("warning", "system-font") in _rules(system_font)
    assert ("warning", "system-font") not in _rules(GOOD)
    css, missing = font_css(["Fraunces", "Totally Unknown Font"])
    assert "@font-face" in css and "data:font/woff2;base64," in css and missing == ["Totally Unknown Font"]
    system = parse_design_md(GOOD.replace("Public Sans", "Fraunces"))
    assert families_of(system) == ["Fraunces"] and "data:font/woff2" in specimen_html(system)
