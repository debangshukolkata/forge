---
id: fx-marker-highlight
type: effect
title: Highlighter marker
summary: A marker stroke grows under a phrase.
moods: [editorial, friendly, warm]
products: [articles, landing, emphasis]
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

## Highlighter marker

`<span class="marker">phrase</span>`; add `is-visible` when it scrolls in (the `Reveal` helper does this) or use `marker-now` to show it at once.

Import the stylesheet once in main.tsx after index.css: `import "./motion-more.css"`. Budget: count it against the MOTION_INTENSITY dial (hover and focus effects are free); everything stops under `prefers-reduced-motion`.
