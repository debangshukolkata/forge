---
id: fx-react-pinned-steps
type: effect
title: "Pinned steps (React)"
summary: "A list of steps beside a panel that stays pinned while the active step follows the scroll."
moods: [clear, editorial]
products: [onboarding, how it works, product story]
tags: [animation, motion, react, scroll, steps, sticky]
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
preview: assets/preview/fx-react-pinned-steps.jpg
---

## Pinned steps (React)

A list of steps beside a panel that stays pinned while the active step follows the scroll. Use `<PinnedSteps steps={[{ title, body }, ...]} />` for three to six steps. It collapses to one column on a phone with the panel on top; every step is a real heading and paragraph in document order.

Import `motion-hooks.css` once in main.tsx after index.css and the component from `./motion-hooks`. Budget: count it against the MOTION_INTENSITY dial; everything is final and static under `prefers-reduced-motion`.
