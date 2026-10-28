---
id: fx-grain
type: effect
title: Film grain overlay
summary: A subtle noise layer that takes the digital flatness off large colour areas.
moods: [editorial, retro, warm]
products: [posters, landing, portfolio]
tags: [animation, motion]
density: any
dependencies: []
licence: original
source: "authored for DebCraft (motion kit, D-251)"
tested: "kit built with Vite + Tailwind v4, audit clean at 1280 and 375 px, reduced-motion safe (D-251)"
files:
  - {from: recipes/motion.css, to: src/motion.css}
preview: assets/preview/fx-grain.jpg
---

## Film grain overlay

`.grain` on a `relative` container. Opacity is low by design; never over small text.

Effect budget: count it against the page's MOTION_INTENSITY dial; one signature effect per page.
