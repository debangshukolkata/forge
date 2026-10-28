---
id: fx-parallax
type: effect
title: Parallax drift
summary: An element drifts slower or faster than the page as it passes through the viewport.
moods: [modern, dreamy]
products: [hero images, backgrounds]
tags: [animation, motion, scroll]
density: any
dependencies: []
licence: original
source: authored for DebCraft (motion kit part 2, D-269)
tested: "demo page in Edge: the class animates or transitions as described, no console errors, switched off under reduced motion (tests/test_motion_more.py, D-269)"
files:
  - from: recipes/motion-more.css
    to: src/motion-more.css
preview: assets/preview/fx-parallax.jpg
---

## Parallax drift

`class="parallax"` with `--from` and `--to` offsets (for example 40px and -40px); only where scroll-driven animations are supported, otherwise static.

Import the stylesheet once in main.tsx after index.css: `import "./motion-more.css"`. Budget: count it against the MOTION_INTENSITY dial (hover and focus effects are free); everything stops under `prefers-reduced-motion`.
