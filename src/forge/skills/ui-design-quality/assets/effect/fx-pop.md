---
id: fx-pop
type: effect
title: Pop
summary: A quick overshoot scale for a badge or count that just changed.
moods: [playful, energetic]
products: [badges, cart, likes]
tags: [animation, motion, feedback]
density: any
dependencies: []
licence: original
source: authored for DebCraft (motion kit part 2, D-269)
tested: "demo page in Edge: the class animates or transitions as described, no console errors, switched off under reduced motion (tests/test_motion_more.py, D-269)"
files:
  - from: recipes/motion-more.css
    to: src/motion-more.css
---

## Pop

Add `pop` when the value changes (re-add the class to repeat).

Import the stylesheet once in main.tsx after index.css: `import "./motion-more.css"`. Budget: count it against the MOTION_INTENSITY dial (hover and focus effects are free); everything stops under `prefers-reduced-motion`.
