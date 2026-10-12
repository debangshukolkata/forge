---
id: fx-pulse-ring
type: effect
title: Pulse rings
summary: "Two rings expand and fade from an element, like a live signal."
moods: [energetic, urgent]
products: [live status, record, donate, cta]
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

## Pulse rings

`class="pulse-ring"` on a round or rounded element; the rings use the brand colour.

Import the stylesheet once in main.tsx after index.css: `import "./motion-more.css"`. Budget: count it against the MOTION_INTENSITY dial (hover and focus effects are free); everything stops under `prefers-reduced-motion`.
