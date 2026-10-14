---
version: alpha
name: Bold campaign poster
description: "Near-black, one hot colour, huge grotesk type and hard offset shadows: loud and urgent."
composition: lay-poster-hero
dials:
  density: 6
  variance: 9
  motion: 7
colors:
  primary: "#E11D48"
  neutral: "#0B0B0C"
  surface: "#18181B"
  ink: "#FFFFFF"
  muted: "#D4D4D8"
  border: "#3F3F46"
typography:
  display:
    fontFamily: "Space Grotesk"
    fontSize: 96px
    fontWeight: 800
    lineHeight: 1.05
    letterSpacing: -0.04em
  h2:
    fontFamily: "Space Grotesk"
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
  sm: 0px
  md: 4px
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
    backgroundColor: "#BF193D"
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

# Bold campaign poster

## Overview
A poster that happens to be a website: one message, shouted, with a countdown or a number as the hero.
Dials: VISUAL_DENSITY 6, DESIGN_VARIANCE 9, MOTION_INTENSITY 7 (1-10). Use for: events, drives, launches, sport.

## Colors
Near-black with one hot red; white type. A second hot colour (yellow) may appear once, as a sticker.

## Typography
Space Grotesk for display and headings, Inter for text. Numbers in tables use tabular figures.

## Layout
Container 1180px, breakpoints 375 / 768 / 1280, spacing scale 4-8-16-32-64, one left edge per column.

## Shapes
Corners 0px and 4px.

## Do's and Don'ts
- Headlines are 72-140px, tight tracking, uppercase labels
- Corners are sharp or one big radius, borders 2-3px
- Hard offset shadows only
- One hero number or countdown

## Responsive Behavior
Grids collapse to one column at 768px, navigation to a menu, tables to cards; touch targets are at least 44px.

## Known Gaps
- Fonts are named, not bundled: load them with find_font or fall back to the system stack.
- Derived from dir-bold-poster; adapt every value to the product before building.
