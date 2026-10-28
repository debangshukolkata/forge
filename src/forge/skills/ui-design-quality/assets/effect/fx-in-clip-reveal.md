---
id: fx-in-clip-reveal
type: effect
title: "Entrance: wipe reveal"
summary: A clip-path wipe reveals the element from left to right.
moods: [bold, editorial]
products: [headlines, images, posters]
tags: [animation, motion, entrance]
density: any
dependencies: []
licence: original
source: authored for DebCraft (motion kit part 2, D-269)
tested: "demo page in Edge: the class animates or transitions as described, no console errors, switched off under reduced motion (tests/test_motion_more.py, D-269)"
files:
  - from: recipes/motion-more.css
    to: src/motion-more.css
preview: assets/preview/fx-in-clip-reveal.jpg
---

## Entrance: wipe reveal

`class="in-clip"`; 0.9 s. Works well on a big headline or an image.

Import the stylesheet once in main.tsx after index.css: `import "./motion-more.css"`. Budget: count it against the MOTION_INTENSITY dial (hover and focus effects are free); everything stops under `prefers-reduced-motion`.
