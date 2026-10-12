---
id: cmp-toasts
type: component
title: Toast region
summary: "A live-region toast stack for success and error messages, replacing `alert()`."
moods: [clean, accessible]
products: [forms, dashboards, any app]
tags: [react, accessible, no dependency]
density: any
dependencies: [lucide-react]
licence: original
source: "authored for DebCraft (components-native.tsx, D-251)"
tested: built with Vite + Tailwind v4 and looked at; keyboard behaviour checked by hand (D-251)
files:
  - {from: recipes/components-native.tsx, to: src/components-native.tsx}
---

## Toast region

Keep `toasts` in state; render `<ToastRegion toasts dismiss />` once near the root. Tones: ok and error.

The whole file `components-native.tsx` is copied (the components share imports); delete the ones you do not use. Style them with the classes from index.css (btn-primary, card, field).
