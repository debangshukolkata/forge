# DESIGN.md template (write one in the project root BEFORE building any UI, then build to it)

A DESIGN.md is the project's design system in plain text: the single source of truth for every colour, size and
component, so a page built today and a page added next month look like one product. Keep it to about one page of
decisions, with exact values (hex, px, font names). The design critic checks the built pages against it. If the
user (or their company) supplies a DESIGN.md, it is binding: build to it and do not invent your own.

Copy the headings below and fill every section with specific values.

```markdown
# <Product> design system

## 1. Design read and dials
One line: who this is for, what it must make them feel, what it must NOT look like.
Dials 1-10 (they gate the choices below):
- DESIGN_VARIANCE: 1 centred and calm ... 10 asymmetric and editorial.   Chosen: N
- MOTION_INTENSITY: 1 hover states only ... 10 scroll-driven.             Chosen: N
- VISUAL_DENSITY: 1 spacious ... 10 dense dashboard.                      Chosen: N

## 2. Colour (roles, not just swatches)
accent #______ (hover #______, tint #______) | surface #______ / #______ | text #______ / #______ (muted) |
border #______ | ok #______ | warn #______ | error #______. One accent per page. Contrast of every text pair >= 4.5:1.

## 3. Typography
Display font + body font (with system fallbacks). Scale: 12/14/16/18/20/24/30/36/48/60. Body size and line-height,
heading line-height and tracking, weights used (for example 400/600/700), numeric cells use tabular figures.

## 4. Layout and spacing
Container width, grid and breakpoints (375 / 768 / 1280), spacing scale (4,8,12,16,24,32,48,64,96), section padding,
the hero rule (headline and primary action visible without scrolling at 1280x800).

## 5. Shape and depth
One radius family (for example 8 / 16 / pill), one border colour, the shadow values for rest and lifted states,
any gradient or texture and where it is allowed.

## 6. Components (each with padding, states and an example class list)
Button primary / secondary / ghost; input with label, hint, error; card; nav (desktop and phone); badge; table row;
modal or toast; empty state; loading skeleton. States: hover, focus-visible, active, disabled, loading, error.

## 7. Imagery and icons
Where visuals come from (drawn SVG, photos, illustrations), one icon set and stroke width, avatar style.

## 8. Do's and don'ts
Four to eight project-specific rules, for example "never more than one accent colour per section", "buttons are
always pills", "numbers always use tabular figures", "no more than two image-and-text splits in a row".

## 9. Responsive behaviour
What collapses when (nav to menu, grids to one column, tables to cards), touch targets >= 44px, no sideways scroll.
```

Section 8 is where the product's personality lives: write rules a reviewer could check by looking at the page.
