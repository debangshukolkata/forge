---
version: alpha
name: Charity and community (template palette)
description: "The palette and type of the charity landing template: warm paper, ink and one brave red."
dials:
  density: 4
  variance: 5
  motion: 4
colors:
  primary: "#C62828"
  neutral: "#FAF8F6"
  surface: "#FFFFFF"
  ink: "#1D1A17"
  muted: "#6B625A"
  border: "#E7E1DB"
  ok: "#15803D"
  warn: "#B45309"
  error: "#B91C1C"
typography:
  display:
    fontFamily: "Fraunces"
    fontSize: 56px
    fontWeight: 600
    lineHeight: 1.05
    letterSpacing: -0.02em
  h2:
    fontFamily: "Fraunces"
    fontSize: 32px
    fontWeight: 600
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
  sm: 12px
  md: 20px
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
    textColor: "#FFFFFF"
    typography: "{typography.body-md}"
    rounded: "{rounded.pill}"
    padding: 12px
  button-primary-hover:
    backgroundColor: "#A82222"
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

# Charity and community (template palette)

## Overview
Warm, editorial and urgent without shouting: a drive or a cause with a face on it.
Dials: VISUAL_DENSITY 4, DESIGN_VARIANCE 5, MOTION_INTENSITY 4 (1-10). Use for: charity, health, community, events, education.

## Colors
Brave red for action on warm paper; green and amber only for status.

## Typography
Fraunces for display and headings, Inter for text. Numbers in tables use tabular figures.

## Layout
Container 1180px, breakpoints 375 / 768 / 1280, spacing scale 4-8-16-32-64, one left edge per column.

## Shapes
Corners 12px and 20px, buttons are pills.

## Do's and Don'ts
- One red action per screen
- Serif headlines, Inter body
- Real photographs of people, never stock smiles
- Stats in large serif numerals

## Responsive Behavior
Grids collapse to one column at 768px, navigation to a menu, tables to cards; touch targets are at least 44px.

## Known Gaps
- Fonts are named, not bundled: load them with find_font or fall back to the system stack.
- Derived from the charity template (recipes/templates/charity); adapt every value to the product before building.
