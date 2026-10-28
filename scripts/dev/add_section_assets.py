"""Write catalogue asset files for new page sections (TODO L1, D-511).

    python scripts/dev/add_section_assets.py

The table below is the source for the asset files of the sections added in batch 1 (assets/section/sec-*.md). An existing file is left alone, so the
script can be rerun. Afterwards: python scripts/dev/make_section_previews.py <names>, then python scripts/build_asset_catalogue.py."""

from __future__ import annotations

import re
from pathlib import Path

SKILL = Path(__file__).resolve().parents[2] / "src" / "forge" / "skills" / "ui-design-quality"

# name: (title, summary, moods, products, tags, density, how to use)
SECTIONS: dict[str, tuple[str, str, str, str, str, str, str]] = {
    "HeroStacked": (
        "Stacked hero",
        "A left-aligned headline and one line of text, then a full-width picture band that breaks out of the text column.",
        "calm, warm, confident",
        "bakery, venue, restaurant, product, travel, studio",
        "hero, picture-led, full bleed",
        "airy",
        "Pass your own picture as children (a wide crop, about 3:1 on desktop); the drawn band is a stand-in. Choose it when the picture carries the page.",
    ),
    "HeroNumbers": (
        "Numbers hero",
        "The headline on the left and three large figures on the right, each with a label, between hairlines.",
        "precise, trustworthy, serious",
        "clinic, report, fintech, nonprofit, research, service",
        "hero, figures, proof",
        "balanced",
        "`figures` is a list of value and label; use real, specific numbers (the audit flags placeholder text). Choose it when the claim can be proven with numbers.",
    ),
    "HeroSignup": (
        "Sign-up hero",
        "A centred headline, one sentence and an inline e-mail field with a button; the single action happens in the first view.",
        "focused, modern, plain",
        "waiting list, newsletter, saas, launch, app",
        "hero, form, e-mail, validation",
        "airy",
        "A real labelled input that validates on submit; `onSubmit(email)` receives the address. Choose it for a pre-launch or waiting-list page with one goal.",
    ),
    "HeroPoster": (
        "Poster hero",
        "Giant uppercase type on a solid brand-colour field, edge to edge, with a thin information bar and one button under it.",
        "loud, bold, energetic",
        "event, festival, launch, campaign, conference, sale",
        "hero, poster, big type",
        "airy",
        "`title` is one to three short lines; `details` fills the bar (when, where, price). White text on the brand colour: the token files keep the contrast. Choose it for events and campaigns, not for a quiet product.",
    ),
    "FeaturesNumbered": (
        "Numbered features",
        "A short intro that stays in view on the left and a long column of numbered points on the right, each with a large numeral.",
        "editorial, ordered, calm",
        "method, process, principles, agency, consultancy, course",
        "features, numbered, sticky, list",
        "airy",
        "`items` is a list of title and text (four to eight). The intro is sticky on desktop and stacks on a phone. Choose it for a method that is read in order.",
    ),
    "FeaturesComparison": (
        "Before and after",
        "Two columns of short lines, the old way struck through in grey and the new way in full colour with a tick.",
        "clear, persuasive, plain",
        "saas, service, booking, migration, upgrade, tool",
        "features, comparison, before after",
        "balanced",
        "`before` and `after` each have a heading and three to six lines of the same length. Choose it where the benefit is a contrast (a week against an hour).",
    ),
    "FeaturesTabs": (
        "Tabbed features",
        "A row of tabs with one panel of text under it; arrow keys, Home and End move between the tabs and the selected one is announced.",
        "organised, practical, clean",
        "studio, school, product, services, platform",
        "features, tabs, accessible, interactive",
        "balanced",
        "`tabs` is a list of label, title, text and optional points (three to five). Choose it when several features need a paragraph each and one place.",
    ),
    "NewsletterBand": (
        "Newsletter band",
        "A slim full-width band with one sentence on the left and an inline e-mail field on the right; sits above a footer.",
        "light, friendly, plain",
        "newsletter, blog, shop, studio, community",
        "form, e-mail, band, validation",
        "balanced",
        "A real labelled input that validates on submit; `onSubmit(email)` receives the address. Put it between the last section and the footer.",
    ),
    "ContactSplit": (
        "Contact split",
        "Address, hours, phone and e-mail as a list on the left and a validated message form on the right.",
        "practical, open, warm",
        "shop, studio, clinic, restaurant, school, local business",
        "form, contact, location, validation",
        "balanced",
        "`details` is a list of label and value. The form checks the name, the e-mail and a message of at least ten characters, and shows a thank-you. Use it when people also need to find the place; `ContactForm` is the form on its own.",
    ),
    "HeroSearch": (
        "Search hero",
        "A headline and one large search field with a button, and a line of popular searches under it that fill the field.",
        "practical, open, helpful",
        "directory, catalogue, listings, help centre, marketplace",
        "hero, search, form",
        "airy",
        "`onSearch(query)` receives the query; `popular` is a list of terms. A labelled search input in a form with role search. Choose it where the first thing a visitor does is look for something.",
    ),
    "FeaturesIconRow": (
        "Icon row",
        "Three or four features side by side, each with a small line icon, a title and two sentences, divided by hairlines and not boxed.",
        "friendly, clear, light",
        "service, trades, saas, clinic, shop, local business",
        "features, icons, row, inline svg",
        "balanced",
        "The four line icons are drawn inline (nothing to install); pass your own `icon` node per item to change one. Choose it for short, parallel reasons to choose you.",
    ),
    "TestimonialColumns": (
        "Testimonial columns",
        "Three short quotes side by side as plain text between hairlines, with the name and role under each; no boxes, no stars.",
        "warm, human, quiet",
        "school, clinic, service, studio, shop, nonprofit",
        "testimonial, quotes, columns, social proof",
        "balanced",
        "`items` is a list of text, name and role; use real quotes with one concrete detail each. Pairs with `TestimonialFeature` (one long quote).",
    ),
    "TeamRoster": (
        "Team roster",
        "People as rows between hairlines: a badge or photo, name and role, a one-line note and a contact link.",
        "calm, trustworthy, plain",
        "studio, practice, agency, clinic, firm, school",
        "team, people, list, about",
        "balanced",
        "`people` is a list of name, role, note, optional href and photo (a letter badge shows when there is no photo). Quieter and faster to scan than a grid of portrait cards.",
    ),
    "TimelineVertical": (
        "Vertical timeline",
        "Dated entries down the page along a thin line, the year large on the left and the event on the right.",
        "story, warm, steady",
        "history, roadmap, programme, about, company, nonprofit",
        "timeline, history, dates, vertical",
        "airy",
        "`items` is a list of when, title and text (four to eight). Order it newest first or last as the story needs.",
    ),
    "PricingTable": (
        "Pricing table",
        "Plans as columns of one real table, features as rows with ticks and rules, the price and a button in the header.",
        "precise, businesslike, clear",
        "saas, subscription, software, platform, membership",
        "pricing, table, comparison, plans",
        "dense",
        "`plans` and `features` (a label and one value per plan: true, false or text). Use it when plans differ in many small ways; `PricingTiers` suits two or three plans that differ in a few. It scrolls sideways inside its own box on a phone.",
    ),
}


