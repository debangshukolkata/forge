---
id: lib-tabler
type: recipe
title: "Tabler"
summary: "Component-library mode: tabler."
moods: [practical]
products: [internal tool, admin]
tags: [component library, daisyui, mui, shadcn, tabler, quickstart]
density: any
dependencies: []
licence: original
source: "authored for DebCraft (recipes/component-libraries.md, D-437)"
tested: "quickstarts were built and audited when the recipe was written (D-251, D-437); not re-run for this asset"
---

## Tabler
Icons: `npm i @tabler/icons-react` (MIT, about 5,000 icons, consistent stroke): a good alternative to lucide. The Tabler dashboard
kit (`@tabler/core`, Bootstrap 5) is MIT: use its demo pages as layout references for dashboards and rebuild them in
Tailwind; do not mix its Bootstrap CSS into a Tailwind app. Its bundled ApexCharts has revenue-threshold paid terms: use
Recharts or Chart.js for charts.
