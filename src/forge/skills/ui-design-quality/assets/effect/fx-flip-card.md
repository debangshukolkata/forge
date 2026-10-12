---
id: fx-flip-card
type: effect
title: Flip card
summary: A card turns over to show its back on hover or keyboard focus.
moods: [playful, modern]
products: [team, features, flashcards]
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

## Flip card

Structure: `.flip-card > .flip-inner > .face` (front) and `.face.back`; give `.flip-card` a `tabindex="0"` so keyboard users can flip it. Content on the back must also be reachable some other way for touch screens.

Import the stylesheet once in main.tsx after index.css: `import "./motion-more.css"`. Budget: count it against the MOTION_INTENSITY dial (hover and focus effects are free); everything stops under `prefers-reduced-motion`.