def kebab(name: str) -> str:
    return re.sub(r"(?<!^)(?=[A-Z])", "-", name).lower()


def main() -> None:
    made = 0
    for name, (title, summary, moods, products, tags, density, usage) in SECTIONS.items():
        asset_id = f"sec-{kebab(name)}"
        path = SKILL / "assets" / "section" / f"{asset_id}.md"
        if path.exists():
            continue
        text = (
            f'---\nid: {asset_id}\ntype: section\ntitle: {title}\nsummary: "{summary}"\nmoods: [{moods}]\nproducts: [{products}]\n'
            f"tags: [react, tailwind v4, tokens only, {tags}]\ndensity: {density}\ndependencies: []\nlicence: original\n"
            f'source: "authored for DebCraft (section library, D-511)"\n'
            f'tested: "built with Vite + Tailwind v4, type-checked (tsc strict), audit clean at 1280 and 375 px, screenshot looked at (tests/test_sections.py, D-511)"\n'
            f"files:\n  - from: recipes/sections/{name}.tsx\n    to: src/sections/{name}.tsx\n---\n\n## {title}\n\n"
            f"Component `{name}` in `src/sections/{name}.tsx`. Every prop has a default (example content): pass your own words and links. {usage} "
            "It uses only the theme token classes of `index.css` (brand-*, ink-*, btn-primary, btn-secondary, eyebrow, field, font-display), so changing the tokens "
            "restyles it. Needs the `index.css` token file (the `tpl-landing-*` templates ship one, or copy `recipes/index.css`).\n\n"
            "Rules: replace the example copy completely (the audit flags placeholder text), keep one primary button per view and check the page at 375 px.\n"
        )
        path.write_text(text, encoding="utf-8", newline="\n")
        made += 1
    print(f"{made} section asset files written")


if __name__ == "__main__":
    main()
