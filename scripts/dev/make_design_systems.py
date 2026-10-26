"""Makes the design-system assets of the ui-design-quality skill (TODO DS3, D-350): one tokenised DESIGN.md per visual direction and per template,
the asset descriptor for the catalogue, and a specimen picture for each. Run it again after changing a system:

    .venv\\Scripts\\python scripts/dev/make_design_systems.py

Every file is linted here and the script stops on an error or warning. Then run `scripts/build_asset_catalogue.py`."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from pathlib import Path

from forge.brand.kit import mix, readable_on
from forge.designsystem.lint import describe_findings, lint_text
from forge.designsystem.spec import parse_design_md
from forge.designsystem.specimen import specimen_html
from forge.tools.design_candidates import draw

SKILL = Path(__file__).resolve().parents[2] / "src" / "forge" / "skills" / "ui-design-quality"


@dataclass
class System:
    id: str
    title: str
    summary: str
    moods: list[str]
    products: list[str]
    source: str
    neutral: str
    surface: str
    ink: str
    muted: str
    primary: str
    border: str
    display_font: str
    body_font: str
    sm: int
    md: int
    pill: bool
    dials: tuple[int, int, int]  # density, variance, motion
    overview: str
    colours_note: str
    dos: list[str]
    secondary: str = ""
    on_primary: str = ""
    extra_colours: dict[str, str] = field(default_factory=dict)
    display_weight: int = 700
    display_size: int = 56
    tracking: str = "-0.02em"
    composition: str = ""  # the layout recipe (find_asset type section, tag composition) this system suits
    gaps: str = "Fonts are named, not bundled: load them with find_font or fall back to the system stack."


SYSTEMS = [
    System(
        "ds-soft-editorial",
        "Soft editorial",
        "Warm off-white, a serif display, generous whitespace and soft shadows: humane and trustworthy.",
        ["warm", "calm", "trustworthy", "editorial"],
        ["health", "charity", "education", "boutique"],
        "dir-soft-editorial",
        "#FAF8F6",
        "#FFFFFF",
        "#1D1A17",
        "#6B625A",
        "#9F1D20",
        "#E7E1DB",
        "Fraunces",
        "Inter",
        12,
        20,
        True,
        (3, 5, 3),
        "A humane, unhurried look for places people come to for care or learning. It must feel like a well-set magazine page, not a SaaS dashboard.",
        "One deep red accent for the single action on a screen; everything else is warm ink and paper. No second accent.",
        [
            "Use the accent only for the one primary action per screen",
            "Set headlines in the serif and everything else in Inter",
            "Leave at least 64px between sections",
            "Never use a cool grey; neutrals are warm",
        ],
        display_weight=600,
        tracking="-0.01em",
    ),
    System(
        "ds-clean-product",
        "Clean product",
        "White and pale blue-grey, one saturated accent, navy text, layered soft shadows: confident B2B.",
        ["clean", "confident", "precise"],
        ["b2b", "fintech", "dashboards", "saas"],
        "dir-clean-product",
        "#FFFFFF",
        "#F6F9FC",
        "#0A2540",
        "#425466",
        "#5546FF",
        "#E3E8EE",
        "Inter",
        "Inter",
        8,
        12,
        False,
        (5, 4, 3),
        "A product site that looks like the product: precise, quiet, trustworthy. Left-aligned hero with a product mockup on the right.",
        "One saturated indigo accent on a white and pale blue-grey page; navy text, never black.",
        [
            "Left-align headings",
            "Numbers use tabular figures",
            "One highlighted pricing card, never two",
            "Shadows are layered and soft, borders are 1px",
        ],
    ),
    System(
        "ds-dark-dashboard",
        "Dark dashboard",
        "Near-black surfaces, light text, one indigo accent and clear status colours: dense and calm.",
        ["dark", "dense", "technical", "calm"],
        ["analytics", "ops", "monitoring", "admin"],
        "dir-dark-dashboard",
        "#0B0D12",
        "#12151C",
        "#E5E7EB",
        "#9CA3AF",
        "#818CF8",
        "#1F2330",
        "Inter",
        "Inter",
        6,
        10,
        False,
        (8, 3, 2),
        "A tool people stare at all day: dense, legible, restful. Data first, chrome second.",
        "Indigo accent for selection and the primary action; green, amber and red mean status and nothing else.",
        [
            "Body text is 13-14px with tabular figures",
            "Charts use one accent plus muted greys",
            "Status colours carry a label or icon too",
            "Sticky table headers and a 240px left nav",
        ],
        on_primary="#0B0D12",
        extra_colours={"ok": "#34D399", "warn": "#FBBF24", "error": "#F87171"},
        display_size=40,
        display_weight=600,
    ),
    System(
        "ds-bold-poster",
        "Bold campaign poster",
        "Near-black, one hot colour, huge grotesk type and hard offset shadows: loud and urgent.",
        ["bold", "urgent", "loud"],
        ["events", "drives", "launches", "sport"],
        "dir-bold-poster",
        "#0B0B0C",
        "#18181B",
        "#FFFFFF",
        "#D4D4D8",
        "#E11D48",
        "#3F3F46",
        "Space Grotesk",
        "Inter",
        0,
        4,
        False,
        (6, 9, 7),
        "A poster that happens to be a website: one message, shouted, with a countdown or a number as the hero.",
        "Near-black with one hot red; white type. A second hot colour (yellow) may appear once, as a sticker.",
        [
            "Headlines are 72-140px, tight tracking, uppercase labels",
            "Corners are sharp or one big radius, borders 2-3px",
            "Hard offset shadows only",
            "One hero number or countdown",
        ],
        on_primary="#FFFFFF",
        display_size=96,
        display_weight=800,
        tracking="-0.04em",
    ),
    System(
        "ds-neo-brutalist",
        "Neo-brutalist",
        "Flat saturated colours on cream with thick black outlines and hard shadows: playful and honest.",
        ["playful", "raw", "honest"],
        ["creative tools", "indie products", "playful brands"],
        "dir-neo-brutalist",
        "#FFFAF0",
        "#FFFFFF",
        "#111111",
        "#3F3F46",
        "#FF6B6B",
        "#111111",
        "Space Grotesk",
        "Space Mono",
        0,
        6,
        False,
        (5, 7, 5),
        "A product that does not take itself too seriously and is still easy to use. The grid is visible, the shadows are hard.",
        "Flat saturated red on cream with yellow and teal as the only other colours; black outlines everywhere.",
        [
            "3px black borders and 4-8px hard shadows",
            "No gradients and no blur",
            "Tilt a card at most -1.5 degrees",
            "Mono type for labels and numbers",
        ],
        secondary="#FFDE59",
        on_primary="#111111",
        extra_colours={"teal": "#4ECDC4"},
        display_weight=800,
    ),
    System(
        "ds-glass-aurora",
        "Glass and aurora",
        "A dark base, frosted glass panels and a sparing indigo-to-cyan glow: modern AI and developer tools.",
        ["dark", "modern", "glowing"],
        ["saas", "ai", "developer tools"],
        "dir-glass-aurora",
        "#0A0B10",
        "#14161F",
        "#F4F4F8",
        "#A5A8B8",
        "#9D8CFF",
        "#2A2D3A",
        "Geist",
        "Inter",
        12,
        20,
        False,
        (5, 6, 6),
        "A product that feels like light behind glass. The glow is a seasoning, never the meal.",
        "Violet accent with a cyan highlight used once; glass panels are translucent white over the dark base.",
        [
            "Glow appears once per screen",
            "Panels use a 1px light border and blur 16-24px",
            "Light weights for display type",
            "Never put body text on the glow",
        ],
        secondary="#22D3EE",
        on_primary="#0A0B10",
        display_weight=300,
        tracking="-0.03em",
    ),
    System(
        "ds-minimal-monochrome",
        "Minimal monochrome",
        "Black, white, one grey and one accent used once per screen; large type and huge margins.",
        ["minimal", "refined", "quiet"],
        ["portfolio", "architecture", "luxury"],
        "dir-minimal-monochrome",
        "#FFFFFF",
        "#F5F5F5",
        "#0A0A0A",
        "#525252",
        "#C2410C",
        "#E5E5E5",
        "Newsreader",
        "Inter",
        0,
        0,
        False,
        (2, 3, 1),
        "Calm and exact. Minimal is not empty: it needs excellent type and real content.",
        "Black on white with one grey; the orange accent appears once per screen, as a single mark or link.",
        [
            "No shadows and no gradients",
            "Thin rules instead of boxes",
            "Real photography or none",
            "A strict grid with a visible baseline",
        ],
        display_weight=400,
        display_size=72,
        tracking="-0.03em",
    ),
    System(
        "ds-playful-friendly",
        "Playful and friendly",
        "Bright, rounded and bouncy: big radii, thick-stroke icons and a rounded sans.",
        ["playful", "friendly", "bright"],
        ["kids", "food", "community", "consumer apps"],
        "dir-playful-friendly",
        "#FFFDF7",
        "#FFFFFF",
        "#2B2118",
        "#6B5B4B",
        "#FF7A59",
        "#F1E6D3",
        "Nunito",
        "Nunito",
        16,
        28,
        True,
        (4, 6, 7),
        "A product people smile at. Big shapes, friendly words, nothing sharp.",
        "Coral accent with sunny yellow and mint as supporting colours on warm white.",
        [
            "Radius 28px and pills",
            "Thick-stroke icons, no emoji as icons",
            "Bouncy easing on hover only",
            "Rounded sans for headings",
        ],
        secondary="#FFD166",
        on_primary="#2B2118",
        extra_colours={"mint": "#06D6A0"},
        display_weight=800,
    ),
    System(
        "ds-claymorphism",
        "Claymorphism",
        "Pastel fills, chunky radii and soft inner shadows that make everything look moulded: gentle and tactile.",
        ["soft", "tactile", "gentle"],
        ["onboarding", "games", "kids products"],
        "dir-claymorphism",
        "#F3F7FF",
        "#FFFFFF",
        "#1F2A44",
        "#4B5675",
        "#7F9CFF",
        "#DCE4F7",
        "Nunito",
        "Nunito",
        20,
        32,
        True,
        (3, 5, 6),
        "A toy-like, friendly surface. Use sparingly: it tires the eye on long pages.",
        "Pastel blue accent on a pale blue page; pink and yellow may tint cards.",
        [
            "Radius 24-32px, no borders",
            "Double inner shadows for depth",
            "Chunky icons",
            "Do not use for dense or data-heavy screens",
        ],
        on_primary="#1F2A44",
        display_weight=800,
    ),
    System(
        "ds-retro-terminal",
        "Retro terminal",
        "Monospace type, 1px borders and phosphor green on black: for developer tools and nostalgia.",
        ["retro", "technical", "nostalgic"],
        ["developer tools", "games"],
        "dir-retro-terminal",
        "#0A0F0A",
        "#101810",
        "#B6F2B6",
        "#7BD389",
        "#33FF66",
        "#1F3A1F",
        "JetBrains Mono",
        "JetBrains Mono",
        0,
        2,
        False,
        (6, 2, 3),
        "A screen that looks like it runs on a CRT, with the contrast kept high so it stays readable.",
        "Phosphor green on black, with amber as the only other colour.",
        [
            "Monospace everywhere",
            "1px borders and ASCII dividers",
            "A blinking caret, never more than one animation",
            "Keep contrast above 7:1",
        ],
        on_primary="#0A0F0A",
        secondary="#FFB000",
        display_size=40,
        display_weight=700,
        tracking="0",
    ),
    System(
        "ds-bento",
        "Bento and cards",
        "An unequal grid of rounded tiles, each holding one idea, in neutral tones with two tinted accents.",
        ["modern", "organised", "light"],
        ["feature overviews", "personal sites", "dashboard home"],
        "dir-bento",
        "#F5F5F4",
        "#FFFFFF",
        "#1C1917",
        "#57534E",
        "#0F766E",
        "#E7E5E4",
        "Inter",
        "Inter",
        16,
        24,
        False,
        (5, 5, 4),
        "A page of tiles: a number, a chart, a quote, a small illustration. The layout is the design.",
        "Neutral tiles with teal and amber tints; text stays on white or the neutral.",
        [
            "Tiles span 2x2, 1x2 or 1x1, never all equal",
            "One idea per tile",
            "Teal for action, amber for highlight, nothing else",
            "Tile padding 24px",
        ],
        secondary="#B45309",
        display_weight=700,
    ),
    System(
        "ds-tpl-charity",
        "Charity and community (template palette)",
        "The palette and type of the charity landing template: warm paper, ink and one brave red.",
        ["warm", "editorial", "trustworthy"],
        ["charity", "health", "community", "events", "education"],
        "the charity template (recipes/templates/charity)",
        "#FAF8F6",
        "#FFFFFF",
        "#1D1A17",
        "#6B625A",
        "#C62828",
        "#E7E1DB",
        "Fraunces",
        "Inter",
        12,
        20,
        True,
        (4, 5, 4),
        "Warm, editorial and urgent without shouting: a drive or a cause with a face on it.",
        "Brave red for action on warm paper; green and amber only for status.",
        [
            "One red action per screen",
            "Serif headlines, Inter body",
            "Real photographs of people, never stock smiles",
            "Stats in large serif numerals",
        ],
        display_weight=600,
        extra_colours={"ok": "#15803D", "warn": "#B45309", "error": "#B91C1C"},
    ),
    System(
        "ds-tpl-saas",
        "SaaS (template palette)",
        "The palette and type of the SaaS landing template: cool slate, one indigo accent, Plus Jakarta Sans.",
        ["clean", "modern", "confident"],
        ["saas", "b2b", "developer tools", "fintech"],
        "the SaaS template (recipes/templates/saas)",
        "#F8FAFC",
        "#FFFFFF",
        "#0F172A",
        "#5B6B82",
        "#4F46E5",
        "#E2E8F0",
        "Plus Jakarta Sans",
        "Inter",
        8,
        14,
        True,
        (5, 5, 4),
        "A product page that explains one thing well and then shows it.",
        "Indigo accent on cool slate; ink is navy-black.",
        [
            "Hero headline states the outcome",
            "One highlighted plan",
            "Logos in a muted row",
            "Numbers use tabular figures",
        ],
        extra_colours={"ok": "#15803D", "warn": "#B45309", "error": "#B91C1C"},
    ),
    System(
        "ds-tpl-portfolio",
        "Portfolio (template palette)",
        "The palette and type of the portfolio template: white, stone and ink with a Playfair display.",
        ["refined", "editorial", "quiet"],
        ["portfolio", "studio", "photography", "writing"],
        "the portfolio template (recipes/templates/portfolio)",
        "#FFFFFF",
        "#F5F5F4",
        "#1C1917",
        "#6B6560",
        "#1C1917",
        "#E7E5E4",
        "Playfair Display",
        "DM Sans",
        4,
        8,
        False,
        (3, 6, 2),
        "The work is the design. Type and spacing carry the personality; colour stays out of the way.",
        "Ink on white and stone; the accent is the ink itself.",
        [
            "Let images run large",
            "Playfair for titles, DM Sans for text",
            "Project metadata in small caps",
            "No decoration",
        ],
        display_weight=500,
        extra_colours={"ok": "#15803D", "warn": "#B45309", "error": "#B91C1C"},
    ),
    System(
        "ds-office-polish",
        "Office polish",
        "Cool off-white page, white cards with a hairline border and one soft shadow, one orange accent, tinted status chips with an inner ring, Inter: calm, finished back-office screens.",
        ["businesslike", "calm", "polished", "light"],
        ["back office", "admin", "crm", "case management", "government", "operations", "erp"],
        "the design philosophy of a user-owned back-office app (D-489)",
        "#F7F8FA",
        "#FFFFFF",
        "#1C1C1E",
        "#5F6672",
        "#A34C00",
        "#E5E7EB",
        "Inter",
        "Inter",
        8,
        12,
        True,
        (5, 2, 4),
        "An office tool people use all day: quiet, regular and finished. One orange accent marks the main action, the active menu item and the counts; everything else is neutral. Every coloured label is built the same way, every card the same way, so the whole app reads as one system.",
        "Orange is the only accent. The filled controls use the deeper orange (primary) so white text passes contrast; the bright orange (brand) is for the active-item bar, tab underline, progress, focus ring and icon chips, never for text on white.",
        [
            "One accent: orange marks the main action, the active menu item and the counts; everything else stays neutral",
            "Every coloured label is built the same way: a pale tint of the colour, darker text of the same hue and a thin inner ring",
            "Cards are white on the off-white page with a 1px border and one soft shadow; a clickable card lifts 2px on hover",
            "Icons come from one family; alone (stat tiles, page headers, empty states) they sit in a soft tinted rounded square",
            "Hierarchy comes from weight and grey, not many sizes: labels 11px uppercase and spaced, titles 24px bold with tight tracking",
            "Motion is 200 to 300 ms: fade and rise on mount, lift on hover, a 98% press, a slide for drawers; nothing bounces",
            "Status is colour plus words, never colour alone; an overdue row carries a red bar on its left edge",
            "Money and dates use the reader's convention (lakh and crore, 30 Sep 2026); numbers use tabular figures",
        ],
        extra_colours={
            "brand": "#FF7A00",
            "ok": "#17693D",
            "warn": "#8A5200",
            "error": "#B42318",
            "info": "#0A6FD6",
        },
        display_weight=700,
        display_size=40,
        tracking="-0.02em",
        gaps="Inter has no Bengali or other Indic letters: for such content name a fallback face (Tiro Bangla for Bengali) with find_font. White text on the bright orange #FF7A00 is only 2.6 to 1, so filled controls use the deeper orange.",
    ),
]


COMPOSITIONS = {
    "ds-soft-editorial": "lay-editorial-split",
    "ds-bold-poster": "lay-poster-hero",
    "ds-playful-friendly": "lay-ticket-stub",
    "ds-neo-brutalist": "lay-notebook-grid",
    "ds-clean-product": "lay-fullbleed-blocks",
}  # the composition recipes (assets/section) each system pairs with; the others name none


def design_md(system: System) -> str:
    on_primary = system.on_primary or ("#" + readable_on(system.primary.lstrip("#")))
    hover = "#" + mix(
        system.primary.lstrip("#"), "000000" if on_primary.upper() == "#FFFFFF" else "FFFFFF", 0.15
    )
    colours = {
        "primary": system.primary,
        "neutral": system.neutral,
        "surface": system.surface,
        "ink": system.ink,
        "muted": system.muted,
        "border": system.border,
        **({"secondary": system.secondary} if system.secondary else {}),
        **system.extra_colours,
    }
    rounded = [f"  sm: {system.sm}px", f"  md: {system.md}px"] + (["  pill: 9999px"] if system.pill else [])
    lines = [
        "---",
        "version: alpha",
        f"name: {system.title}",
        f'description: "{system.summary}"',
        *([f"composition: {COMPOSITIONS[system.id]}"] if system.id in COMPOSITIONS else []),
        "dials:",
        f"  density: {system.dials[0]}",
        f"  variance: {system.dials[1]}",
        f"  motion: {system.dials[2]}",
        "colors:",
    ]
    lines += [f'  {role}: "{value}"' for role, value in colours.items()]
    lines += [
        "typography:",
        "  display:",
        f'    fontFamily: "{system.display_font}"',
        f"    fontSize: {system.display_size}px",
        f"    fontWeight: {system.display_weight}",
        "    lineHeight: 1.05",
        f"    letterSpacing: {system.tracking if system.tracking != '0' else '0em'}",
        "  h2:",
        f'    fontFamily: "{system.display_font}"',
        "    fontSize: 32px",
        f"    fontWeight: {min(system.display_weight, 700)}",
        "    lineHeight: 1.2",
        "  body-md:",
        f'    fontFamily: "{system.body_font}"',
        "    fontSize: 16px",
        "    fontWeight: 400",
        "    lineHeight: 1.6",
        "  body-tabular:",
        f'    fontFamily: "{system.body_font}"',
        "    fontSize: 14px",
        "    fontWeight: 400",
        "    lineHeight: 1.5",
        '    fontFeature: "tnum"',
        "rounded:",
        *rounded,
        "spacing:",
        "  xs: 4px",
        "  sm: 8px",
        "  md: 16px",
        "  lg: 32px",
        "  xl: 64px",
        "components:",
        "  button-primary:",
        '    backgroundColor: "{colors.primary}"',
        f'    textColor: "{on_primary}"',
        '    typography: "{typography.body-md}"',
        f'    rounded: "{{rounded.{"pill" if system.pill else "md"}}}"',
        "    padding: 12px",
        "  button-primary-hover:",
        f'    backgroundColor: "{hover}"',
        f'    textColor: "{on_primary}"',
        "  card:",
        '    backgroundColor: "{colors.surface}"',
        '    textColor: "{colors.ink}"',
        '    rounded: "{rounded.md}"',
        "    padding: 24px",
        "  input:",
        '    backgroundColor: "{colors.neutral}"',
        '    textColor: "{colors.ink}"',
        '    rounded: "{rounded.sm}"',
        "    padding: 12px",
        "---",
        "",
        f"# {system.title}",
        "",
        "## Overview",
        system.overview,
        f"Dials: VISUAL_DENSITY {system.dials[0]}, DESIGN_VARIANCE {system.dials[1]}, MOTION_INTENSITY {system.dials[2]} (1-10). Use for: {', '.join(system.products)}.",
        "",
        "## Colors",
        system.colours_note,
        "",
        "## Typography",
        f"{system.display_font} for display and headings, {system.body_font} for text. Numbers in tables use tabular figures.",
        "",
        "## Layout",
        "Container 1180px, breakpoints 375 / 768 / 1280, spacing scale 4-8-16-32-64, one left edge per column.",
        "",
        "## Shapes",
        f"Corners {system.sm}px and {system.md}px" + (", buttons are pills." if system.pill else "."),
        "",
        "## Do's and Don'ts",
        *[f"- {rule}" for rule in system.dos],
        "",
        "## Responsive Behavior",
        "Grids collapse to one column at 768px, navigation to a menu, tables to cards; touch targets are at least 44px.",
        "",
        "## Known Gaps",
        f"- {system.gaps}",
        f"- Derived from {system.source}; adapt every value to the product before building.",
    ]
    return "\n".join(lines) + "\n"


def asset_md(system: System) -> str:
    return f'''---
id: {system.id}
type: design-system
title: "{system.title}"
summary: "{system.summary}"
moods: [{", ".join(system.moods)}]
products: [{", ".join(system.products)}]
tags: [design-md, tokens, tailwind v4 export]
density: {"airy" if system.dials[0] <= 3 else "dense" if system.dials[0] >= 7 else "balanced"}
dependencies: []
licence: original
source: "authored for DebCraft (D-350) from {system.source}"
tested: "the DESIGN.md lints with no errors or warnings (design_md_lint) and a specimen picture was drawn and looked at (D-350)"
files:
  - from: recipes/design-systems/{system.id}.design.md
    to: DESIGN.md
---
A complete design system in the DESIGN.md format: exact colours, type, radii, spacing and components with the reasoning. Add it with add_asset, then
adapt every value to the product (name, accent, fonts), run design_md_lint, and export the tokens with design_md_export. Do not use it unchanged for a
product it was not made for: a catalogue system is a starting point, and two products on the same file look like the same product.
'''


async def main() -> int:
    status = 0
    for system in SYSTEMS:
        text = design_md(system)
        findings = [f for f in lint_text(text) if f.severity in ("error", "warning")]
        if findings:
            print(f"{system.id}: {describe_findings(findings)}")
            status = 1
            continue
        target = SKILL / "recipes" / "design-systems" / f"{system.id}.design.md"
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(text, encoding="utf-8")
        asset = SKILL / "assets" / "design-system" / f"{system.id}.md"
        asset.parent.mkdir(parents=True, exist_ok=True)
        asset.write_text(asset_md(system), encoding="utf-8")
        picture = SKILL / "assets" / "preview" / f"{system.id}-specimen.png"
        await draw(specimen_html(parse_design_md(text)), picture)
        from PIL import Image

        with Image.open(picture) as image:
            image.convert("RGB").resize((800, round(800 * image.height / image.width))).save(
                picture.with_suffix(".jpg"), quality=80
            )
        picture.unlink()
        print(f"{system.id}: ok")
    return status


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
