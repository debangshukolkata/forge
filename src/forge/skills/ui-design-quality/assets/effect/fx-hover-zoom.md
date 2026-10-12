---
id: fx-hover-zoom
type: effect
title: Image zoom on hover
summary: The image inside zooms slowly while the frame stays put.
moods: [editorial, warm]
products: [galleries, cards, portfolio]
tags: [animation, motion, hover]
density: any
dependencies: []
licence: original
source: authored for DebCraft (motion kit part 2, D-269)
tested: "demo page in Edge: the class animates or transitions as described, no console errors, switched off under reduced motion (tests/test_motion_more.py, D-269)"
files:
  - from: recipes/motion-more.css
    to: src/motion-more.css
---

## Image zoom on hover

`<div class="hover-zoom rounded-xl"><img ...></div>`; the wrapper clips the overflow.

Import the stylesheet once in main.tsx after index.css: `import "./motion-more.css"`. Budget: count it against the MOTION_INTENSITY dial (hover and focus effects are free); everything stops under `prefers-reduced-motion`.
