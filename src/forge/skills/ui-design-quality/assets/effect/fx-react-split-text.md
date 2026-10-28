---
id: fx-react-split-text
type: effect
title: "Split text (React)"
summary: "Words or letters of a heading rise in one after another when scrolled into view."
moods: [editorial, confident]
products: [marketing, headlines, landing]
tags: [animation, motion, react, text, entrance, stagger]
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
preview: assets/preview/fx-react-split-text.jpg
---

## Split text (React)

Words or letters of a heading rise in one after another when scrolled into view. Use `<SplitText text="Give blood, give time" by="word" />` for a hero heading. The full text is the aria-label and the pieces are aria-hidden, so screen readers read one heading. Under reduced motion the text is simply there.

Import `motion-hooks.css` once in main.tsx after index.css and the component from `./motion-hooks`. Budget: count it against the MOTION_INTENSITY dial; everything is final and static under `prefers-reduced-motion`.
