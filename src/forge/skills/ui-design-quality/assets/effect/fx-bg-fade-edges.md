---
id: fx-bg-fade-edges
type: effect
title: Fade edges mask
summary: Fades a decorative background to transparent toward the edges.
moods: [modern, clean]
products: [hero, backgrounds]
tags: [animation, motion, ambient]
density: any
dependencies: []
licence: original
source: authored for DebCraft (motion kit part 2, D-269)
tested: "demo page in Edge: the class animates or transitions as described, no console errors, switched off under reduced motion (tests/test_motion_more.py, D-269)"
files:
  - from: recipes/motion-more.css
    to: src/motion-more.css
preview: assets/preview/fx-bg-fade-edges.jpg
---

## Fade edges mask

Add `bg-fade-edges` to the same element as `bg-grid`, `bg-dots` or `bg-mesh`.

Import the stylesheet once in main.tsx after index.css: `import "./motion-more.css"`. Budget: count it against the MOTION_INTENSITY dial (hover and focus effects are free); everything stops under `prefers-reduced-motion`.
