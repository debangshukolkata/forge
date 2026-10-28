---
id: fx-rainbow-border-button
type: effect
title: Rainbow border button
summary: A pill button whose border is a rotating rainbow gradient.
moods: [playful, bold, energetic]
products: [cta, landing, ai]
tags: [animation, motion, showpiece]
density: any
dependencies: []
licence: original
source: authored for DebCraft (motion kit part 3, in the spirit of public UI-effect catalogues, no code copied, D-270)
tested: "demo page in Edge: animation runs, positions or scales as described, no console errors, off under reduced motion (tests/test_motion_fancy.py, D-270)"
files:
  - from: recipes/motion-fancy.css
    to: src/motion-fancy.css
preview: assets/preview/fx-rainbow-border-button.jpg
---

## Rainbow border button

`<a class="btn-rainbow">Get started</a>`; set `--rb-fill` to the page background colour so the inside looks flat. One per page; needs `@property` support (all current browsers).

Import the stylesheet once in main.tsx after index.css: `import "./motion-fancy.css"`. Showpiece effects: one signature moment per page, never several in one viewport; everything stops under `prefers-reduced-motion`.
