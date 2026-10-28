---
id: lib-mui
type: recipe
title: "MUI"
summary: "Component-library mode: mui."
moods: [practical]
products: [internal tool, admin]
tags: [component library, daisyui, mui, shadcn, tabler, quickstart]
density: any
dependencies: []
licence: original
source: "authored for DebCraft (recipes/component-libraries.md, D-437)"
tested: "quickstarts were built and audited when the recipe was written (D-251, D-437); not re-run for this asset"
---

## MUI
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
