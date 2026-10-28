---
id: fx-in-slide
type: effect
title: "Entrance: slide in from the side"
summary: "Elements slide in from the left (`in-left`) or right (`in-right`) while fading."
moods: [energetic, modern]
products: [landing, features, split sections]
tags: [animation, motion, entrance]
density: any
dependencies: []
licence: original
source: authored for DebCraft (motion kit part 2, D-269)
tested: "demo page in Edge: the class animates or transitions as described, no console errors, switched off under reduced motion (tests/test_motion_more.py, D-269)"
files:
  - from: recipes/motion-more.css
    to: src/motion-more.css
preview: assets/preview/fx-in-slide.jpg
---

## Entrance: slide in from the side

`in-left` for text columns, `in-right` for visuals so the two meet. 28 px travel; stagger with `--i`.

Import the stylesheet once in main.tsx after index.css: `import "./motion-more.css"`. Budget: count it against the MOTION_INTENSITY dial (hover and focus effects are free); everything stops under `prefers-reduced-motion`.
