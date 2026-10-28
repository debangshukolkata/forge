---
id: css-responsive-and-accessibility-basics
type: css-technique
title: "Responsive and accessibility basics"
summary: "Snippets for responsive and accessibility basics."
moods: [focus, contrast]
products: [stylesheet]
tags: [css, technique]
density: any
dependencies: []
licence: original
source: "authored for DebCraft (recipes/css-techniques.md)"
tested: snippets follow current Chromium (Edge) behaviour; checked when the recipe was written (D-251)
---

## Responsive and accessibility basics
- Mobile first; breakpoints 640 / 768 / 1024 / 1280. Test 375 and 1280. Touch targets >= 44 px.
- `:focus-visible` ring on everything interactive; never `outline: none` without a replacement.
- `forced-colors` and `prefers-contrast` are cheap wins: keep borders on controls, do not rely on shadows alone.
- `@media (hover: hover)` around hover-only effects; `@media (pointer: coarse)` to enlarge targets.
