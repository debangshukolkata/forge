---
version: alpha
name: SaaS (template palette)
description: "The palette and type of the SaaS landing template: cool slate, one indigo accent, Plus Jakarta Sans."
dials:
  density: 5
  variance: 5
  motion: 4
colors:
  primary: "#4F46E5"
  neutral: "#F8FAFC"
  surface: "#FFFFFF"
  ink: "#0F172A"
  muted: "#5B6B82"
  border: "#E2E8F0"
  ok: "#15803D"
  warn: "#B45309"
  error: "#B91C1C"
typography:
  display:
    fontFamily: "Plus Jakarta Sans"
    fontSize: 56px
    fontWeight: 700
    lineHeight: 1.05
    letterSpacing: -0.02em
  h2:
    fontFamily: "Plus Jakarta Sans"
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
  md: 14px
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
    backgroundColor: "#433CC3"
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

# SaaS (template palette)

## Overview
A product page that explains one thing well and then shows it.
Dials: VISUAL_DENSITY 5, DESIGN_VARIANCE 5, MOTION_INTENSITY 4 (1-10). Use for: saas, b2b, developer tools, fintech.

## Colors
Indigo accent on cool slate; ink is navy-black.

## Typography
Plus Jakarta Sans for display and headings, Inter for text. Numbers in tables use tabular figures.

## Layout
Container 1180px, breakpoints 375 / 768 / 1280, spacing scale 4-8-16-32-64, one left edge per column.

## Shapes
Corners 8px and 14px, buttons are pills.

## Do's and Don'ts
- Hero headline states the outcome
- One highlighted plan
- Logos in a muted row
- Numbers use tabular figures

## Responsive Behavior
Grids collapse to one column at 768px, navigation to a menu, tables to cards; touch targets are at least 44px.

## Known Gaps
- Fonts are named, not bundled: load them with find_font or fall back to the system stack.
- Derived from the SaaS template (recipes/templates/saas); adapt every value to the product before building.
