---
id: fx-skeleton
type: effect
title: Skeleton loader
summary: Pulsing placeholder blocks shown while data loads.
moods: [calm, clean]
products: [dashboard, lists, forms]
tags: [animation, motion]
density: any
dependencies: []
licence: original
source: "authored for DebCraft (motion kit, D-251)"
tested: "kit built with Vite + Tailwind v4, audit clean at 1280 and 375 px, reduced-motion safe (D-251)"
files:
  - {from: recipes/motion.css, to: src/motion.css}
---

## Skeleton loader

`.skeleton` on blocks sized like the real content. For rows use the `SkeletonRows` component (component asset `cmp-skeleton-rows`).

Effect budget: count it against the page's MOTION_INTENSITY dial; one signature effect per page.
