# Palettes, font pairings and layout ideas (pick one per product; do not reuse the reference's)

Choose by the product's mood, then write the choice at the top of the CSS file. Every palette is one accent scale,
one neutral scale, and semantic ok/warn/error. Check text contrast 4.5:1 before using a pair.

## Palettes (accent / neutral surfaces / text)
| Mood | Accent | Neutral surfaces | Text | Use for |
|---|---|---|---|---|
| Warm trust (health, charity) | #c62828 deep red, tint #fef2f2 | #faf8f6, #f3efeb | #1d1a17 | donation, clinic, NGO |
| Calm clinical | #0f766e teal, tint #f0fdfa | #f8fafc, #f1f5f9 | #0f172a | hospital, wellness, insurance |
| Bold campaign | #e11d48 rose + #111827 near-black | #ffffff, #f4f4f5 | #09090b | events, drives, sports |
| Modern product | #4f46e5 indigo, tint #eef2ff, subtle gradient to #7c3aed | #fafafa, #f4f4f5 | #18181b | SaaS, dashboards, dev tools |
| Fresh and friendly | #16a34a green, tint #f0fdf4 | #fafaf9, #f5f5f4 | #1c1917 | food, grocery, community |
| Premium editorial | #b45309 amber-brown + ink #1c1917 | #fbf9f4, #f3eee3 | #1c1917 | boutique, travel, magazine |
| Dark mode product | #818cf8 on #0b0d12 surfaces, borders #1f2330 | #0b0d12, #12151c | #e5e7eb | developer, analytics, media |

## Font pairings (Google Fonts; always keep a system fallback in the stack)
- Fraunces (display) + Inter: warm, human, trustworthy.
- Plus Jakarta Sans + Inter: friendly modern product.
- Space Grotesk + Inter: techy, confident, campaign posters.
- Playfair Display + Source Sans 3: premium editorial.
- Manrope alone (weights 400/600/800): clean, minimal, works for dashboards.
- Inter alone with tight tracking on big headings (-0.02em): Linear/Stripe-like neutrality.
The office laptop may have no internet: load the font with a `<link>` and keep a system stack fallback so the page
still looks designed without it.

## Type scale and rhythm
12 / 14 / 16 / 18 / 20 / 24 / 30 / 36 / 48 / 60 px. Body 16-18 with line-height 1.5-1.7; headings line-height
1.05-1.25. Spacing 4, 8, 12, 16, 24, 32, 48, 64, 96. Section padding 64-96 vertical. Cards 24 padding. Max content
width 1152 (max-w-6xl); reading text max-w-prose.

## Layout ideas (so variants of one page really differ)
- Split hero: text left, drawn visual or photo right (the reference).
- Centred hero: huge headline, subtext, one button, a wide product image or numbers strip below.
- Poster hero: full-bleed colour block, giant type over it, a countdown or date as the visual.
- Bento grid: unequal cards in a grid for features or stats instead of three equal columns.
- Timeline: vertical steps with a line and numbered markers for "how it works".
- Sticky side panel: the registration card stays in view while the long page scrolls.
- Dark band sections alternating with light for rhythm; one strongly coloured section as the focal call-to-action.

## Visual assets without images
Inline SVG shapes (circles, blobs, waves) in brand tints; gradient meshes (two radial-gradients on a base colour);
large numerals; lucide-react icons in tinted rounded squares; subtle grid or dot patterns via background-image;
avatar initials on coloured circles. Never an empty grey box.

## Other screens
- Dashboard: left nav or top tabs, KPI row (4 cards: big number, small label, trend chip), one main chart, a table
  with sticky header, row hover, sortable headers, search, pagination, and an empty state with a call to action.
- Form flow: one column, labels above, help text under, errors inline in the error colour, a progress bar for
  multi-step, a review step, a confirmation screen with the next step.
- Settings: grouped cards with a title and one-line description left, controls right; a save bar appears on change.
- Empty state: small illustration or icon, one sentence on what goes here, one primary button to add the first item.
- Loading: skeleton blocks the shape of the content (animate-pulse), not a spinner alone.
