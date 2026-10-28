---
id: lib-daisyui-v5-on-tailwind-v4
type: recipe
title: "daisyUI v5 on Tailwind v4"
summary: "Component-library mode: daisyui v5 on tailwind v4."
moods: [practical]
products: [internal tool, admin]
tags: [component library, daisyui, mui, shadcn, tabler, quickstart]
density: any
dependencies: []
licence: original
source: "authored for DebCraft (recipes/component-libraries.md, D-437)"
tested: "quickstarts were built and audited when the recipe was written (D-251, D-437); not re-run for this asset"
---

## daisyUI v5 on Tailwind v4
Install: `npm i tailwindcss @tailwindcss/vite` (see SKILL.md section 0) and `npm i -D daisyui`.
Built-in themes (pick a few; first is the default, `--prefersdark` follows the OS):
```css
@import "tailwindcss";
@plugin "daisyui" {
  themes: light --default, dark --prefersdark, cupcake, retro, forest, synthwave;
}
```
A brand theme (recommended: this is what stops it looking like daisyUI):
```css
@import "tailwindcss";
@plugin "daisyui" { themes: false; }
@plugin "daisyui/theme" {
  name: "brand"; default: true; color-scheme: light;
  --color-base-100: oklch(99% 0.004 60);  --color-base-200: oklch(96% 0.008 60);  --color-base-300: oklch(90% 0.012 60);
  --color-base-content: oklch(24% 0.02 40);
  --color-primary: oklch(50% 0.19 27);    --color-primary-content: oklch(98% 0.01 27);
  --color-secondary: oklch(42% 0.05 40);  --color-secondary-content: oklch(98% 0.01 40);
  --color-accent: oklch(70% 0.14 70);     --color-accent-content: oklch(22% 0.03 70);
  --color-neutral: oklch(27% 0.02 40);    --color-neutral-content: oklch(96% 0.01 40);
  --color-info: oklch(62% 0.13 240);      --color-info-content: oklch(98% 0.01 240);
  --color-success: oklch(60% 0.14 150);   --color-success-content: oklch(98% 0.01 150);
  --color-warning: oklch(80% 0.15 80);    --color-warning-content: oklch(25% 0.04 80);
  --color-error: oklch(58% 0.2 27);       --color-error-content: oklch(98% 0.01 27);
  --radius-selector: 1rem; --radius-field: 0.75rem; --radius-box: 1.25rem;
  --size-selector: 0.25rem; --size-field: 0.25rem; --border: 1px; --depth: 1; --noise: 0;
}
```
**Set the theme on `<html>`**, not on a wrapper div (a wrapper leaves a white strip below the content and misses the page
background): `document.documentElement.setAttribute("data-theme", name)`. Switch themes the same way and remember the choice.
Component classes (all semantic, no JavaScript): `btn btn-primary|secondary|accent|ghost|outline|sm|lg`, `card card-body card-title`,
`navbar`, `hero hero-content`, `stats stat stat-title stat-value stat-desc`, `steps step step-primary`, `badge badge-outline`,
`alert alert-success|error|warning|info`, `input input-bordered`, `select`, `textarea`, `checkbox`, `toggle`, `tabs tab`,
`table`, `modal` (works with `<dialog>`), `dropdown`, `drawer`, `toast`, `skeleton`, `loading loading-spinner`, `collapse`
(accordion), `timeline`, `menu`, `breadcrumbs`, `pagination (join)`. Use Tailwind utilities for layout around them
(`mx-auto max-w-4xl px-4 grid gap-4 sm:grid-cols-2`). Colour utilities use the theme (`bg-base-200 text-base-content text-primary`).
Gotchas: the audit may flag low contrast on built-in themes that are meant to be playful (synthwave, retro); choose a theme or
a brand theme that passes. Fields need a visible border (`input-bordered` or `input` in daisyUI 5, check the screenshot).
