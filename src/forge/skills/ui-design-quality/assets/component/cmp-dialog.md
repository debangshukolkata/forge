---
id: cmp-dialog
type: component
title: Accessible dialog
summary: "A native `<dialog>` modal with focus trapping, Esc to close and a backdrop, no dependency."
moods: [clean, accessible]
products: [forms, confirmations, settings]
tags: [react, accessible, no dependency]
density: any
dependencies: [lucide-react]
licence: original
source: "authored for DebCraft (components-native.tsx, D-251)"
tested: built with Vite + Tailwind v4 and looked at; keyboard behaviour checked by hand (D-251)
files:
  - {from: recipes/components-native.tsx, to: src/components-native.tsx}
---

## Accessible dialog

`<Dialog open onClose title>`. Always give the dialog a title (it labels it for screen readers).

The whole file `components-native.tsx` is copied (the components share imports); delete the ones you do not use. Style them with the classes from index.css (btn-primary, card, field).
