---
id: fx-shimmer-text
type: effect
title: Shimmer gradient text
summary: Heading text filled with a slowly panning brand gradient.
moods: [modern, premium]
products: [saas, ai, hero]
tags: [animation, motion]
density: any
dependencies: []
licence: original
source: "authored for DebCraft (motion kit, D-251)"
tested: "kit built with Vite + Tailwind v4, audit clean at 1280 and 375 px, reduced-motion safe (D-251)"
files:
  - {from: recipes/motion.css, to: src/motion.css}
---

## Shimmer gradient text

`.text-shimmer` on dark backgrounds and `.text-shimmer-light` on light ones; uses `--color-brand-*` theme variables. Use on one word or phrase, not whole paragraphs (contrast).

Effect budget: count it against the page's MOTION_INTENSITY dial; one signature effect per page.
