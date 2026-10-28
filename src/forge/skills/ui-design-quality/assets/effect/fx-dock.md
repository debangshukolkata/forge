---
id: fx-dock
type: effect
title: Dock magnification
summary: "Icons grow under the pointer and their neighbours grow a little, like a macOS dock."
moods: [playful, polished]
products: [toolbars, navigation, portfolio]
tags: [animation, motion, showpiece]
density: any
dependencies: []
licence: original
source: authored for DebCraft (motion kit part 3, in the spirit of public UI-effect catalogues, no code copied, D-270)
tested: "demo page in Edge: animation runs, positions or scales as described, no console errors, off under reduced motion (tests/test_motion_fancy.py, D-270)"
files:
  - from: recipes/motion-fancy.css
    to: src/motion-fancy.css
preview: assets/preview/fx-dock.jpg
---

## Dock magnification

`<nav class="dock"><a>..</a><a>..</a>...</nav>`; each child is an icon button (48 px). It also reacts to keyboard focus. Needs `:has()` (current browsers).

Import the stylesheet once in main.tsx after index.css: `import "./motion-fancy.css"`. Showpiece effects: one signature moment per page, never several in one viewport; everything stops under `prefers-reduced-motion`.
