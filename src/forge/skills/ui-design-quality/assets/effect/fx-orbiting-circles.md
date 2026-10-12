---
id: fx-orbiting-circles
type: effect
title: Orbiting circles
summary: Small circles travel around a centre point on a dashed ring; good for integrations or a tech-stack graphic.
moods: [modern, techy, playful]
products: [saas, integrations, hero visual]
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

## Orbiting circles

`<div class="orbit" style="--r:90px"><b>core</b><span class="dot" style="--a:0deg">1</span><span class="dot" style="--a:120deg">2</span>...</div>`; give each dot a start angle `--a` (360 / count apart). `--duration` sets the speed. Two or three dots read best.

Import the stylesheet once in main.tsx after index.css: `import "./motion-fancy.css"`. Showpiece effects: one signature moment per page, never several in one viewport; everything stops under `prefers-reduced-motion`.
