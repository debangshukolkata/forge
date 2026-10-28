---
id: lib-shadcn-ui
type: recipe
title: "shadcn/ui"
summary: "Component-library mode: shadcn/ui."
moods: [practical]
products: [internal tool, admin]
tags: [component library, daisyui, mui, shadcn, tabler, quickstart]
density: any
dependencies: []
licence: original
source: "authored for DebCraft (recipes/component-libraries.md, D-437)"
tested: "quickstarts were built and audited when the recipe was written (D-251, D-437); not re-run for this asset"
---

## shadcn/ui
**Call `shadcn_setup`** (project_dir, components such as `["button", "card", "input", "dialog"]`, base `radix` or `base`). It makes a Vite + React + TypeScript project if the
folder has none, installs Tailwind v4 and its Vite plugin, adds the `@/` alias to vite.config.ts and both tsconfig files, imports Tailwind in `src/index.css`, runs
`npx shadcn@latest init` and adds the components. Do not run `init` by hand in a fresh Vite project: it stops with "No Tailwind CSS configuration found" and "Could not find
valid path aliases" until those steps are done. It is safe to run again, and for a Next.js project run `npx shadcn@latest init` yourself. Later components:
`npx shadcn@latest add button card dialog tabs input form`. Components land in the project and are yours to restyle; theme through the CSS variables it writes.
Needs the network once; keep to `components-native.tsx` when offline. On a company network that inspects HTTPS the tool repeats a step that failed on a certificate
after DebCraft has exported the Windows certificates for Node; if a command still reports a certificate error, tell the user (their company root certificate is not in
the Windows store) and never turn certificate checking off.

Rules that keep a shadcn project clean (our own words, from the library's habits; they apply when the project already uses it):
- Use an existing component before writing custom markup: look in `components/ui` first, add the missing one with the CLI (`npx shadcn@latest add <name>`), and compose
  from it. Wrap, do not fork, unless the design needs a different structure.
- Colours are semantic tokens (`bg-primary`, `text-muted-foreground`, `border-border`), never raw palette classes such as `bg-blue-500`; the tokens are the CSS variables in the
  global stylesheet, and they are where the DESIGN.md colours go.
- Spacing between siblings with `gap-*` on a flex or grid parent, not `space-x-*`/`space-y-*`; equal width and height with `size-*`.
- A dialog, sheet or alert dialog always has a title (hidden with `sr-only` if the design has none) and a description; a form uses its field and label components, so labels
  and errors are connected to the inputs.
- Edit the project's existing global CSS file for tokens; do not create a second one. Preview what a registry change would do with `npx shadcn@latest add <name> --dry-run`
  (or `--diff`) and never overwrite a component the project changed without saying so.
- Never guess a registry: a third-party registry (`@name/component`) is used only when the user named it. If a certificate error remains after the automatic retry, tell the user
  what to do (see D-402 and the Node certificate line of `forge doctor`) and fall back to `components-native.tsx`.
- Re-theme before the first screen: the default zinc, neutral look is the generic default. Set the radius, the primary and the font from DESIGN.md, then check the page
  with `browser_screenshot`; a shadcn page that still looks stock has not been designed.
