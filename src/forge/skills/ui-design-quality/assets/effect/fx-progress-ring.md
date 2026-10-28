---
id: fx-progress-ring
type: effect
title: Progress ring
summary: A ring that fills to a percentage and animates between values.
moods: [clean, technical]
products: [dashboards, goals, uploads]
tags: [animation, motion, feedback]
density: any
dependencies: []
licence: original
source: authored for DebCraft (motion kit part 2, D-269)
tested: "demo page in Edge: the class animates or transitions as described, no console errors, switched off under reduced motion (tests/test_motion_more.py, D-269)"
files:
  - from: recipes/motion-more.css
    to: src/motion-more.css
preview: assets/preview/fx-progress-ring.jpg
---

## Progress ring

`<div class="progress-ring" style="--value:60" role="progressbar" aria-valuenow="60">`; change `--value` (0 to 100) to animate; set the size with `--size`.

Import the stylesheet once in main.tsx after index.css: `import "./motion-more.css"`. Budget: count it against the MOTION_INTENSITY dial (hover and focus effects are free); everything stops under `prefers-reduced-motion`.
