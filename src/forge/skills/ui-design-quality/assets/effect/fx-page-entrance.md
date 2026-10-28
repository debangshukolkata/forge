---
id: fx-page-entrance
type: effect
title: Page entrance
summary: "A staggered fade-up of the first screen using `.enter` and `--i` per element."
moods: [calm, polished]
products: [landing, hero]
tags: [animation, motion]
density: any
dependencies: []
licence: original
source: "authored for DebCraft (motion kit, D-251)"
tested: "kit built with Vite + Tailwind v4, audit clean at 1280 and 375 px, reduced-motion safe (D-251)"
files:
  - {from: recipes/motion.css, to: src/motion.css}
preview: assets/preview/fx-page-entrance.jpg
---

## Page entrance

Add `class="enter"` and `style={{ '--i': n }}` to hero elements; each starts 100 ms after the previous. One signature entrance per page.

Effect budget: count it against the page's MOTION_INTENSITY dial; one signature effect per page.
