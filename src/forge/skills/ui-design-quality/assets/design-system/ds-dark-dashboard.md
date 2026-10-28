---
id: ds-dark-dashboard
type: design-system
title: "Dark dashboard"
summary: "Near-black surfaces, light text, one indigo accent and clear status colours: dense and calm."
moods: [dark, dense, technical, calm]
products: [analytics, ops, monitoring, admin]
tags: [design-md, tokens, tailwind v4 export]
density: dense
dependencies: []
licence: original
source: "authored for DebCraft (D-350) from dir-dark-dashboard"
tested: "the DESIGN.md lints with no errors or warnings (design_md_lint) and a specimen picture was drawn and looked at (D-350)"
files:
  - from: recipes/design-systems/ds-dark-dashboard.design.md
    to: DESIGN.md
preview: assets/preview/ds-dark-dashboard-specimen.jpg
---
A complete design system in the DESIGN.md format: exact colours, type, radii, spacing and components with the reasoning. Add it with add_asset, then
adapt every value to the product (name, accent, fonts), run design_md_lint, and export the tokens with design_md_export. Do not use it unchanged for a
product it was not made for: a catalogue system is a starting point, and two products on the same file look like the same product.
