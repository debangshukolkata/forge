---
id: css-selectors-that-remove-javascript
type: css-technique
title: "Selectors that remove JavaScript"
summary: "Snippets for selectors that remove javascript."
moods: [selectors]
products: [web, landing, app, dashboard]
tags: [css, html, native, no dependency]
density: any
dependencies: []
licence: original
source: "authored for DebCraft (recipes/css-techniques.md)"
tested: snippets follow current Chromium (Edge) behaviour; checked when the recipe was written (D-251)
---

## Selectors that remove JavaScript
```css
.field:has(input:user-invalid) { --ring: var(--color-brand-600); }          /* style a parent by its child's state */
form:has(:invalid) button[type="submit"] { opacity: .6; }                   /* disable-look until valid */
.nav a:is(:hover, :focus-visible) { color: var(--color-brand-600); }        /* group selectors */
li:not(:last-child) { border-bottom: 1px solid var(--color-ink-200); }
input:user-invalid { border-color: var(--color-brand-600); }                /* only after the user interacted */
details[open] summary svg { transform: rotate(180deg); }                    /* accordion state */
```
