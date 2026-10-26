---
version: alpha
name: Office polish
description: "Cool off-white page, white cards with a hairline border and one soft shadow, one orange accent, tinted status chips with an inner ring, Inter: calm, finished back-office screens."
dials:
  density: 5
  variance: 2
  motion: 4
colors:
  primary: "#A34C00"
  neutral: "#F7F8FA"
  surface: "#FFFFFF"
  ink: "#1C1C1E"
  muted: "#5F6672"
  border: "#E5E7EB"
  brand: "#FF7A00"
  ok: "#17693D"
  warn: "#8A5200"
  error: "#B42318"
  info: "#0A6FD6"
typography:
  display:
    fontFamily: "Inter"
    fontSize: 40px
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
  sm: 8px
  md: 12px
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
    backgroundColor: "#8B4100"
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

# Office polish

## Overview
An office tool people use all day: quiet, regular and finished. One orange accent marks the main action, the active menu item and the counts; everything else is neutral. Every coloured label is built the same way, every card the same way, so the whole app reads as one system.
Dials: VISUAL_DENSITY 5, DESIGN_VARIANCE 2, MOTION_INTENSITY 4 (1-10). Use for: back office, admin, crm, case management, government, operations, erp.

## Colors
Orange is the only accent. The filled controls use the deeper orange (primary) so white text passes contrast; the bright orange (brand) is for the active-item bar, tab underline, progress, focus ring and icon chips, never for text on white.

## Typography
Inter for display and headings, Inter for text. Numbers in tables use tabular figures.

## Layout
Container 1180px, breakpoints 375 / 768 / 1280, spacing scale 4-8-16-32-64, one left edge per column.

## Shapes
Corners 8px and 12px, buttons are pills.

## Do's and Don'ts
- One accent: orange marks the main action, the active menu item and the counts; everything else stays neutral
- Every coloured label is built the same way: a pale tint of the colour, darker text of the same hue and a thin inner ring
- Cards are white on the off-white page with a 1px border and one soft shadow; a clickable card lifts 2px on hover
- Icons come from one family; alone (stat tiles, page headers, empty states) they sit in a soft tinted rounded square
- Hierarchy comes from weight and grey, not many sizes: labels 11px uppercase and spaced, titles 24px bold with tight tracking
- Motion is 200 to 300 ms: fade and rise on mount, lift on hover, a 98% press, a slide for drawers; nothing bounces
- Status is colour plus words, never colour alone; an overdue row carries a red bar on its left edge
- Money and dates use the reader's convention (lakh and crore, 30 Sep 2026); numbers use tabular figures

## Responsive Behavior
Grids collapse to one column at 768px, navigation to a menu, tables to cards; touch targets are at least 44px.

## Known Gaps
- Inter has no Bengali or other Indic letters: for such content name a fallback face (Tiro Bangla for Bengali) with find_font. White text on the bright orange #FF7A00 is only 2.6 to 1, so filled controls use the deeper orange.
- Derived from the design philosophy of a user-owned back-office app (D-489); adapt every value to the product before building.
