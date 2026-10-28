---
id: css-animation-techniques
type: css-technique
title: "Animation techniques"
summary: "Snippets for animation techniques."
moods: [scroll, transitions]
products: [stylesheet]
tags: [css, technique]
density: any
dependencies: []
licence: original
source: "authored for DebCraft (recipes/css-techniques.md)"
tested: snippets follow current Chromium (Edge) behaviour; checked when the recipe was written (D-251)
---

## Animation techniques
- Only `transform`, `opacity` (and filter for one-off effects) are cheap. Never animate width/height/top/left; for height
  use `grid-template-rows: 0fr -> 1fr` or `<details>`.
- Scroll-driven (no JS): `animation-timeline: scroll()` for a reading-progress bar; `animation-timeline: view()` with
  `animation-range: entry 0% cover 30%` for reveals (see `.reveal-scroll`). Wrap in `@supports (animation-timeline: view())`.
```css
.progress { position: fixed; inset: 0 0 auto 0; height: 3px; background: var(--accent); transform-origin: 0 50%; animation: grow linear; animation-timeline: scroll(root); }
@keyframes grow { from { transform: scaleX(0); } to { transform: scaleX(1); } }
```
- Entry animation for elements that appear (dialogs, popovers, toasts) with `@starting-style`:
```css
.toast { transition: opacity .3s, transform .3s; }
@starting-style { .toast { opacity: 0; transform: translateY(8px); } }
```
- Animate to/from `display: none` and `height: auto`: `transition-behavior: allow-discrete` and `interpolate-size: allow-keywords` (Chromium).
- Custom property animation with `@property` (rotating gradient border, number counters via `counter-reset` + `content: counter()`).
- View Transitions: `document.startViewTransition(() => setState(...))` gives a cross-fade or shared-element morph between
  states; give shared elements the same `view-transition-name`. Multi-page: `@view-transition { navigation: auto; }`.
- Easing: `cubic-bezier(.22,1,.36,1)` (smooth out), `cubic-bezier(.34,1.56,.64,1)` (bouncy), `ease-in-out` for loops.
  Durations: micro 120-200 ms, UI 200-350 ms, entrances 500-800 ms, ambient 6-20 s. Stagger 60-100 ms per item.
- Always: `@media (prefers-reduced-motion: reduce)` disables parallax, loops and big movement.
