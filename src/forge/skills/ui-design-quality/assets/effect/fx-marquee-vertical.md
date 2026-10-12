---
id: fx-marquee-vertical
type: effect
title: Vertical marquee
summary: "A column of items scrolls upward endlessly, pausing on hover."
moods: [bold, modern]
products: [testimonials, logos, feeds]
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

## Vertical marquee

`<div class="marquee-vertical" style="--h:16rem"><div class="track">items, then the same items again</div></div>`; duplicate the items so the loop is seamless.

Import the stylesheet once in main.tsx after index.css: `import "./motion-more.css"`. Budget: count it against the MOTION_INTENSITY dial (hover and focus effects are free); everything stops under `prefers-reduced-motion`.
