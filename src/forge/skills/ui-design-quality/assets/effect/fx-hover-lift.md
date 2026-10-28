---
id: fx-hover-lift
type: effect
title: Hover lift
summary: Cards rise 4 px with a deeper shadow on hover or focus.
moods: [clean, polished]
products: [cards, pricing, features]
tags: [animation, motion, hover]
density: any
dependencies: []
licence: original
source: authored for DebCraft (motion kit part 2, D-269)
tested: "demo page in Edge: the class animates or transitions as described, no console errors, switched off under reduced motion (tests/test_motion_more.py, D-269)"
files:
  - from: recipes/motion-more.css
    to: src/motion-more.css
preview: assets/preview/fx-hover-lift.jpg
---

## Hover lift

`class="hover-lift"` on clickable cards only; also works with keyboard focus.

Import the stylesheet once in main.tsx after index.css: `import "./motion-more.css"`. Budget: count it against the MOTION_INTENSITY dial (hover and focus effects are free); everything stops under `prefers-reduced-motion`.
