---
id: fx-grid-pulse
type: effect
title: Pulsing grid
summary: A grid or pattern layer slowly brightens and fades.
moods: [techy, dark]
products: [ai, saas, hero]
tags: [animation, motion, ambient]
density: any
dependencies: []
licence: original
source: authored for DebCraft (motion kit part 2, D-269)
tested: "demo page in Edge: the class animates or transitions as described, no console errors, switched off under reduced motion (tests/test_motion_more.py, D-269)"
files:
  - from: recipes/motion-more.css
    to: src/motion-more.css
preview: assets/preview/fx-grid-pulse.jpg
---

## Pulsing grid

Add `grid-pulse` next to `bg-grid` on a layer behind the content.

Import the stylesheet once in main.tsx after index.css: `import "./motion-more.css"`. Budget: count it against the MOTION_INTENSITY dial (hover and focus effects are free); everything stops under `prefers-reduced-motion`.
