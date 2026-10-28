---
id: fx-in-fade
type: effect
title: "Entrance: fade"
summary: "Fade an element in on page load; `--i` staggers siblings by 80 ms."
moods: [calm, polished]
products: [landing, hero, any page]
tags: [animation, motion, entrance]
density: any
dependencies: []
licence: original
source: authored for DebCraft (motion kit part 2, D-269)
tested: "demo page in Edge: the class animates or transitions as described, no console errors, switched off under reduced motion (tests/test_motion_more.py, D-269)"
files:
  - from: recipes/motion-more.css
    to: src/motion-more.css
preview: assets/preview/fx-in-fade.jpg
---

## Entrance: fade

`class="in-fade"` and optionally `style="--i:2"`. 0.7 s. The safest entrance; use it for most content.

Import the stylesheet once in main.tsx after index.css: `import "./motion-more.css"`. Budget: count it against the MOTION_INTENSITY dial (hover and focus effects are free); everything stops under `prefers-reduced-motion`.
