---
id: ds-office-polish
type: design-system
title: "Office polish"
summary: "Cool off-white page, white cards with a hairline border and one soft shadow, one orange accent, tinted status chips with an inner ring, Inter: calm, finished back-office screens."
moods: [businesslike, calm, polished, light]
products: [back office, admin, crm, case management, government, operations, erp]
tags: [design-md, tokens, tailwind v4 export]
density: balanced
dependencies: []
licence: original
source: "authored for DebCraft (D-350) from the design philosophy of a user-owned back-office app (D-489)"
tested: "the DESIGN.md lints with no errors or warnings (design_md_lint) and a specimen picture was drawn and looked at (D-350)"
files:
  - from: recipes/design-systems/ds-office-polish.design.md
    to: DESIGN.md
---
A complete design system in the DESIGN.md format: exact colours, type, radii, spacing and components with the reasoning. Add it with add_asset, then
adapt every value to the product (name, accent, fonts), run design_md_lint, and export the tokens with design_md_export. Do not use it unchanged for a
product it was not made for: a catalogue system is a starting point, and two products on the same file look like the same product.
