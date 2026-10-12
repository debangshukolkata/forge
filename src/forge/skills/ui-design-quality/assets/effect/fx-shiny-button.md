---
id: fx-shiny-button
type: effect
title: Shiny button
summary: A dark button with a soft highlight that keeps sweeping across.
moods: [premium, modern]
products: [cta, saas, pricing]
tags: [animation, motion, showpiece]
density: any
dependencies: []
licence: original
source: authored for DebCraft (motion kit part 3, in the spirit of public UI-effect catalogues, no code copied, D-270)
tested: "demo page in Edge: animation runs, positions or scales as described, no console errors, off under reduced motion (tests/test_motion_fancy.py, D-270)"
files:
  - from: recipes/motion-fancy.css
    to: src/motion-fancy.css
---

## Shiny button

`<a class="btn-shiny">Start free</a>`; white text on the ink colour. Use it for the single primary action.

Import the stylesheet once in main.tsx after index.css: `import "./motion-fancy.css"`. Showpiece effects: one signature moment per page, never several in one viewport; everything stops under `prefers-reduced-motion`.
