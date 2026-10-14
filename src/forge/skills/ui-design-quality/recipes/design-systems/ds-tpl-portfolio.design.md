---
version: alpha
name: Portfolio (template palette)
description: "The palette and type of the portfolio template: white, stone and ink with a Playfair display."
dials:
  density: 3
  variance: 6
  motion: 2
colors:
  primary: "#1C1917"
  neutral: "#FFFFFF"
  surface: "#F5F5F4"
  ink: "#1C1917"
  muted: "#6B6560"
  border: "#E7E5E4"
  ok: "#15803D"
  warn: "#B45309"
  error: "#B91C1C"
typography:
  display:
    fontFamily: "Playfair Display"
    fontSize: 56px
    fontWeight: 500
    lineHeight: 1.05
    letterSpacing: -0.02em
  h2:
    fontFamily: "Playfair Display"
    fontSize: 32px
    fontWeight: 500
    lineHeight: 1.2
  body-md:
    fontFamily: "DM Sans"
    fontSize: 16px
    fontWeight: 400
    lineHeight: 1.6
  body-tabular:
    fontFamily: "DM Sans"
    fontSize: 14px
    fontWeight: 400
    lineHeight: 1.5
    fontFeature: "tnum"
rounded:
  sm: 4px
  md: 8px
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
    backgroundColor: "#181514"
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

# Portfolio (template palette)

## Overview
The work is the design. Type and spacing carry the personality; colour stays out of the way.
Dials: VISUAL_DENSITY 3, DESIGN_VARIANCE 6, MOTION_INTENSITY 2 (1-10). Use for: portfolio, studio, photography, writing.

## Colors
Ink on white and stone; the accent is the ink itself.

## Typography
Playfair Display for display and headings, DM Sans for text. Numbers in tables use tabular figures.

## Layout
Container 1180px, breakpoints 375 / 768 / 1280, spacing scale 4-8-16-32-64, one left edge per column.

## Shapes
Corners 4px and 8px.

## Do's and Don'ts
- Let images run large
- Playfair for titles, DM Sans for text
- Project metadata in small caps
- No decoration

## Responsive Behavior
Grids collapse to one column at 768px, navigation to a menu, tables to cards; touch targets are at least 44px.

## Known Gaps
- Fonts are named, not bundled: load them with find_font or fall back to the system stack.
- Derived from the portfolio template (recipes/templates/portfolio); adapt every value to the product before building.
