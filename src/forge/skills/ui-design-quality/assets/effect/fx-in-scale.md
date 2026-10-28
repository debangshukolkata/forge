---
id: fx-in-scale
type: effect
title: "Entrance: scale up"
summary: "Elements grow slightly from 92 % while fading in."
moods: [friendly, polished]
products: [cards, modals, pricing]
tags: [animation, motion, entrance]
density: any
dependencies: []
licence: original
source: authored for DebCraft (motion kit part 2, D-269)
tested: "demo page in Edge: the class animates or transitions as described, no console errors, switched off under reduced motion (tests/test_motion_more.py, D-269)"
files:
  - from: recipes/motion-more.css
    to: src/motion-more.css
preview: assets/preview/fx-in-scale.jpg
---

## Entrance: scale up

`class="in-scale"`; good for cards and dialogs. Keep the scale subtle.

Import the stylesheet once in main.tsx after index.css: `import "./motion-more.css"`. Budget: count it against the MOTION_INTENSITY dial (hover and focus effects are free); everything stops under `prefers-reduced-motion`.
