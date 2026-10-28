---
id: fx-glass-surface
type: effect
title: Glass surface
summary: Frosted translucent panels in a light and a dark variant.
moods: [modern, soft, premium]
products: [saas, cards, navigation]
tags: [animation, motion]
density: any
dependencies: []
licence: original
source: "authored for DebCraft (motion kit, D-251)"
tested: "kit built with Vite + Tailwind v4, audit clean at 1280 and 375 px, reduced-motion safe (D-251)"
files:
  - {from: recipes/motion.css, to: src/motion.css}
preview: assets/preview/fx-glass-surface.jpg
---

## Glass surface

`.glass` (light) and `.glass-dark`; they need something colourful behind them to show the blur. The audit skips elements over gradients, so check contrast by eye.

Effect budget: count it against the page's MOTION_INTENSITY dial; one signature effect per page.
