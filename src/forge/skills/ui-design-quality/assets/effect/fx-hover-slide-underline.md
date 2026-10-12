---
id: fx-hover-slide-underline
type: effect
title: Sliding underline
summary: An underline slides in from the left and out to the right.
moods: [clean, editorial]
products: [navigation, links]
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

## Sliding underline

`class="hover-slide-underline"` on links; pair with a visible focus style.

Import the stylesheet once in main.tsx after index.css: `import "./motion-more.css"`. Budget: count it against the MOTION_INTENSITY dial (hover and focus effects are free); everything stops under `prefers-reduced-motion`.
