---
id: fx-aurora
type: effect
title: Aurora background
summary: Blurred colour blobs drifting slowly behind the hero.
moods: [modern, dark, soft]
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

## Aurora background

Put `<div class="aurora"><i/><i/></div>` as the first child of a `relative` hero section. Transform-only animation. Keep text contrast above 4.5:1 over the blobs.

Effect budget: count it against the page's MOTION_INTENSITY dial; one signature effect per page.
