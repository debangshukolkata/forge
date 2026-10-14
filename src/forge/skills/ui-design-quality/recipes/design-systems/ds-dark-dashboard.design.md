---
version: alpha
name: Dark dashboard
description: "Near-black surfaces, light text, one indigo accent and clear status colours: dense and calm."
dials:
  density: 8
  variance: 3
  motion: 2
colors:
  primary: "#818CF8"
  neutral: "#0B0D12"
  surface: "#12151C"
  ink: "#E5E7EB"
  muted: "#9CA3AF"
  border: "#1F2330"
  ok: "#34D399"
  warn: "#FBBF24"
  error: "#F87171"
typography:
  display:
    fontFamily: "Inter"
    fontSize: 40px
    fontWeight: 600
    lineHeight: 1.05
    letterSpacing: -0.02em
  h2:
    fontFamily: "Inter"
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
  sm: 6px
  md: 10px
spacing:
  xs: 4px
  sm: 8px
  md: 16px
  lg: 32px
  xl: 64px
components:
  button-primary:
    backgroundColor: "{colors.primary}"
    textColor: "#0B0D12"
    typography: "{typography.body-md}"
    rounded: "{rounded.md}"
    padding: 12px
  button-primary-hover:
    backgroundColor: "#949DF9"
    textColor: "#0B0D12"
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

# Dark dashboard

## Overview
A tool people stare at all day: dense, legible, restful. Data first, chrome second.
Dials: VISUAL_DENSITY 8, DESIGN_VARIANCE 3, MOTION_INTENSITY 2 (1-10). Use for: analytics, ops, monitoring, admin.

## Colors
Indigo accent for selection and the primary action; green, amber and red mean status and nothing else.

## Typography
Inter for display and headings, Inter for text. Numbers in tables use tabular figures.

## Layout
Container 1180px, breakpoints 375 / 768 / 1280, spacing scale 4-8-16-32-64, one left edge per column.

## Shapes
Corners 6px and 10px.

## Do's and Don'ts
- Body text is 13-14px with tabular figures
- Charts use one accent plus muted greys
- Status colours carry a label or icon too
- Sticky table headers and a 240px left nav

## Responsive Behavior
Grids collapse to one column at 768px, navigation to a menu, tables to cards; touch targets are at least 44px.

## Known Gaps
- Fonts are named, not bundled: load them with find_font or fall back to the system stack.
- Derived from dir-dark-dashboard; adapt every value to the product before building.
