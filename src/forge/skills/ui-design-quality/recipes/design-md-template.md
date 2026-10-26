# DESIGN.md template (write one in the project root BEFORE building any UI, then build to it)

A DESIGN.md is the project's design system: the single source of truth for every colour, size and component, so a page built today and a
page added next month look like one product. It uses the open DESIGN.md format (Google Labs, Apache-2.0): **YAML tokens** between `---`
lines, then **prose sections** that say why. Tokens are exact values (hex, px, font names); prose is the reasoning a reviewer can check.
`design_md_lint` checks the file (references, units, contrast, section order); `design_md_export` turns the tokens into a CSS theme so
the code uses them instead of retyping them. The design critic checks the built pages against it. If the user (or their company) supplies a
DESIGN.md or brand guide, it is binding: build to it and do not invent your own.

Copy the file below and replace every value with a decision that comes from this product. Remove a token group only by listing it under
`omitted` with a reason. A component variant (hover, pressed, disabled) is a separate entry.

```markdown
---
version: alpha
name: <Product> design system
composition: lay-editorial-split   # the layout recipe this design is built on (find_asset type section, tag composition)
dials:                      # 1-10: how dense, how adventurous, how animated
  density: 5
  variance: 5
  motion: 3
description: "One line: who it is for and what it must feel like."
colors:
  primary: "#______"        # the accent: one per screen, used for the single most important action
  secondary: "#______"
  neutral: "#______"        # the page background
  ink: "#______"            # body text; contrast on neutral >= 4.5:1
  muted: "#______"          # secondary text; also >= 4.5:1 on neutral
  surface: "#______"        # cards and panels
  border: "#______"
  ok: "#______"             # success only
  warn: "#______"
  error: "#______"
typography:
  display:
    fontFamily: <Display font>
    fontSize: 56px
    fontWeight: 700
    lineHeight: 1.05
    letterSpacing: -0.02em
  h2:
    fontFamily: <Display font>
    fontSize: 32px
    fontWeight: 600
    lineHeight: 1.2
  body-md:
    fontFamily: <Body font>
    fontSize: 16px
    fontWeight: 400
    lineHeight: 1.6
  body-tabular:             # numbers in tables and prices
    fontFamily: <Body font>
    fontSize: 14px
    fontWeight: 400
    lineHeight: 1.5
    fontFeature: "tnum"
rounded:
  sm: 6px
  md: 12px
  pill: 9999px
spacing:
  xs: 4px
  sm: 8px
  md: 16px
  lg: 32px
  xl: 64px
components:
  button-primary:
    backgroundColor: "{colors.primary}"
    textColor: "{colors.neutral}"
    typography: "{typography.body-md}"
    rounded: "{rounded.pill}"
    padding: 12px
  button-primary-hover:
    backgroundColor: "#______"
    textColor: "{colors.neutral}"
  card:
    backgroundColor: "{colors.surface}"
    textColor: "{colors.ink}"
    rounded: "{rounded.md}"
    padding: 24px
  input:
    backgroundColor: "{colors.neutral}"
    textColor: "{colors.ink}"
    rounded: "{rounded.sm}"
    padding: 12px
---

# <Product> design system

## Concept
For a brand page (landing page, portfolio, marketing site); an application screen leaves it out. Written before everything else; the gates read these two lines.
Idea: one sentence on what this page is about, taken from the subject's own world (a studio above a river at first light; a bakery that starts at 4 am). Not a style word.
Signature visual: the one picture that carries the hero: what it shows, how it is made (a drawn SVG scene, a licensed photograph found with find_image, a product shot) and how large it is (the whole hero, half of it). It belongs to this product and no other.
Why not generic: what the obvious version would be (a headline, a card, three columns of text) and what this page does instead.

## Experience
Written first, before any token. Who it is for and the context they arrive in (for an application: the people, what each must get done, in how many steps, and what must never go wrong). The feeling in three or four words and what it must NOT feel like. The reaction wanted, in the visitor's words ("This bakery looks special. I want to visit."). One line of creative direction ("the warmth of a neighbourhood bakery, the refinement of an editorial food magazine"). Say what you inferred from the brief.

## Story
The journey, one numbered line per section of the page: its job, its density (quiet, rich or dramatic) and the picture it needs with its source (brand folder, find_image query, generate_image). Example for a bakery: 1. Desire: the loaf and one promise, rich, large photograph of the bread. 2. Trust: hours, place, delivery, quiet, no picture. 3. Exploration: what is sold, rich, three product photographs. 4. Craft: the hands and the process, dramatic, a dark band with a photograph of the baker. 5. Invitation: the shop and one visit action, quiet, a photograph of the shop front. Neighbouring sections differ in density; a screen holds one dramatic moment. For an application, leave this out and write the tasks under Experience.

## Overview
Who this is for, what it must make them feel, what it must NOT look like. Dials 1-10 (they gate the choices below):
DESIGN_VARIANCE (1 centred and calm ... 10 asymmetric and editorial), MOTION_INTENSITY (1 hover states only ... 10 scroll-driven),
VISUAL_DENSITY (1 spacious ... 10 dense dashboard). Chosen: N / N / N. Where the single bold move is (one hero, one colour move, one
unusual type choice) and why everything else stays calm.

## Colors
Roles, not swatches: what each colour is for and where it must never appear. One accent per screen. State the contrast of every text pair.

## Typography
Why these two fonts; the scale and where each level is used; numeric cells use tabular figures. System fallbacks. Font substitutes if a
licensed font cannot be used.

## Layout
Container width, grid, breakpoints (375 / 768 / 1280), the spacing rhythm, section padding, the hero rule (headline and primary action visible
without scrolling at 1280x800), alignment rule (one left edge).

## Elevation & Depth
How depth is shown: shadows (values for rest and lifted), borders, or flat colour contrast. Any gradient or texture and where it is allowed.

## Shapes
One radius family and where each radius is used; one border colour.

## Components
Button, input with label, hint and error, card, navigation (desktop and phone), badge, table row, modal or toast, empty state, loading
skeleton. States for each: hover, focus-visible, active, disabled, loading, success, error.

## Imagery and Icons
Where visuals come from (drawn SVG, photos, illustrations), one icon set and stroke width, avatar style. Never a grey placeholder box.

## Page Composition
The sections of each page in order, what each is for, and the layout recipe it comes from. One bullet per decision, each with its reason
("Hero is a split with a photograph on the right, because the visitor must see the studio before reading about it").

## Motion and Interaction
What moves and what stays still, durations and easing, the hover, focus, pressed and loading states, and the reduced-motion rule. Each choice with its reason.

## Accessibility
Contrast pairs, focus order and visible focus, touch targets, reading order, labels and error text. Each choice with its reason.

## Do's and Don'ts
Four to eight project-specific rules a reviewer could check by looking at the page, for example "never more than one accent colour per
section", "buttons are always pills", "numbers always use tabular figures".

## Responsive Behavior
What collapses when (nav to menu, grids to one column, tables to cards), touch targets >= 44px, no sideways scroll.

## Known Gaps
What this file could not decide or could not match (a font that needs a licence, an image that was not available). Honest gaps are better
than invented values.
```

The order of the first eight headings follows the format (Overview, Colors, Typography, Layout, Elevation & Depth, Shapes, Components,
Do's and Don'ts); Imagery, Page Composition, Motion and Interaction, Accessibility, Responsive Behavior and Known Gaps are allowed extras (`design_md_lint` notes a missing one and any list of decisions that gives no reason). Section 'Do's and Don'ts' is where the product's
personality lives.
