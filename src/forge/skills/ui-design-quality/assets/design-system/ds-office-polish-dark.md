---
id: ds-office-polish-dark
type: design-system
title: "Office polish, dark"
summary: "Near-black blue page, raised dark cards with a hairline border, one light orange accent with dark text on filled controls, tinted status chips, Inter: the dark twin of Office polish."
moods: [businesslike, calm, polished, dark]
products: [back office, admin, crm, case management, operations, monitoring, erp]
tags: [design-md, tokens, tailwind v4 export]
density: balanced
dependencies: []
licence: original
source: "authored for DebCraft (D-350) from the office design (D-489) as its own dark token set, not overrides of the light one (BO7)"
tested: "the DESIGN.md lints with no errors or warnings (design_md_lint) and a specimen picture was drawn and looked at (D-350)"
files:
  - from: recipes/design-systems/ds-office-polish-dark.design.md
    to: DESIGN.md
---
A complete design system in the DESIGN.md format: exact colours, type, radii, spacing and components with the reasoning. Add it with add_asset, then
adapt every value to the product (name, accent, fonts), run design_md_lint, and export the tokens with design_md_export. Do not use it unchanged for a
product it was not made for: a catalogue system is a starting point, and two products on the same file look like the same product.
