---
id: fx-scroll-progress
type: effect
title: Scroll progress bar
summary: "A thin bar at the top fills as the page scrolls (scroll-driven, no JavaScript)."
moods: [clean, editorial]
products: [articles, docs, long pages]
tags: [animation, motion, scroll]
density: any
dependencies: []
licence: original
source: authored for DebCraft (motion kit part 2, D-269)
tested: "demo page in Edge: the class animates or transitions as described, no console errors, switched off under reduced motion (tests/test_motion_more.py, D-269)"
files:
  - from: recipes/motion-more.css
    to: src/motion-more.css
---

## Scroll progress bar

`<div class="scroll-progress" aria-hidden="true"></div>` once near the top. Browsers without scroll-driven animations hide the bar.

Import the stylesheet once in main.tsx after index.css: `import "./motion-more.css"`. Budget: count it against the MOTION_INTENSITY dial (hover and focus effects are free); everything stops under `prefers-reduced-motion`.
