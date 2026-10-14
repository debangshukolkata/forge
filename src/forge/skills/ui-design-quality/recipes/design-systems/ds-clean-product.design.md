---
version: alpha
name: Clean product
description: "White and pale blue-grey, one saturated accent, navy text, layered soft shadows: confident B2B."
dials:
  density: 5
  variance: 4
  motion: 3
colors:
  primary: "#5546FF"
  neutral: "#FFFFFF"
  surface: "#F6F9FC"
  ink: "#0A2540"
  muted: "#425466"
  border: "#E3E8EE"
typography:
  display:
    fontFamily: "Inter"
    fontSize: 56px
    fontWeight: 700
    lineHeight: 1.05
    letterSpacing: -0.02em
  h2:
    fontFamily: "Inter"
    fontSize: 32px
    fontWeight: 700
    lineHeight: 1.2
  body-md:
    fontFamily: "Inter"
    fontSize: 16px
    fontWeight: 400
    lineHeight: 1.6
  body-tabular:
    fontFamily: "Inter"
    fontSize: 14px
    fontWeight: 400
    lineHeight: 1.5
    fontFeature: "tnum"
rounded:
  sm: 8px
  md: 12px
spacing:
  xs: 4px
  sm: 8px
  md: 16px
  lg: 32px
  xl: 64px
components:
  button-primary:
    backgroundColor: "{colors.primary}"
    textColor: "#FFFFFF"
    typography: "{typography.body-md}"
    rounded: "{rounded.md}"
    padding: 12px
  button-primary-hover:
    backgroundColor: "#483CD9"
    textColor: "#FFFFFF"
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

# Clean product

## Overview
A product site that looks like the product: precise, quiet, trustworthy. Left-aligned hero with a product mockup on the right.
Dials: VISUAL_DENSITY 5, DESIGN_VARIANCE 4, MOTION_INTENSITY 3 (1-10). Use for: b2b, fintech, dashboards, saas.

## Colors
One saturated indigo accent on a white and pale blue-grey page; navy text, never black.

## Typography
Inter for display and headings, Inter for text. Numbers in tables use tabular figures.

## Layout
Container 1180px, breakpoints 375 / 768 / 1280, spacing scale 4-8-16-32-64, one left edge per column.

## Shapes
Corners 8px and 12px.

## Do's and Don'ts
- Left-align headings
- Numbers use tabular figures
- One highlighted pricing card, never two
- Shadows are layered and soft, borders are 1px

## Responsive Behavior
Grids collapse to one column at 768px, navigation to a menu, tables to cards; touch targets are at least 44px.

## Known Gaps
- Fonts are named, not bundled: load them with find_font or fall back to the system stack.
- Derived from dir-clean-product; adapt every value to the product before building.
