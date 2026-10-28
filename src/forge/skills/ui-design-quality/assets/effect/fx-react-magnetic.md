---
id: fx-react-magnetic
type: effect
title: "Magnetic hover (React)"
summary: "A button or icon leans a few pixels toward the pointer and springs back."
moods: [playful, modern]
products: [marketing, creative, portfolio]
tags: [animation, motion, react, hover, pointer, button]
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
preview: assets/preview/fx-react-magnetic.jpg
---

## Magnetic hover (React)

A button or icon leans a few pixels toward the pointer and springs back. Wrap one call to action: `<Magnetic strength={10}><button className="btn">Donate</button></Magnetic>`. Pointer devices only; the wrapper adds no layout (inline-block).

Import `motion-hooks.css` once in main.tsx after index.css and the component from `./motion-hooks`. Budget: count it against the MOTION_INTENSITY dial; everything is final and static under `prefers-reduced-motion`.
