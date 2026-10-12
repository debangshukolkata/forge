---
id: fx-warp-background
type: effect
title: Warp background
summary: Grid lines rush toward the viewer on a tilted plane.
moods: [techy, dark, bold]
products: [hero, ai, games]
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

## Warp background

`<section class="warp">` over a dark background; content goes in a `relative` child above it. The plane fades out toward the top.

Import the stylesheet once in main.tsx after index.css: `import "./motion-fancy.css"`. Showpiece effects: one signature moment per page, never several in one viewport; everything stops under `prefers-reduced-motion`.
