---
id: ds-tpl-portfolio
type: design-system
title: "Portfolio (template palette)"
summary: "The palette and type of the portfolio template: white, stone and ink with a Playfair display."
moods: [refined, editorial, quiet]
products: [portfolio, studio, photography, writing]
tags: [design-md, tokens, tailwind v4 export]
density: airy
dependencies: []
licence: original
source: "authored for DebCraft (D-350) from the portfolio template (recipes/templates/portfolio)"
tested: "the DESIGN.md lints with no errors or warnings (design_md_lint) and a specimen picture was drawn and looked at (D-350)"
files:
  - from: recipes/design-systems/ds-tpl-portfolio.design.md
    to: DESIGN.md
preview: assets/preview/ds-tpl-portfolio-specimen.jpg
---
A complete design system in the DESIGN.md format: exact colours, type, radii, spacing and components with the reasoning. Add it with add_asset, then
adapt every value to the product (name, accent, fonts), run design_md_lint, and export the tokens with design_md_export. Do not use it unchanged for a
product it was not made for: a catalogue system is a starting point, and two products on the same file look like the same product.
