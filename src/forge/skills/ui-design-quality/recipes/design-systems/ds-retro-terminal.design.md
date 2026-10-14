---
version: alpha
name: Retro terminal
description: "Monospace type, 1px borders and phosphor green on black: for developer tools and nostalgia."
dials:
  density: 6
  variance: 2
  motion: 3
colors:
  primary: "#33FF66"
  neutral: "#0A0F0A"
  surface: "#101810"
  ink: "#B6F2B6"
  muted: "#7BD389"
  border: "#1F3A1F"
  secondary: "#FFB000"
typography:
  display:
    fontFamily: "JetBrains Mono"
    fontSize: 40px
    fontWeight: 700
    lineHeight: 1.05
    letterSpacing: 0em
  h2:
    fontFamily: "JetBrains Mono"
    fontSize: 32px
    fontWeight: 700
    lineHeight: 1.2
  body-md:
    fontFamily: "JetBrains Mono"
    fontSize: 16px
    fontWeight: 400
    lineHeight: 1.6
  body-tabular:
    fontFamily: "JetBrains Mono"
    fontSize: 14px
    fontWeight: 400
    lineHeight: 1.5
    fontFeature: "tnum"
rounded:
  sm: 0px
  md: 2px
spacing:
  xs: 4px
  sm: 8px
  md: 16px
  lg: 32px
  xl: 64px
components:
  button-primary:
    backgroundColor: "{colors.primary}"
    textColor: "#0A0F0A"
    typography: "{typography.body-md}"
    rounded: "{rounded.md}"
    padding: 12px
  button-primary-hover:
    backgroundColor: "#52FF7D"
    textColor: "#0A0F0A"
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

# Retro terminal

## Overview
A screen that looks like it runs on a CRT, with the contrast kept high so it stays readable.
Dials: VISUAL_DENSITY 6, DESIGN_VARIANCE 2, MOTION_INTENSITY 3 (1-10). Use for: developer tools, games.

## Colors
Phosphor green on black, with amber as the only other colour.

## Typography
JetBrains Mono for display and headings, JetBrains Mono for text. Numbers in tables use tabular figures.

## Layout
Container 1180px, breakpoints 375 / 768 / 1280, spacing scale 4-8-16-32-64, one left edge per column.

## Shapes
Corners 0px and 2px.

## Do's and Don'ts
- Monospace everywhere
- 1px borders and ASCII dividers
- A blinking caret, never more than one animation
- Keep contrast above 7:1

## Responsive Behavior
Grids collapse to one column at 768px, navigation to a menu, tables to cards; touch targets are at least 44px.

## Known Gaps
- Fonts are named, not bundled: load them with find_font or fall back to the system stack.
- Derived from dir-retro-terminal; adapt every value to the product before building.
