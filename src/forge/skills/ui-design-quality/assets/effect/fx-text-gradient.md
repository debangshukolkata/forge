---
id: fx-text-gradient
type: effect
title: Static gradient text
summary: Heading text filled with a brand gradient that does not move.
moods: [modern, premium]
products: [hero, saas]
tags: [animation, motion, text]
density: any
dependencies: []
licence: original
source: authored for DebCraft (motion kit part 2, D-269)
tested: "demo page in Edge: the class animates or transitions as described, no console errors, switched off under reduced motion (tests/test_motion_more.py, D-269)"
files:
  - from: recipes/motion-more.css
    to: src/motion-more.css
preview: assets/preview/fx-text-gradient.jpg
---

## Static gradient text

`class="text-gradient"` on one word or phrase; uses `--color-brand-500` and `--color-brand-200`.

Import the stylesheet once in main.tsx after index.css: `import "./motion-more.css"`. Budget: count it against the MOTION_INTENSITY dial (hover and focus effects are free); everything stops under `prefers-reduced-motion`.
