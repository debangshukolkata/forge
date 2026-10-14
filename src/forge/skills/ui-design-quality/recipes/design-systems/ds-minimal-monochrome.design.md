---
version: alpha
name: Minimal monochrome
description: "Black, white, one grey and one accent used once per screen; large type and huge margins."
dials:
  density: 2
  variance: 3
  motion: 1
colors:
  primary: "#C2410C"
  neutral: "#FFFFFF"
  surface: "#F5F5F5"
  ink: "#0A0A0A"
  muted: "#525252"
  border: "#E5E5E5"
typography:
  display:
    fontFamily: "Newsreader"
    fontSize: 72px
    fontWeight: 400
    lineHeight: 1.05
    letterSpacing: -0.03em
  h2:
    fontFamily: "Newsreader"
    fontSize: 32px
    fontWeight: 400
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
  sm: 0px
  md: 0px
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
    backgroundColor: "#A5370A"
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

# Minimal monochrome

## Overview
Calm and exact. Minimal is not empty: it needs excellent type and real content.
Dials: VISUAL_DENSITY 2, DESIGN_VARIANCE 3, MOTION_INTENSITY 1 (1-10). Use for: portfolio, architecture, luxury.

## Colors
Black on white with one grey; the orange accent appears once per screen, as a single mark or link.

## Typography
Newsreader for display and headings, Inter for text. Numbers in tables use tabular figures.

## Layout
Container 1180px, breakpoints 375 / 768 / 1280, spacing scale 4-8-16-32-64, one left edge per column.

## Shapes
Corners 0px and 0px.

## Do's and Don'ts
- No shadows and no gradients
- Thin rules instead of boxes
- Real photography or none
- A strict grid with a visible baseline

## Responsive Behavior
Grids collapse to one column at 768px, navigation to a menu, tables to cards; touch targets are at least 44px.

## Known Gaps
- Fonts are named, not bundled: load them with find_font or fall back to the system stack.
- Derived from dir-minimal-monochrome; adapt every value to the product before building.
