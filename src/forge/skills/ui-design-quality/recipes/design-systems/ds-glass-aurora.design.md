---
version: alpha
name: Glass and aurora
description: "A dark base, frosted glass panels and a sparing indigo-to-cyan glow: modern AI and developer tools."
dials:
  density: 5
  variance: 6
  motion: 6
colors:
  primary: "#9D8CFF"
  neutral: "#0A0B10"
  surface: "#14161F"
  ink: "#F4F4F8"
  muted: "#A5A8B8"
  border: "#2A2D3A"
  secondary: "#22D3EE"
typography:
  display:
    fontFamily: "Geist"
    fontSize: 56px
    fontWeight: 300
    lineHeight: 1.05
    letterSpacing: -0.03em
  h2:
    fontFamily: "Geist"
    fontSize: 32px
    fontWeight: 300
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
spacing:
  xs: 4px
  sm: 8px
  md: 16px
  lg: 32px
  xl: 64px
components:
  button-primary:
    backgroundColor: "{colors.primary}"
    textColor: "#0A0B10"
    typography: "{typography.body-md}"
    rounded: "{rounded.md}"
    padding: 12px
  button-primary-hover:
    backgroundColor: "#AC9DFF"
    textColor: "#0A0B10"
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

# Glass and aurora

## Overview
A product that feels like light behind glass. The glow is a seasoning, never the meal.
Dials: VISUAL_DENSITY 5, DESIGN_VARIANCE 6, MOTION_INTENSITY 6 (1-10). Use for: saas, ai, developer tools.

## Colors
Violet accent with a cyan highlight used once; glass panels are translucent white over the dark base.

## Typography
Geist for display and headings, Inter for text. Numbers in tables use tabular figures.

## Layout
Container 1180px, breakpoints 375 / 768 / 1280, spacing scale 4-8-16-32-64, one left edge per column.

## Shapes
Corners 12px and 20px.

## Do's and Don'ts
- Glow appears once per screen
- Panels use a 1px light border and blur 16-24px
- Light weights for display type
- Never put body text on the glow

## Responsive Behavior
Grids collapse to one column at 768px, navigation to a menu, tables to cards; touch targets are at least 44px.

## Known Gaps
- Fonts are named, not bundled: load them with find_font or fall back to the system stack.
- Derived from dir-glass-aurora; adapt every value to the product before building.
