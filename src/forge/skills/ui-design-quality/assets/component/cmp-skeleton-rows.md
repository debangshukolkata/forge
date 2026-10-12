---
id: cmp-skeleton-rows
type: component
title: Skeleton rows
summary: Placeholder rows for tables and lists while data loads.
moods: [clean, calm]
products: [tables, lists]
tags: [react, accessible, no dependency]
density: any
dependencies: [lucide-react]
licence: original
source: "authored for DebCraft (components-native.tsx, D-251)"
tested: built with Vite + Tailwind v4 and looked at; keyboard behaviour checked by hand (D-251)
files:
  - {from: recipes/components-native.tsx, to: src/components-native.tsx}
---

## Skeleton rows

`<SkeletonRows rows={4} />`; uses the `.skeleton` class from the motion kit (asset `fx-skeleton`).

The whole file `components-native.tsx` is copied (the components share imports); delete the ones you do not use. Style them with the classes from index.css (btn-primary, card, field).
