---
id: fx-scroll-reveal
type: effect
title: Scroll reveal with stagger
summary: Elements fade and slide in when scrolled into view; stagger a list with an index.
moods: [calm, modern, editorial]
products: [landing, marketing, portfolio]
tags: [animation, motion]
density: any
dependencies: []
licence: original
source: "authored for DebCraft (motion kit, D-251)"
tested: "kit built with Vite + Tailwind v4, audit clean at 1280 and 375 px, reduced-motion safe (D-251)"
files:
  - {from: recipes/motion.css, to: src/motion.css}
  - {from: recipes/motion.tsx, to: src/motion.tsx}
preview: assets/preview/fx-scroll-reveal.jpg
---

## Scroll reveal with stagger

Wrap content in `<Reveal>` (or `<Reveal index={i}>` for a stagger). Classes `.reveal`, `.reveal-left`, `.reveal-scale`, and a CSS-only `.reveal-scroll` variant where scroll-driven animations exist. Import `./motion.css` in main.tsx after index.css. Content stays visible without JavaScript and under reduced motion.

Effect budget: count it against the page's MOTION_INTENSITY dial; one signature effect per page.
