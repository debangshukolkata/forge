---
version: alpha
name: Office polish, dark
description: "Near-black blue page, raised dark cards with a hairline border, one light orange accent with dark text on filled controls, tinted status chips, Inter: the dark twin of Office polish."
dials:
  density: 5
  variance: 2
  motion: 4
colors:
  primary: "#FF9A3D"
  neutral: "#0E1116"
  surface: "#171B22"
  ink: "#E8EAEE"
  muted: "#98A2B3"
  border: "#2A303A"
  brand: "#FF9A3D"
  ok: "#4ADE80"
  warn: "#FBBF24"
  error: "#F87171"
  info: "#60A5FA"
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
    textColor: "#111111"
    typography: "{typography.body-md}"
    rounded: "{rounded.pill}"
    padding: 12px
  button-primary-hover:
    backgroundColor: "#FFA95A"
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

# Office polish, dark

## Overview
The office tool for a dark room or a long shift: the same quiet, regular system as the light version, built from its own dark tokens. Depth comes from lighter surfaces, not shadows; one light orange accent marks the main action, the active menu item and the counts.
Dials: VISUAL_DENSITY 5, DESIGN_VARIANCE 2, MOTION_INTENSITY 4 (1-10). Use for: back office, admin, crm, case management, operations, monitoring, erp.

## Colors
Light orange is the only accent and the filled controls carry dark text on it (it passes contrast). Raised surfaces are lighter than the page; status colours are the light tints of green, amber, red and blue so they read on dark.

## Typography
Inter for display and headings, Inter for text. Numbers in tables use tabular figures.

## Layout
Container 1180px, breakpoints 375 / 768 / 1280, spacing scale 4-8-16-32-64, one left edge per column.

## Shapes
Corners 8px and 12px, buttons are pills.

## Do's and Don'ts
- One accent: light orange marks the main action, the active menu item and the counts; everything else stays neutral
- Surfaces rise by lightness: page darkest, cards one step lighter, popovers and drawers one more; borders are 1px, shadows are barely there
- Every coloured label is built the same way: a dark tint of the colour, light text of the same hue and a thin inner ring
- Text is never pure white on pure black: ink is an off-white and long text uses the muted grey for secondary lines
- Filled controls carry dark text on the light orange; the focus ring is the same orange at 3px with a gap
- Motion is 200 to 300 ms: fade and rise on mount, lift on hover, a 98% press, a slide for drawers; nothing bounces
- Status is colour plus words, never colour alone; an overdue row carries a red bar on its left edge
- Charts use the same few hues at the light tints, with grid lines at the border colour

## Responsive Behavior
Grids collapse to one column at 768px, navigation to a menu, tables to cards; touch targets are at least 44px.

## Known Gaps
- Inter has no Bengali or other Indic letters: for such content name a fallback face (Tiro Bangla for Bengali) with find_font.
- Derived from the office design (D-489) as its own dark token set, not overrides of the light one (BO7); adapt every value to the product before building.
