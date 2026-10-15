---
id: fx-spotlight-card
type: effect
title: Spotlight card
summary: A soft glow follows the pointer across a card.
moods: [modern, premium, dark]
products: [saas, features, bento]
tags: [animation, motion, glow, glows, following, follows, mouse, cursor, pointer, hover]
density: any
dependencies: []
licence: original
source: "authored for DebCraft (motion kit, D-251)"
tested: "kit built with Vite + Tailwind v4, audit clean at 1280 and 375 px, reduced-motion safe (D-251)"
files:
  - {from: recipes/motion.css, to: src/motion.css}
  - {from: recipes/motion.tsx, to: src/motion.tsx}
---

## Spotlight card

`<SpotlightCard className="card">`; sets `--x/--y` from the pointer. Works best on dark or tinted card surfaces.

Effect budget: count it against the page's MOTION_INTENSITY dial; one signature effect per page.
