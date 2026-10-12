---
id: fx-bg-dots
type: effect
title: Dot grid background
summary: A faint dot pattern behind a section.
moods: [clean, calm, technical]
products: [landing, dashboards, hero]
tags: [animation, motion, ambient]
density: any
dependencies: []
licence: original
source: authored for DebCraft (motion kit part 2, D-269)
tested: "demo page in Edge: the class animates or transitions as described, no console errors, switched off under reduced motion (tests/test_motion_more.py, D-269)"
files:
  - from: recipes/motion-more.css
    to: src/motion-more.css
---

## Dot grid background

`class="bg-dots"`; quieter than the line grid.

Import the stylesheet once in main.tsx after index.css: `import "./motion-more.css"`. Budget: count it against the MOTION_INTENSITY dial (hover and focus effects are free); everything stops under `prefers-reduced-motion`.
