---
version: alpha
name: Playful and friendly
description: "Bright, rounded and bouncy: big radii, thick-stroke icons and a rounded sans."
dials:
  density: 4
  variance: 6
  motion: 7
colors:
  primary: "#FF7A59"
  neutral: "#FFFDF7"
  surface: "#FFFFFF"
  ink: "#2B2118"
  muted: "#6B5B4B"
  border: "#F1E6D3"
  secondary: "#FFD166"
  mint: "#06D6A0"
typography:
  display:
    fontFamily: "Nunito"
    fontSize: 56px
    fontWeight: 800
    lineHeight: 1.05
    letterSpacing: -0.02em
  h2:
    fontFamily: "Nunito"
    fontSize: 32px
    fontWeight: 700
    lineHeight: 1.2
  body-md:
    fontFamily: "Nunito"
    fontSize: 16px
    fontWeight: 400
    lineHeight: 1.6
  body-tabular:
    fontFamily: "Nunito"
    fontSize: 14px
    fontWeight: 400
    lineHeight: 1.5
    fontFeature: "tnum"
rounded:
  sm: 16px
  md: 28px
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
    textColor: "#2B2118"
    typography: "{typography.body-md}"
    rounded: "{rounded.pill}"
    padding: 12px
  button-primary-hover:
    backgroundColor: "#FF8E72"
    textColor: "#2B2118"
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

# Playful and friendly

## Overview
A product people smile at. Big shapes, friendly words, nothing sharp.
Dials: VISUAL_DENSITY 4, DESIGN_VARIANCE 6, MOTION_INTENSITY 7 (1-10). Use for: kids, food, community, consumer apps.

## Colors
Coral accent with sunny yellow and mint as supporting colours on warm white.

## Typography
Nunito for display and headings, Nunito for text. Numbers in tables use tabular figures.

## Layout
Container 1180px, breakpoints 375 / 768 / 1280, spacing scale 4-8-16-32-64, one left edge per column.

## Shapes
Corners 16px and 28px, buttons are pills.

## Do's and Don'ts
- Radius 28px and pills
- Thick-stroke icons, no emoji as icons
- Bouncy easing on hover only
- Rounded sans for headings

## Responsive Behavior
Grids collapse to one column at 768px, navigation to a menu, tables to cards; touch targets are at least 44px.

## Known Gaps
- Fonts are named, not bundled: load them with find_font or fall back to the system stack.
- Derived from dir-playful-friendly; adapt every value to the product before building.
