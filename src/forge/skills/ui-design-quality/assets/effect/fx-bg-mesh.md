---
id: fx-bg-mesh
type: effect
title: Gradient mesh background
summary: Soft overlapping colour glows built from your brand variables.
moods: [modern, soft, warm]
products: [hero, saas, onboarding]
tags: [animation, motion, ambient]
density: any
dependencies: []
licence: original
source: authored for DebCraft (motion kit part 2, D-269)
tested: "demo page in Edge: the class animates or transitions as described, no console errors, switched off under reduced motion (tests/test_motion_more.py, D-269)"
files:
  - from: recipes/motion-more.css
    to: src/motion-more.css
---

## Gradient mesh background

`class="bg-mesh"` on the hero section; static (no animation), so it is cheap and accessible.

Import the stylesheet once in main.tsx after index.css: `import "./motion-more.css"`. Budget: count it against the MOTION_INTENSITY dial (hover and focus effects are free); everything stops under `prefers-reduced-motion`.
