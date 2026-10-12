---
id: cmp-empty-state
type: component
title: Empty state
summary: "A designed empty state with an icon, a title, one sentence and an action."
moods: [friendly, clean]
products: [lists, dashboards, search]
tags: [react, accessible, no dependency]
density: any
dependencies: [lucide-react]
licence: original
source: "authored for DebCraft (components-native.tsx, D-251)"
tested: built with Vite + Tailwind v4 and looked at; keyboard behaviour checked by hand (D-251)
files:
  - {from: recipes/components-native.tsx, to: src/components-native.tsx}
---

## Empty state

`<EmptyState title text action />`; say what to do next, never just 'No data'.

The whole file `components-native.tsx` is copied (the components share imports); delete the ones you do not use. Style them with the classes from index.css (btn-primary, card, field).
