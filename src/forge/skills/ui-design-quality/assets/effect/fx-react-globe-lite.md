---
id: fx-react-globe-lite
type: effect
title: "Globe (React)"
summary: "A slowly turning sphere of dots: a world without map data."
moods: [global, modern]
products: [travel, logistics, nonprofit, saas]
tags: [animation, motion, react, canvas, globe, hero]
density: any
dependencies: []
licence: original
source: "authored for DebCraft (canvas and SVG showpiece effects, D-384)"
tested: "built with Vite and React (type-checked); in Edge the beam draws a path with a moving light, the canvases paint and keep changing, and under reduced motion they are drawn once (tests/test_motion_canvas.py, D-384)"
files:
  - from: recipes/motion-canvas.tsx
    to: src/motion-canvas.tsx
---

## Globe (React)

A slowly turning sphere of dots: a world without map data. `<GlobeLite size={320} />` as a hero visual or a section ornament; it is a sphere, not a map, so do not use it to show places. Drawn once under reduced motion.

Import the component from `./motion-canvas`. Colours come from `--color-primary`; the effect is decoration and sets aria-hidden itself. Budget: one showpiece per page, counted against the MOTION_INTENSITY dial.
