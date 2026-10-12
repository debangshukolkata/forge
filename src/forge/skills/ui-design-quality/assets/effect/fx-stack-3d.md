---
id: fx-stack-3d
type: effect
title: 3D layer stack
summary: Stacked layers separate in depth on hover.
moods: [modern, premium]
products: [hero visuals, product shots]
tags: [animation, motion, 3d]
density: any
dependencies: []
licence: original
source: authored for DebCraft (motion kit part 2, D-269)
tested: "demo page in Edge: the class animates or transitions as described, no console errors, switched off under reduced motion (tests/test_motion_more.py, D-269)"
files:
  - from: recipes/motion-more.css
    to: src/motion-more.css
---

## 3D layer stack

`.stack-3d` on the parent with children `style="--i:0"`, `--i:1`, ...; the parent needs `perspective` from a wrapper.

Import the stylesheet once in main.tsx after index.css: `import "./motion-more.css"`. Budget: count it against the MOTION_INTENSITY dial (hover and focus effects are free); everything stops under `prefers-reduced-motion`.
