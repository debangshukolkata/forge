---
id: fx-spinner
type: effect
title: Spinner
summary: A small ring spinner for pending actions.
moods: [clean, neutral]
products: [buttons, loading]
tags: [animation, motion, feedback]
density: any
dependencies: []
licence: original
source: authored for DebCraft (motion kit part 2, D-269)
tested: "demo page in Edge: the class animates or transitions as described, no console errors, switched off under reduced motion (tests/test_motion_more.py, D-269)"
files:
  - from: recipes/motion-more.css
    to: src/motion-more.css
preview: assets/preview/fx-spinner.jpg
---

## Spinner

`<span class="spinner" role="status" aria-label="Loading"></span>`; takes the text colour of its parent.

Import the stylesheet once in main.tsx after index.css: `import "./motion-more.css"`. Budget: count it against the MOTION_INTENSITY dial (hover and focus effects are free); everything stops under `prefers-reduced-motion`.
