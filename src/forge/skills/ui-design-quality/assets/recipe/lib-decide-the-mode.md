---
id: lib-decide-the-mode
type: recipe
title: "Decide the mode"
summary: "Component-library mode: decide the mode."
moods: [practical]
products: [internal tool, admin]
tags: [component library, daisyui, mui, shadcn, tabler, quickstart]
density: any
dependencies: []
licence: original
source: "authored for DebCraft (recipes/component-libraries.md, D-437)"
tested: "quickstarts were built and audited when the recipe was written (D-251, D-437); not re-run for this asset"
---

## Decide the mode
| The product is... | Use | Why |
|---|---|---|
| a marketing or brand-led page, campaign, portfolio | **Custom design** (recipes: index.css, landing-reference, style-directions) | identity matters more than speed |
| an app UI, internal tool, dashboard, admin, form-heavy flow on Tailwind | **daisyUI** (below) or **shadcn/ui** | fast, consistent, themeable, no extra styling engine |
| a data-heavy business app that needs grids, date pickers, autocomplete, charts | **MUI** (below) | the richest ready-made components; theme it hard |
| a Bootstrap codebase or an existing Tabler admin | **Tabler** (npm `@tabler/core`) | do not mix Bootstrap and Tailwind in one app |
| a Bootstrap codebase, or the user asks for a conventional, quick interface | **Bootstrap 5.3** (MIT; `npm i bootstrap`) | fast and consistent, the most familiar look; re-theme it through its CSS variables (`--bs-primary`, `--bs-body-font-family`, `--bs-border-radius`) or Sass variables and `data-bs-theme`; never ship the default blue, and never mix it with Tailwind in one app |
Whatever the mode: re-theme it (palette, type, radius, shadow), never ship a library's default look; run the audit and the
critic as usual; keep to one library per app.
