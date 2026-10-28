---
id: fx-bg-grid
type: effect
title: Grid background
summary: A faint square grid behind a section.
moods: [technical, clean, modern]
products: [saas, developer tools, hero]
tags: [animation, motion, ambient]
density: any
dependencies: []
licence: original
source: authored for DebCraft (motion kit part 2, D-269)
tested: "demo page in Edge: the class animates or transitions as described, no console errors, switched off under reduced motion (tests/test_motion_more.py, D-269)"
files:
  - from: recipes/motion-more.css
    to: src/motion-more.css
preview: assets/preview/fx-bg-grid.jpg
---

## Grid background

`class="bg-grid"` on a container; combine with `bg-fade-edges` so the grid fades toward the edges.

Import the stylesheet once in main.tsx after index.css: `import "./motion-more.css"`. Budget: count it against the MOTION_INTENSITY dial (hover and focus effects are free); everything stops under `prefers-reduced-motion`.
