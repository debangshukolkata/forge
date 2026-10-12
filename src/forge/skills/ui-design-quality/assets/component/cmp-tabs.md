---
id: cmp-tabs
type: component
title: ARIA tabs
summary: "Keyboard-accessible tabs (arrow keys, Home and End) with proper roles."
moods: [clean, accessible]
products: [settings, dashboards, docs]
tags: [react, accessible, no dependency]
density: any
dependencies: [lucide-react]
licence: original
source: "authored for DebCraft (components-native.tsx, D-251)"
tested: built with Vite + Tailwind v4 and looked at; keyboard behaviour checked by hand (D-251)
files:
  - {from: recipes/components-native.tsx, to: src/components-native.tsx}
---

## ARIA tabs

`<Tabs tabs={[{id,label,content}]} />`. Style the active tab with an underline or filled pill from your tokens.

The whole file `components-native.tsx` is copied (the components share imports); delete the ones you do not use. Style them with the classes from index.css (btn-primary, card, field).
