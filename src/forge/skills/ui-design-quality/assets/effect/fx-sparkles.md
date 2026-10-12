---
id: fx-sparkles
type: effect
title: Sparkles
summary: Small stars that twinkle at positions you choose.
moods: [magical, playful, premium]
products: [hero, ai, badges]
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

## Sparkles

`<div class="sparkles"><i style="--x:20%;--y:30%;--d:0s"></i>...</div>`; three to six stars with different delays. Place them near a headline, not over text.

Import the stylesheet once in main.tsx after index.css: `import "./motion-fancy.css"`. Showpiece effects: one signature moment per page, never several in one viewport; everything stops under `prefers-reduced-motion`.
