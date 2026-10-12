---
id: fx-tilt-card
type: effect
title: Tilt card
summary: A gentle 3D tilt that follows the pointer on hover (pointer devices only).
moods: [playful, modern]
products: [cards, portfolio, products]
tags: [animation, motion]
density: any
dependencies: []
licence: original
source: "authored for DebCraft (motion kit, D-251)"
tested: "kit built with Vite + Tailwind v4, audit clean at 1280 and 375 px, reduced-motion safe (D-251)"
files:
  - {from: recipes/motion.css, to: src/motion.css}
  - {from: recipes/motion.tsx, to: src/motion.tsx}
---

## Tilt card

`<TiltCard max={6}>`; disabled on touch and under reduced motion. Keep the angle small (6 degrees or less).

Effect budget: count it against the page's MOTION_INTENSITY dial; one signature effect per page.
