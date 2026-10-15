---
id: fx-react-animated-beam
type: effect
title: "Animated beam (React)"
summary: "A light travels along a curve between two elements: integrations, data flow, how things connect."
moods: [technical, modern]
products: [integrations, developer tools, saas]
tags: [animation, motion, react, svg, connection, beam]
density: any
dependencies: []
licence: original
source: "authored for DebCraft (canvas and SVG showpiece effects, D-384)"
tested: "built with Vite and React (type-checked); in Edge the beam draws a path with a moving light, the canvases paint and keep changing, and under reduced motion they are drawn once (tests/test_motion_canvas.py, D-384)"
files:
  - from: recipes/motion-canvas.tsx
    to: src/motion-canvas.tsx
---

## Animated beam (React)

A light travels along a curve between two elements: integrations, data flow, how things connect. Put the two elements and the beam in one positioned container: `<AnimatedBeam containerRef={box} fromRef={a} toRef={b} />`. It re-measures on resize; under reduced motion it is a still line.

Import the component from `./motion-canvas`. Colours come from `--color-primary`; the effect is decoration and sets aria-hidden itself. Budget: one showpiece per page, counted against the MOTION_INTENSITY dial.
