---
id: fx-nudge-arrow
type: effect
title: Arrow nudge
summary: An arrow nudges right when its link or card is hovered.
moods: [clean, friendly]
products: [links, cta, cards]
tags: [animation, motion, hover]
density: any
dependencies: []
licence: original
source: authored for DebCraft (motion kit part 2, D-269)
tested: "demo page in Edge: the class animates or transitions as described, no console errors, switched off under reduced motion (tests/test_motion_more.py, D-269)"
files:
  - from: recipes/motion-more.css
    to: src/motion-more.css
---

## Arrow nudge

Put `group` on the link and `<span class="nudge">&rarr;</span>` inside it.

Import the stylesheet once in main.tsx after index.css: `import "./motion-more.css"`. Budget: count it against the MOTION_INTENSITY dial (hover and focus effects are free); everything stops under `prefers-reduced-motion`.
