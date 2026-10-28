---
id: fx-in-blur
type: effect
title: "Entrance: blur to sharp"
summary: Elements come into focus from a blur.
moods: [modern, dreamy, premium]
products: [hero, saas, ai]
tags: [animation, motion, entrance]
density: any
dependencies: []
licence: original
source: authored for DebCraft (motion kit part 2, D-269)
tested: "demo page in Edge: the class animates or transitions as described, no console errors, switched off under reduced motion (tests/test_motion_more.py, D-269)"
files:
  - from: recipes/motion-more.css
    to: src/motion-more.css
preview: assets/preview/fx-in-blur.jpg
---

## Entrance: blur to sharp

`class="in-blur"`; use on headings and hero visuals, not on long text (blur costs paint time).

Import the stylesheet once in main.tsx after index.css: `import "./motion-more.css"`. Budget: count it against the MOTION_INTENSITY dial (hover and focus effects are free); everything stops under `prefers-reduced-motion`.
