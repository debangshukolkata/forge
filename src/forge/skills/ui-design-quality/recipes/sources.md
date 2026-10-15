# External sources worth using, and the rules for using them

Prefer the recipes in this folder: they are tested and need no network. Use an external source when the task needs
more (a specific effect, a chart, a component set) and the network allows it (npm install asks the user to approve).
Never paste large blocks of someone else's code without checking its licence; install a package or copy-paste a
component that is explicitly meant to be copied, and keep its licence notice when the licence requires it.

## Safe to use (permissive licences; verify the LICENSE file of the exact package when it matters)
| Source | What it gives | Licence | How |
|---|---|---|---|
| shadcn/ui + Radix/Base UI | accessible primitives (dialog, tabs, select, popover, command, toast) styled with Tailwind | MIT | `npx shadcn@latest init`, `npx shadcn@latest add button dialog tabs` (components are copied into the project) |
| Motion (motion.dev, formerly Framer Motion) | spring physics, layout animations, gestures, scroll-linked values, exit animations | MIT | `npm i motion`, `import { motion } from "motion/react"` |
| Magic UI | 150+ animated components (marquee, bento grid, border beam, number ticker, animated list, shimmer button) | MIT | `npx shadcn@latest add "https://magicui.design/r/<name>"` or copy from magicui.design |
| daisyUI | semantic Tailwind classes (btn, card, modal, navbar) and 30+ themes; best fit for a Tailwind v4 app UI (tested quickstart and brand theme in component-libraries.md) | MIT | `npm i -D daisyui`, `@plugin "daisyui" { themes: ... }` in the CSS |
| MUI (Material UI) | big React component library (forms, grids, date pickers, autocomplete) in Material Design; must be re-themed hard (tested theme in component-libraries.md) | MIT core and MUI X community tier; MUI X Pro/Premium and Store templates are paid | `npm i @mui/material @emotion/react @emotion/styled` |
| Tabler (@tabler/core, @tabler/icons-react) | Bootstrap 5 admin dashboard kit with 120+ demo pages (use as layout references; do not mix Bootstrap into a Tailwind app) and about 5,000 consistent icons | MIT (its bundled ApexCharts has revenue-based paid terms: avoid it) | `npm i @tabler/icons-react` |
| opensourceui (bidyut10) | 200+ copy-paste React + Tailwind v4 components in 30 categories, same stack (lucide, TypeScript); quality not yet judged by us: look at the live preview before using | MIT | copy a component and the helpers it names (`lib/cn.ts`) from the repository |
| Uiverse Galaxy (uiverse-io/galaxy) | 3,000+ community micro-interactions (buttons, loaders, toggles, inputs, cards); quality varies, many are flashy: curate | MIT for the archive (the uiverse.io site's own terms were not readable; take elements from the MIT archive, keep attribution) | copy the HTML/CSS or Tailwind snippet, then restyle with the project's tokens |
| HyperUI | copy-paste Tailwind marketing and application blocks | MIT | copy from hyperui.dev |
| Flowbite (free part) | Tailwind components and blocks | MIT (Pro assets are paid: do not use) | `npm i flowbite` |
| Open Props | design tokens as CSS variables (colours, easings, shadows, sizes), pre-made keyframes | MIT | `npm i open-props`, `@import "open-props/style";` |
| Lucide, Tabler, Phosphor icons | thousands of SVG icons | ISC / MIT / MIT | `npm i lucide-react` (or `@tabler/icons-react`, `@phosphor-icons/react`) |
| Fontsource | self-hosted web fonts (Inter, Fraunces, Space Grotesk, Manrope, Plus Jakarta Sans...) | font licences OFL | `npm i @fontsource-variable/<name>` |
| Recharts, Chart.js, visx | charts | MIT | `npm i recharts` |
| Animate.css | ready CSS keyframes (fadeInUp, bounceIn) | MIT | `npm i animate.css` (or copy the keyframes you need) |
| AutoAnimate | one-line list add/remove/reorder animation | MIT | `npm i @formkit/auto-animate` |
| Lottie (lottie-web / dotLottie) | designer-made vector animations (files from LottieFiles carry their own licence: check each) | MIT (player) | `npm i @lottiefiles/dotlottie-react` |
| Three.js / react-three-fiber | 3D hero scenes; heavy: only when 3D is the point | MIT | `npm i three @react-three/fiber` |
| awesome-design-md (VoltAgent) | per-brand DESIGN.md design systems; use for inspiration/tokens when a brand feel is asked | MIT (brand identities remain their owners') | `web_fetch https://raw.githubusercontent.com/VoltAgent/awesome-design-md/main/design-md/<slug>/DESIGN.md` |
| taste-skill (Leonxlnx) | an opinionated anti-generic skill family; the user can install it with `forge skill add` | MIT | user's choice |
| MDN, web.dev, CSS-Tricks, Codrops, Smashing | reference and tutorials for any CSS/JS technique (`web_fetch` them when stuck) | read, do not copy wholesale | |

## Use with care or avoid
- **GSAP** (free "no charge" licence, not open source; barred for tools that compete with Webflow's visual builder): fine for
  a normal site; prefer CSS or Motion first; never ship it inside a no-code or template builder.
- **React Bits** (MIT with Commons Clause): look for ideas, do not copy its code into deliverables unless the licence is confirmed for the use.
- **Aceternity UI** (animated landing-page effects; its free components' terms are not stated on the site, its Pro licence allows end products for yourself or clients but not reselling the item or a template made from it) and **21st.dev** (a community catalogue: each
  component carries its own author's licence, which the site does not state; its terms forbid scraping and bots and ask for visible credit to the author; the free plan copies two components a day): never picked by the model. When the **user** chooses a component there and sends its install link, `add_ui_component` installs
  it with the shadcn CLI, records it in NOTICES.md, and you tell the user to check that author's licence and keep the credit before the site ships. Otherwise take the idea and write the effect with our own micro-effects (`find_asset` type effect).
- **Hover.css** (reports differ on commercial use): write the 3-line hover effect yourself.
- **Tailwind UI / Tailwind Plus, Pro kits, paid templates**: not open source. Do not reproduce.
- **Stock photos**: only from clearly licensed sources (Unsplash and Pexels licences allow use; credit is polite). In a
  throwaway demo use drawn SVG instead of hot-linking.
- Brand logos and trademarks: do not reproduce a company's identity. Use the feel, not the name or mark.

## Picking quickly
- Need accessible overlays/forms/menus: shadcn/ui (or the native components in components-native.tsx).
- Need motion beyond CSS: Motion for React; keep `motion.css` for ambient effects.
- Need a fast marketing page: take the structure from landing-reference.tsx, a section idea from HyperUI/Magic UI.
- Need 3D, maps, rich charts: install the specific library; budget the bundle size.
- Offline or locked-down network: everything in this folder works with no network except npm installs.

## Using the real Magic UI (when the network allows; not verified from the build machine)
- Install a component with the shadcn CLI: `npx shadcn@latest add "@magicui/<name>"` (or the `https://magicui.design/r/<name>`
  form in the table above). It copies the component source into `src/components/ui/`; it needs the project's `@/` path alias
  and the shadcn `components.json` (`npx shadcn@latest init` first).
- Its components are written for Next.js and React with Tailwind. In a Vite project check the alias in `vite.config` and
  `tsconfig`, and add the keyframes a component needs to the Tailwind v4 `@theme` block: a missing keyframe is the most
  common reason a copied component does nothing.
- Many components import `motion` (framer-motion) at runtime; the globe pulls in a 3D library. Check `package.json` size.
- Not all of its components honour `prefers-reduced-motion`; wrap the app in `<MotionConfig reducedMotion="user">` or turn the
  effect off with a media query.
- If the registry is unreachable (company network), use the offline effects in `motion.css`, `motion-more.css` and
  `motion-fancy.css` instead; they cover the same ideas without a dependency.
- Optional: the user can install Magic UI's own skill with `forge skill add https://github.com/magicuidesign/magicui`.
