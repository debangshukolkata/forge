---
id: fx-in-flip
type: effect
title: "Entrance: flip down"
summary: Elements tip down into place with a slight 3D rotation.
moods: [playful, modern]
products: [cards, lists]
tags: [animation, motion, entrance]
density: any
dependencies: []
licence: original
source: authored for DebCraft (motion kit part 2, D-269)
tested: "demo page in Edge: the class animates or transitions as described, no console errors, switched off under reduced motion (tests/test_motion_more.py, D-269)"
files:
  - from: recipes/motion-more.css
    to: src/motion-more.css
preview: assets/preview/fx-in-flip.jpg
---

## Entrance: flip down

`class="in-flip"`; use on one group, not on the whole page.

Import the stylesheet once in main.tsx after index.css: `import "./motion-more.css"`. Budget: count it against the MOTION_INTENSITY dial (hover and focus effects are free); everything stops under `prefers-reduced-motion`.
