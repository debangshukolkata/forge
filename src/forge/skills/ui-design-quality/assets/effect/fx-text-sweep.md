---
id: fx-text-sweep
type: effect
title: Text light sweep
summary: A bright band sweeps across heading text on a loop.
moods: [premium, modern, bold]
products: [hero, saas, campaign]
tags: [animation, motion, text]
density: any
dependencies: []
licence: original
source: authored for DebCraft (motion kit part 2, D-269)
tested: "demo page in Edge: the class animates or transitions as described, no console errors, switched off under reduced motion (tests/test_motion_more.py, D-269)"
files:
  - from: recipes/motion-more.css
    to: src/motion-more.css
preview: assets/preview/fx-text-sweep.jpg
---

## Text light sweep

`class="text-sweep"` on a heading; it sets the text colour itself. One per page, large type only (the sweep lowers contrast briefly).

Import the stylesheet once in main.tsx after index.css: `import "./motion-more.css"`. Budget: count it against the MOTION_INTENSITY dial (hover and focus effects are free); everything stops under `prefers-reduced-motion`.
