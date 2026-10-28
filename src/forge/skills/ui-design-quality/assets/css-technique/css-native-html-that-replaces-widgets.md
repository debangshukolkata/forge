---
id: css-native-html-that-replaces-widgets
type: css-technique
title: "Native HTML that replaces widgets"
summary: "Snippets for native html that replaces widgets."
moods: [dialog, popover]
products: [stylesheet]
tags: [css, technique]
density: any
dependencies: []
licence: original
source: "authored for DebCraft (recipes/css-techniques.md)"
tested: snippets follow current Chromium (Edge) behaviour; checked when the recipe was written (D-251)
---

## Native HTML that replaces widgets
`<dialog>` (modal, focus trap, Esc), `popover` attribute with `popovertarget` (tooltips, menus, no JS), `<details name="faq">`
(exclusive accordion), `<input type="date|range|color">`, `inert` (disable a region), `loading="lazy"` and `decoding="async"` on
images, `<picture>` for art direction, `fetchpriority="high"` on the hero image, `scroll-snap-type` for carousels.
```css
.carousel { display: flex; overflow-x: auto; scroll-snap-type: x mandatory; gap: 1rem; scrollbar-width: none; }
.carousel > * { flex: 0 0 min(22rem, 85%); scroll-snap-align: start; }
```
