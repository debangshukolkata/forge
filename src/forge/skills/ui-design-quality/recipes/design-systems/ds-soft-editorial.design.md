---
version: alpha
name: Soft editorial
description: "Warm off-white, a serif display, generous whitespace and soft shadows: humane and trustworthy."
dials:
  density: 3
  variance: 5
  motion: 3
colors:
  primary: "#9F1D20"
  neutral: "#FAF8F6"
  surface: "#FFFFFF"
  ink: "#1D1A17"
  muted: "#6B625A"
  border: "#E7E1DB"
typography:
  display:
    fontFamily: "Fraunces"
    fontSize: 56px
    fontWeight: 600
    lineHeight: 1.05
    letterSpacing: -0.01em
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
    backgroundColor: "#87191B"
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

# Soft editorial

## Overview
A humane, unhurried look for places people come to for care or learning. It must feel like a well-set magazine page, not a SaaS dashboard.
Dials: VISUAL_DENSITY 3, DESIGN_VARIANCE 5, MOTION_INTENSITY 3 (1-10). Use for: health, charity, education, boutique.

## Colors
One deep red accent for the single action on a screen; everything else is warm ink and paper. No second accent.

## Typography
Fraunces for display and headings, Inter for text. Numbers in tables use tabular figures.

## Layout
Container 1180px, breakpoints 375 / 768 / 1280, spacing scale 4-8-16-32-64, one left edge per column.

## Shapes
Corners 12px and 20px, buttons are pills.

## Do's and Don'ts
- Use the accent only for the one primary action per screen
- Set headlines in the serif and everything else in Inter
- Leave at least 64px between sections
- Never use a cool grey; neutrals are warm

## Responsive Behavior
Grids collapse to one column at 768px, navigation to a menu, tables to cards; touch targets are at least 44px.

## Known Gaps
- Fonts are named, not bundled: load them with find_font or fall back to the system stack.
- Derived from dir-soft-editorial; adapt every value to the product before building.
