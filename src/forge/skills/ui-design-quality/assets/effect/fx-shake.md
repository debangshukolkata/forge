---
id: fx-shake
type: effect
title: Error shake
summary: A short horizontal shake for invalid input.
moods: [robust, clear]
products: [forms, login]
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

## Error shake

Add `shake` to the field or form when validation fails (remove the class and add it again to repeat); also show the error text, never rely on motion alone.

Import the stylesheet once in main.tsx after index.css: `import "./motion-more.css"`. Budget: count it against the MOTION_INTENSITY dial (hover and focus effects are free); everything stops under `prefers-reduced-motion`.
