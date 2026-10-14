---
id: ds-tpl-charity
type: design-system
title: "Charity and community (template palette)"
summary: "The palette and type of the charity landing template: warm paper, ink and one brave red."
moods: [warm, editorial, trustworthy]
products: [charity, health, community, events, education]
tags: [design-md, tokens, tailwind v4 export]
density: balanced
dependencies: []
licence: original
source: "authored for DebCraft (D-350) from the charity template (recipes/templates/charity)"
tested: "the DESIGN.md lints with no errors or warnings (design_md_lint) and a specimen picture was drawn and looked at (D-350)"
files:
  - from: recipes/design-systems/ds-tpl-charity.design.md
    to: DESIGN.md
---
A complete design system in the DESIGN.md format: exact colours, type, radii, spacing and components with the reasoning. Add it with add_asset, then
adapt every value to the product (name, accent, fonts), run design_md_lint, and export the tokens with design_md_export. Do not use it unchanged for a
product it was not made for: a catalogue system is a starting point, and two products on the same file look like the same product.
