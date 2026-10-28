---
id: lay-photo-led-story
type: section
title: "Composition: Photo-led story"
summary: "A page told in bands: a hero photograph to the page edge with the headline on its fade, a ruled facts strip with line icons, three product photographs, a dark band beside a photograph, a light band beside the shop front."
moods: [warm, appetising, editorial, calm]
products: [bakery, restaurant, cafe, shop, studio, hotel, farm]
tags: [plain html, css, composition, layout, photography, drawn svg stand-ins, no build step, light, dark band]
density: balanced
dependencies: []
licence: original
source: "authored for DebCraft (D-439, after the user's own Fernhill Bakery page)"
tested: "rendered in Edge at 1280 and 375 px: no sideways scroll, the style audit reports nothing apart from the placeholder drawings, looked at (tests/test_compositions.py, D-439)"
files:
  - from: recipes/compositions/photo-led-story.html
    to: compositions/photo-led-story.html
preview: assets/preview/lay-photo-led-story-desktop.jpg
---
A complete, working composition in plain HTML and CSS for a business whose product is seen: food, craft, a place. The story is the order of the bands: desire (the product to the
page edge, the headline on its fade), trust (hours, address, delivery with thin line icons, no boxes), exploration (three product photographs), craft (a dark band beside a photograph
that touches the band edges, once), invitation (the shop and one action). Each `data-slot` says what the real picture must show; replace every `<svg class="stand">` with an `<img>`
of that picture (the user's `brand-assets`, `generate_image`, `find_image`), same size, with alt text. Then change the words, replace the `:root` block with the tokens exported from
DESIGN.md (`design_md_export css-variables`) and link the fonts you fetched. The headline is set light; keep it. Use it as the layout of one candidate in `design_candidates`; do not
use it unchanged for a product it was not made for.
