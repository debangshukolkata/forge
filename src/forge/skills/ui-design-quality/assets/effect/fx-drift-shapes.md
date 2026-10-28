---
id: fx-drift-shapes
type: effect
title: Drifting shapes
summary: "Decorative shapes float slowly; each uses `--i` for a different phase."
moods: [playful, soft]
products: [hero, illustration]
tags: [animation, motion, ambient]
density: any
dependencies: []
licence: original
source: authored for DebCraft (motion kit part 2, D-269)
tested: "demo page in Edge: the class animates or transitions as described, no console errors, switched off under reduced motion (tests/test_motion_more.py, D-269)"
files:
  - from: recipes/motion-more.css
    to: src/motion-more.css
preview: assets/preview/fx-drift-shapes.jpg
---

## Drifting shapes

`<div class="drift" style="--i:1" aria-hidden="true">`; three or four shapes at most.

Import the stylesheet once in main.tsx after index.css: `import "./motion-more.css"`. Budget: count it against the MOTION_INTENSITY dial (hover and focus effects are free); everything stops under `prefers-reduced-motion`.
