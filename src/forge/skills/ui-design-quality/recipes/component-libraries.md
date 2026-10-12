# Component-library mode: when to use a library, and tested quickstarts

A library gives a weaker model good defaults (spacing, states, accessibility) so it composes instead of styling from
scratch. The price is a more generic look, so **decide the mode first** and write it in DESIGN.md.

## Decide the mode
| The product is... | Use | Why |
|---|---|---|
| a marketing or brand-led page, campaign, portfolio | **Custom design** (recipes: index.css, landing-reference, style-directions) | identity matters more than speed |
| an app UI, internal tool, dashboard, admin, form-heavy flow on Tailwind | **daisyUI** (below) or **shadcn/ui** | fast, consistent, themeable, no extra styling engine |
| a data-heavy business app that needs grids, date pickers, autocomplete, charts | **MUI** (below) | the richest ready-made components; theme it hard |
| a Bootstrap codebase or an existing Tabler admin | **Tabler** (npm `@tabler/core`) | do not mix Bootstrap and Tailwind in one app |
Whatever the mode: re-theme it (palette, type, radius, shadow), never ship a library's default look; run the audit and the
critic as usual; keep to one library per app.

## daisyUI v5 on Tailwind v4 (tested: builds, audit clean at 1280 and 375, console clean)
Install: `npm i tailwindcss @tailwindcss/vite` (see SKILL.md section 0) and `npm i -D daisyui`.
Built-in themes (pick a few; first is the default, `--prefersdark` follows the OS):
```css
@import "tailwindcss";
@plugin "daisyui" {
  themes: light --default, dark --prefersdark, cupcake, retro, forest, synthwave;
}
```
A brand theme (recommended: this is what stops it looking like daisyUI):
```css
@import "tailwindcss";
@plugin "daisyui" { themes: false; }
@plugin "daisyui/theme" {
  name: "brand"; default: true; color-scheme: light;
  --color-base-100: oklch(99% 0.004 60);  --color-base-200: oklch(96% 0.008 60);  --color-base-300: oklch(90% 0.012 60);
  --color-base-content: oklch(24% 0.02 40);
  --color-primary: oklch(50% 0.19 27);    --color-primary-content: oklch(98% 0.01 27);
  --color-secondary: oklch(42% 0.05 40);  --color-secondary-content: oklch(98% 0.01 40);
  --color-accent: oklch(70% 0.14 70);     --color-accent-content: oklch(22% 0.03 70);
  --color-neutral: oklch(27% 0.02 40);    --color-neutral-content: oklch(96% 0.01 40);
  --color-info: oklch(62% 0.13 240);      --color-info-content: oklch(98% 0.01 240);
  --color-success: oklch(60% 0.14 150);   --color-success-content: oklch(98% 0.01 150);
  --color-warning: oklch(80% 0.15 80);    --color-warning-content: oklch(25% 0.04 80);
  --color-error: oklch(58% 0.2 27);       --color-error-content: oklch(98% 0.01 27);
  --radius-selector: 1rem; --radius-field: 0.75rem; --radius-box: 1.25rem;
  --size-selector: 0.25rem; --size-field: 0.25rem; --border: 1px; --depth: 1; --noise: 0;
}
```
**Set the theme on `<html>`**, not on a wrapper div (a wrapper leaves a white strip below the content and misses the page
background): `document.documentElement.setAttribute("data-theme", name)`. Switch themes the same way and remember the choice.
Component classes (all semantic, no JavaScript): `btn btn-primary|secondary|accent|ghost|outline|sm|lg`, `card card-body card-title`,
`navbar`, `hero hero-content`, `stats stat stat-title stat-value stat-desc`, `steps step step-primary`, `badge badge-outline`,
`alert alert-success|error|warning|info`, `input input-bordered`, `select`, `textarea`, `checkbox`, `toggle`, `tabs tab`,
`table`, `modal` (works with `<dialog>`), `dropdown`, `drawer`, `toast`, `skeleton`, `loading loading-spinner`, `collapse`
(accordion), `timeline`, `menu`, `breadcrumbs`, `pagination (join)`. Use Tailwind utilities for layout around them
(`mx-auto max-w-4xl px-4 grid gap-4 sm:grid-cols-2`). Colour utilities use the theme (`bg-base-200 text-base-content text-primary`).
Gotchas: the audit may flag low contrast on built-in themes that are meant to be playful (synthwave, retro); choose a theme or
a brand theme that passes. Fields need a visible border (`input-bordered` or `input` in daisyUI 5, check the screenshot).

