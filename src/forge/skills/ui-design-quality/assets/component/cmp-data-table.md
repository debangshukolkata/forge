---
id: cmp-data-table
type: component
title: "Sortable, searchable table"
summary: "A table with sortable columns, a search box, numeric alignment and an empty state."
moods: [clean, dense, technical]
products: [admin, dashboards, reports]
tags: [react, accessible, no dependency]
density: any
dependencies: [lucide-react]
licence: original
source: "authored for DebCraft (components-native.tsx, D-251)"
tested: built with Vite + Tailwind v4 and looked at; keyboard behaviour checked by hand (D-251)
files:
  - {from: recipes/components-native.tsx, to: src/components-native.tsx}
---

## Sortable, searchable table

`<DataTable rows columns />`; mark numeric columns `numeric: true` so they right-align with tabular figures.

The whole file `components-native.tsx` is copied (the components share imports); delete the ones you do not use. Style them with the classes from index.css (btn-primary, card, field).
