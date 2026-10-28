---
id: fx-react-parallax
type: effect
title: "Parallax layer (React)"
summary: "A decorative layer that moves slower or faster than the page while it crosses the viewport."
moods: [calm, cinematic]
products: [marketing, storytelling, portfolio]
tags: [animation, motion, react, scroll, parallax, depth]
density: any
dependencies: []
licence: original
source: "authored for DebCraft (React motion hooks, D-383)"
tested: "built with Vite and React (type-checked); in Edge the text appears, the scramble settles on the real text, the magnet moves, the pinned step follows the scroll, nothing animates under reduced motion (tests/test_motion_hooks.py, D-383)"
files:
  - from: recipes/motion-hooks.tsx
    to: src/motion-hooks.tsx
  - from: recipes/motion-hooks.css
    to: src/motion-hooks.css
preview: assets/preview/fx-react-parallax.jpg
---

## Parallax layer (React)

A decorative layer that moves slower or faster than the page while it crosses the viewport. Wrap decorative art only: `<Parallax speed={0.2}><svg .../></Parallax>`. Never put text or controls in a moving layer; `useScrollProgress` gives the 0 to 1 value for your own effects.

Import `motion-hooks.css` once in main.tsx after index.css and the component from `./motion-hooks`. Budget: count it against the MOTION_INTENSITY dial; everything is final and static under `prefers-reduced-motion`.