## MUI (Material UI) with a hard re-theme (tested: strict TypeScript build, audit clean, looks branded)
Install: `npm i @mui/material @emotion/react @emotion/styled @fontsource-variable/inter @fontsource-variable/fraunces`.
Wrap the app once, with `CssBaseline`, and import the fonts (bundled, so they render offline):
```tsx
// main.tsx
import { CssBaseline, ThemeProvider } from "@mui/material";
import "@fontsource-variable/inter"; import "@fontsource-variable/fraunces";
import { theme } from "./theme";
createRoot(root).render(<ThemeProvider theme={theme}><CssBaseline /><App /></ThemeProvider>);
```
```ts
// theme.ts: palette, type, shape, shadows and component defaults make it look like THIS product
import { createTheme } from "@mui/material/styles";
export const theme = createTheme({
  palette: { mode: "light", primary: { main: "#b91c1c", contrastText: "#fff" }, secondary: { main: "#5b4636" },
    background: { default: "#f5f1ed", paper: "#fffcfa" }, text: { primary: "#231d19", secondary: "#5d534b" }, divider: "#e5ddd5" },
  shape: { borderRadius: 14 },
  typography: { fontFamily: '"Inter Variable", "Segoe UI", system-ui, sans-serif',
    h1: { fontFamily: '"Fraunces Variable", Georgia, serif', fontWeight: 600, letterSpacing: "-0.02em" },
    h2: { fontFamily: '"Fraunces Variable", Georgia, serif', fontWeight: 600, letterSpacing: "-0.02em" },
    button: { textTransform: "none", fontWeight: 600 } },
  components: {
    MuiButton: { defaultProps: { disableElevation: true }, styleOverrides: { root: { borderRadius: 999, paddingInline: 24, paddingBlock: 10 } } },
    MuiCard: { defaultProps: { variant: "outlined" }, styleOverrides: { root: { borderRadius: 20 } } },
    MuiTextField: { defaultProps: { variant: "outlined", fullWidth: true } },
  },
});
```
Rules: layout with `Container`, `Stack`, `Box` and `sx`; in current MUI put system props such as `justifyContent` inside
`sx={{ ... }}` (as props they fail the strict TypeScript build). Use `AppBar position="sticky"` with a solid
background and a bottom border. Free: `@mui/material`, `@mui/icons-material`. MUI X (DataGrid, date pickers): the community
tier is MIT, the Pro and Premium tiers are paid: use only the community components. Avoid the paid MUI Store templates.
Material's default look (blue, Roboto, big shadows) is exactly what to remove with the theme above.

## shadcn/ui (copy-in components on Radix, MIT)
`npx shadcn@latest init` then `npx shadcn@latest add button card dialog tabs input form`. Components land in the project
and are yours to restyle; theme through the CSS variables it writes. Needs the network once; keep to `components-native.tsx` when offline.

## Tabler
Icons: `npm i @tabler/icons-react` (MIT, about 5,000 icons, consistent stroke): a good alternative to lucide. The Tabler dashboard
kit (`@tabler/core`, Bootstrap 5) is MIT: use its demo pages as layout references for dashboards and rebuild them in
Tailwind; do not mix its Bootstrap CSS into a Tailwind app. Its bundled ApexCharts has revenue-threshold paid terms: use
Recharts or Chart.js for charts.
