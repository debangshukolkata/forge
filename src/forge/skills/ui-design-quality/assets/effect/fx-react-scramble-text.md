---
id: fx-react-scramble-text
type: effect
title: "Scramble text (React)"
summary: "Letters flicker through noise and settle left to right into the real text, once."
moods: [technical, playful]
products: [developer tools, games, dashboards]
tags: [animation, motion, react, text, scramble, decode]
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
---

## Scramble text (React)

Letters flicker through noise and settle left to right into the real text, once. Use `<ScrambleText text="Open every day" />` for a short label or a status word, not for a paragraph. The real text is the aria-label; the animation runs once when 40 percent visible.

Import `motion-hooks.css` once in main.tsx after index.css and the component from `./motion-hooks`. Budget: count it against the MOTION_INTENSITY dial; everything is final and static under `prefers-reduced-motion`.
