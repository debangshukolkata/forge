---
id: fx-avatar-stack
type: effect
title: Avatar stack
summary: Overlapping round pictures with a ring and an optional +N count.
moods: [friendly, social]
products: [social proof, teams, landing]
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

## Avatar stack

`<div class="avatar-stack"><img ...><img ...><span>+12</span></div>`; set `--ring` to the background colour so the rings blend in. Always give each image an `alt`.

Import the stylesheet once in main.tsx after index.css: `import "./motion-fancy.css"`. Showpiece effects: one signature moment per page, never several in one viewport; everything stops under `prefers-reduced-motion`.
