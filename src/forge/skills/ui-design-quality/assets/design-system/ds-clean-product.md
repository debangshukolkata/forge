---
id: ds-clean-product
type: design-system
title: "Clean product"
summary: "White and pale blue-grey, one saturated accent, navy text, layered soft shadows: confident B2B."
moods: [clean, confident, precise]
products: [b2b, fintech, dashboards, saas]
tags: [design-md, tokens, tailwind v4 export]
density: balanced
dependencies: []
licence: original
source: "authored for DebCraft (D-350) from dir-clean-product"
tested: "the DESIGN.md lints with no errors or warnings (design_md_lint) and a specimen picture was drawn and looked at (D-350)"
files:
  - from: recipes/design-systems/ds-clean-product.design.md
    to: DESIGN.md
preview: assets/preview/ds-clean-product-specimen.jpg
---
A complete design system in the DESIGN.md format: exact colours, type, radii, spacing and components with the reasoning. Add it with add_asset, then
adapt every value to the product (name, accent, fonts), run design_md_lint, and export the tokens with design_md_export. Do not use it unchanged for a
product it was not made for: a catalogue system is a starting point, and two products on the same file look like the same product.
