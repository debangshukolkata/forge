---
version: alpha
name: Bento and cards
description: "An unequal grid of rounded tiles, each holding one idea, in neutral tones with two tinted accents."
dials:
  density: 5
  variance: 5
  motion: 4
colors:
  primary: "#0F766E"
  neutral: "#F5F5F4"
  surface: "#FFFFFF"
  ink: "#1C1917"
  muted: "#57534E"
  border: "#E7E5E4"
  secondary: "#B45309"
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
  sm: 16px
  md: 24px
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
    backgroundColor: "#0D645E"
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

# Bento and cards

## Overview
A page of tiles: a number, a chart, a quote, a small illustration. The layout is the design.
Dials: VISUAL_DENSITY 5, DESIGN_VARIANCE 5, MOTION_INTENSITY 4 (1-10). Use for: feature overviews, personal sites, dashboard home.

## Colors
Neutral tiles with teal and amber tints; text stays on white or the neutral.

## Typography
Inter for display and headings, Inter for text. Numbers in tables use tabular figures.

## Layout
Container 1180px, breakpoints 375 / 768 / 1280, spacing scale 4-8-16-32-64, one left edge per column.

## Shapes
Corners 16px and 24px.

## Do's and Don'ts
- Tiles span 2x2, 1x2 or 1x1, never all equal
- One idea per tile
- Teal for action, amber for highlight, nothing else
- Tile padding 24px

## Responsive Behavior
Grids collapse to one column at 768px, navigation to a menu, tables to cards; touch targets are at least 44px.

## Known Gaps
- Fonts are named, not bundled: load them with find_font or fall back to the system stack.
- Derived from dir-bento; adapt every value to the product before building.
