---
id: fx-words-rise
type: effect
title: Words rise one by one
summary: Each word of a headline rises into place in sequence.
moods: [bold, polished, editorial]
products: [hero, headlines]
tags: [animation, motion, text]
density: any
dependencies: []
licence: original
source: authored for DebCraft (motion kit part 2, D-269)
tested: "demo page in Edge: the class animates or transitions as described, no console errors, switched off under reduced motion (tests/test_motion_more.py, D-269)"
files:
  - from: recipes/motion-more.css
    to: src/motion-more.css
preview: assets/preview/fx-words-rise.jpg
---

## Words rise one by one

Wrap each word: `<h1 class="words"><span style="--w:0">Give</span> <span style="--w:1">blood</span></h1>`. Keep headlines short; reduced motion shows them at once.

Import the stylesheet once in main.tsx after index.css: `import "./motion-more.css"`. Budget: count it against the MOTION_INTENSITY dial (hover and focus effects are free); everything stops under `prefers-reduced-motion`.
