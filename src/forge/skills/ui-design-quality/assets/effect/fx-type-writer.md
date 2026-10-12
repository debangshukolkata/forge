---
id: fx-type-writer
type: effect
title: Typewriter text
summary: A line of text types out letter by letter with a blinking caret.
moods: [retro, technical, playful]
products: [developer tools, hero, terminal]
tags: [animation, motion, text]
density: any
dependencies: []
licence: original
source: authored for DebCraft (motion kit part 2, D-269)
tested: "demo page in Edge: the class animates or transitions as described, no console errors, switched off under reduced motion (tests/test_motion_more.py, D-269)"
files:
  - from: recipes/motion-more.css
    to: src/motion-more.css
---

## Typewriter text

`<span class="type-writer" style="--chars:24">...</span>` where `--chars` is the exact length of the single line of text; the class sets a monospace font so the width is exact.

Import the stylesheet once in main.tsx after index.css: `import "./motion-more.css"`. Budget: count it against the MOTION_INTENSITY dial (hover and focus effects are free); everything stops under `prefers-reduced-motion`.
