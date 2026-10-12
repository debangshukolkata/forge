---
id: fx-flickering-grid
type: effect
title: Flickering grid
summary: "A grid of small squares that twinkle at different speeds, like a data display."
moods: [techy, dark, modern]
products: [ai, saas, hero background]
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

## Flickering grid

`<div class="flicker-grid" style="--cols:16"><i></i>...</div>` with as many `<i>` cells as you like (48 to 160); it looks random without JavaScript. Put it behind content with a mask or low opacity.

Import the stylesheet once in main.tsx after index.css: `import "./motion-fancy.css"`. Showpiece effects: one signature moment per page, never several in one viewport; everything stops under `prefers-reduced-motion`.
