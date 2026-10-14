---
version: alpha
name: Claymorphism
description: "Pastel fills, chunky radii and soft inner shadows that make everything look moulded: gentle and tactile."
dials:
  density: 3
  variance: 5
  motion: 6
colors:
  primary: "#7F9CFF"
  neutral: "#F3F7FF"
  surface: "#FFFFFF"
  ink: "#1F2A44"
  muted: "#4B5675"
  border: "#DCE4F7"
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
  sm: 20px
  md: 32px
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
    textColor: "#1F2A44"
    typography: "{typography.body-md}"
    rounded: "{rounded.pill}"
    padding: 12px
  button-primary-hover:
    backgroundColor: "#92ABFF"
    textColor: "#1F2A44"
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

# Claymorphism

## Overview
A toy-like, friendly surface. Use sparingly: it tires the eye on long pages.
Dials: VISUAL_DENSITY 3, DESIGN_VARIANCE 5, MOTION_INTENSITY 6 (1-10). Use for: onboarding, games, kids products.

## Colors
Pastel blue accent on a pale blue page; pink and yellow may tint cards.

## Typography
Nunito for display and headings, Nunito for text. Numbers in tables use tabular figures.

## Layout
Container 1180px, breakpoints 375 / 768 / 1280, spacing scale 4-8-16-32-64, one left edge per column.

## Shapes
Corners 20px and 32px, buttons are pills.

## Do's and Don'ts
- Radius 24-32px, no borders
- Double inner shadows for depth
- Chunky icons
- Do not use for dense or data-heavy screens

## Responsive Behavior
Grids collapse to one column at 768px, navigation to a menu, tables to cards; touch targets are at least 44px.

## Known Gaps
- Fonts are named, not bundled: load them with find_font or fall back to the system stack.
- Derived from dir-claymorphism; adapt every value to the product before building.
