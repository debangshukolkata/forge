---
version: alpha
name: Neo-brutalist
description: "Flat saturated colours on cream with thick black outlines and hard shadows: playful and honest."
composition: lay-notebook-grid
dials:
  density: 5
  variance: 7
  motion: 5
colors:
  primary: "#FF6B6B"
  neutral: "#FFFAF0"
  surface: "#FFFFFF"
  ink: "#111111"
  muted: "#3F3F46"
  border: "#111111"
  secondary: "#FFDE59"
  teal: "#4ECDC4"
typography:
  display:
    fontFamily: "Space Grotesk"
    fontSize: 56px
    fontWeight: 800
    lineHeight: 1.05
    letterSpacing: -0.02em
  h2:
    fontFamily: "Space Grotesk"
    fontSize: 32px
    fontWeight: 700
    lineHeight: 1.2
  body-md:
    fontFamily: "Space Mono"
    fontSize: 16px
    fontWeight: 400
    lineHeight: 1.6
  body-tabular:
    fontFamily: "Space Mono"
    fontSize: 14px
    fontWeight: 400
    lineHeight: 1.5
    fontFeature: "tnum"
rounded:
  sm: 0px
  md: 6px
spacing:
  xs: 4px
  sm: 8px
  md: 16px
  lg: 32px
  xl: 64px
components:
  button-primary:
    backgroundColor: "{colors.primary}"
    textColor: "#111111"
    typography: "{typography.body-md}"
    rounded: "{rounded.md}"
    padding: 12px
  button-primary-hover:
    backgroundColor: "#FF8181"
    textColor: "#111111"
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

# Neo-brutalist

## Overview
A product that does not take itself too seriously and is still easy to use. The grid is visible, the shadows are hard.
Dials: VISUAL_DENSITY 5, DESIGN_VARIANCE 7, MOTION_INTENSITY 5 (1-10). Use for: creative tools, indie products, playful brands.

## Colors
Flat saturated red on cream with yellow and teal as the only other colours; black outlines everywhere.

## Typography
Space Grotesk for display and headings, Space Mono for text. Numbers in tables use tabular figures.

## Layout
Container 1180px, breakpoints 375 / 768 / 1280, spacing scale 4-8-16-32-64, one left edge per column.

## Shapes
Corners 0px and 6px.

## Do's and Don'ts
- 3px black borders and 4-8px hard shadows
- No gradients and no blur
- Tilt a card at most -1.5 degrees
- Mono type for labels and numbers

## Responsive Behavior
Grids collapse to one column at 768px, navigation to a menu, tables to cards; touch targets are at least 44px.

## Known Gaps
- Fonts are named, not bundled: load them with find_font or fall back to the system stack.
- Derived from dir-neo-brutalist; adapt every value to the product before building.
