---
id: lib-what-each-library-is-best-for-the-user-s-list-d-437-and
type: recipe
title: "What each library is best for (the user's list, D-437) and how DebCraft uses it"
summary: "Component-library mode: what each library is best for (the user's list, d-437) and how debcraft uses it."
moods: [practical]
products: [internal tool, admin]
tags: [component library, daisyui, mui, shadcn, tabler, quickstart]
density: any
dependencies: []
licence: original
source: "authored for DebCraft (recipes/component-libraries.md, D-437)"
tested: "quickstarts were built and audited when the recipe was written (D-251, D-437); not re-run for this asset"
---

## What each library is best for (the user's list, D-437) and how DebCraft uses it
| Library | Best use | In DebCraft |
|---|---|---|
| Bootstrap | fast, consistent, conventional interfaces | opt-in for internal tools or an existing Bootstrap codebase; the default look is the generic one, so re-theme it; not with Tailwind |
| shadcn/ui | customizable React applications | `shadcn_setup` sets up Vite, Tailwind v4 and the registry in one call; the preset sets the starting look, DESIGN.md tokens replace it |
| Aceternity UI | distinctive visual effects and animations | ideas, or a component the user chose and sent as a link (`add_ui_component`); free-component terms are not stated: check them |
| Magic UI | animated components and interactions | MIT: `add_ui_component` with `@magicui/<name>` (for example `@magicui/marquee`; verified end to end on a new project) |
| 21st.dev | discovering and reusing community components | the user browses and sends the install link; `add_ui_component` installs it; per-author licence and credit; no scraping or bots |
Magic UI and 21st.dev components are Tailwind and Motion based: add the dependency the CLI names, restyle with the project's tokens, and keep one accent. An animated effect is the single bold move of a page, spent once; the audit and the critic still judge the result.
