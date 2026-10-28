---
id: fx-hover-glow
type: effect
title: Hover glow ring
summary: A soft brand-coloured ring and glow appear on hover or focus.
moods: [modern, friendly]
products: [buttons, cards, inputs]
tags: [animation, motion, hover]
density: any
dependencies: []
licence: original
source: authored for DebCraft (motion kit part 2, D-269)
tested: "demo page in Edge: the class animates or transitions as described, no console errors, switched off under reduced motion (tests/test_motion_more.py, D-269)"
files:
  - from: recipes/motion-more.css
    to: src/motion-more.css
preview: assets/preview/fx-hover-glow.jpg
---

## Hover glow ring

`class="hover-glow"`; it also shows on keyboard focus, so keep it as the visible focus style.

Import the stylesheet once in main.tsx after index.css: `import "./motion-more.css"`. Budget: count it against the MOTION_INTENSITY dial (hover and focus effects are free); everything stops under `prefers-reduced-motion`.
