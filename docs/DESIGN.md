# Forge UI design language (D-185)

Source: the Apple-style design.md the user supplied (2026-10-03), adapted for a developer tool. Where this file and the
original differ, this file wins. Tokens live in `ui-react/src/index.css`; shared pieces in `components/ui.tsx` and
`components/landing.tsx`.

## Principles
- The UI recedes; content and the chat come first. No decorative chrome: no gradients, no shadows, hairline borders.
- **One accent, blue, means "you can click this".** `--accent` #0066cc (dark: #2997ff); solid fills use `--action`
  (#0066cc / #0071e3) so white text stays readable. No second brand colour.
- Status colours are separate and only mean status: `ok` green, `danger` red, `warn` amber (`info` shares the accent blue).
  Success (done, added, targets met, green dots, passed checks) uses `ok`, never the accent.
- Surfaces: white cards on parchment (`--bg` #f5f5f7). Dark theme: near-black (`--bg` #161617, cards #272729). The landing
  screens alternate a light tile and a dark tile (`--tile` #272729 / #1d1d1f); the colour change is the divider.

## Type
- Inter (bundled, OFL) with JetBrains Mono for code. Weights 400 and 600 only; `font-medium` maps to 600.
- Landing screens: headline 34 px (48 px from 640 px up), weight 600, tracking -0.3 px; tagline 17 px / 1.47 / -0.37 px.
- Working screens (chat, run map, panels, forms): 14 px body, 12-13.5 px captions. Not 17 px: it is a dense tool.

## Shapes and motion
- Buttons are pills; primary is the solid blue, secondary/ghost are quiet. Press = `scale(0.95)`.
- Cards 18 px radius with a 1 px `--border`; inputs 8 px; search is a pill; chips and badges are pills.
- Top bar is frosted (`bg-surface/80` + backdrop blur). 150 ms colour transitions; reduced motion is respected.

## Not used from the original
Photography tiles, the product drop-shadow, the two-row Apple nav, the configurator chips and the store grid (no product
images in Forge). Hover is styled lightly because a desktop tool needs it, although the original documents none.

## Added by us (the original has none)
Dark theme; error, validation and check states (ok / warn / fail / running) for the login form and the coming environment
checks; the `ok` green token.
