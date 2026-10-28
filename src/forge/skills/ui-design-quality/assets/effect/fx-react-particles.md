---
id: fx-react-particles
type: effect
title: "Particles (React)"
summary: "Drifting dots with faint links behind a hero; pauses when the tab is hidden or the canvas is off screen."
moods: [technical, calm]
products: [hero, saas, ai]
tags: [animation, motion, react, canvas, particles, background]
density: any
dependencies: []
licence: original
source: "authored for DebCraft (canvas and SVG showpiece effects, D-384)"
tested: "built with Vite and React (type-checked); in Edge the beam draws a path with a moving light, the canvases paint and keep changing, and under reduced motion they are drawn once (tests/test_motion_canvas.py, D-384)"
files:
  - from: recipes/motion-canvas.tsx
    to: src/motion-canvas.tsx
preview: assets/preview/fx-react-particles.jpg
---

## Particles (React)

Drifting dots with faint links behind a hero; pauses when the tab is hidden or the canvas is off screen. Size the parent and put `<Particles count={60} />` inside it behind the content (position absolute, z-index 0). Keep the count under 100 on phones. Decoration only.

Import the component from `./motion-canvas`. Colours come from `--color-primary`; the effect is decoration and sets aria-hidden itself. Budget: one showpiece per page, counted against the MOTION_INTENSITY dial.
