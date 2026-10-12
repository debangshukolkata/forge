---
name: ui-design-quality
description: Make every screen look and feel professionally designed, and prove it. Use whenever you create or change a page, screen, component or stylesheet, and whenever the user says the UI looks bad or asks to improve the UI or UX.
---
# Designing screens that look good, and checking them

Working code is not a finished screen. A page that works but looks like a raw HTML document is a failed task.
Aesthetics and ease of use are part of the requirement even when the user did not mention them.

## 0. Make sure the styles load before any design work
If a screenshot shows plain text, default blue links, grey buttons, no spacing, then the styling setup is broken and
no amount of class tweaking helps. Fix the setup first, then design.
- **Tailwind v4** (what `npm install tailwindcss` gives today): `npm i tailwindcss @tailwindcss/vite`; in
  `vite.config.ts` add `import tailwindcss from '@tailwindcss/vite'` and `plugins: [react(), tailwindcss()]`; in the
  CSS file that `main.tsx` imports, the first line is `@import "tailwindcss";`. No `tailwind.config.js` and no
  `@tailwind base;` lines in v4.
- **Tailwind v3**: `tailwind.config.js` with `content: ["./index.html", "./src/**/*.{js,ts,jsx,tsx}"]`, a
  `postcss.config.js` with tailwindcss and autoprefixer, and `@tailwind base; @tailwind components;
  @tailwind utilities;` in the CSS file. Never mix v3 syntax with a v4 install or the reverse.
- Proof: `browser_screenshot` runs a style audit; a BLOCKER line there means classes in the markup have no effect.
  You may not call a UI task done while it reports one.

## 1. Decide the design before writing markup (write it in 5 lines in your plan or the CSS file's top comment)
- **Purpose and tone** of the product (a blood donation drive: warm, trustworthy, urgent but calm).
- **Palette**: one accent colour (a real brand colour, not default blue), a neutral scale for text and surfaces,
  one semantic colour each for success, warning, error. Define them once as theme variables / Tailwind theme tokens.
- **Type**: one or two font families (load a good one such as Inter or a pairing, with a system fallback), a clear
  scale (for example 14 / 16 / 20 / 30 / 48), line-height 1.5 for body, 1.1-1.25 for large headings.
- **Spacing**: one scale (4, 8, 12, 16, 24, 32, 48, 64, 96). Sections get 64-96px of vertical space, cards 24px of
  padding, related items 8-16px apart. Never leave boxed items touching.
- **Radius, border, shadow**: pick one radius (8-16px) and one soft shadow style and reuse them everywhere.

## 2. Layout and hierarchy
- First screen: a hero with one clear headline, one sentence, one primary button and one secondary action, plus a
  visual (illustration, photo, gradient shape or icon art, never an empty box). A visitor must grasp the purpose
  in five seconds.
- Centre content in a container (`max-w-6xl mx-auto px-4 sm:px-6`), never full-bleed text lines longer than ~75
  characters (`max-w-prose`).
- Use grids and flex with `gap-*` for cards, stats and steps (3-up on desktop, stacked on a phone). Align edges.
- Typical sections for a product page: sticky nav with logo and a call-to-action, hero, key numbers, how it works
  (3 steps with icons), details (who/when/where), FAQ, final call-to-action, footer. Build the ones the product needs.
- Emphasis by size, weight and colour contrast, not by shouting. One primary button per view.
- Real content: write believable copy and numbers, never lorem ipsum, empty cards or "Target donations" with no
  value. If data is loading, show a skeleton; if there is none, an empty state that says what to do next.

## 3. Components that feel finished
- Buttons: padding `px-5 py-3`, rounded, filled primary and outlined secondary, hover, focus-visible ring,
  disabled and loading states. Links in text have a visible hover.
- Cards: surface colour, border or shadow, padding, consistent radius, hover lift only if clickable.
- Forms: visible labels, helper text, inline error messages next to the field, a success message, large tap
  targets (at least 44px), inputs with border, focus ring and sensible `type`/`autocomplete`.
- Icons: use an icon set (lucide-react or inline SVG), not emoji, at a consistent size and stroke width.
- Pills/badges: `inline-flex items-center gap-2 rounded-full px-3 py-1 text-sm`, spaced with `flex flex-wrap gap-3`.
- Motion: short (150-250ms) transitions on hover/focus and gentle entrance fades; respect `prefers-reduced-motion`.

## 4. UX and accessibility
- Each action gives feedback (loading, success, error); the user always knows where they are and what to do next.
- Contrast at least 4.5:1 for text (3:1 for large text); do not rely on colour alone; every image has `alt`;
  keyboard focus is visible; headings go in order (one h1).
- Responsive: design mobile first; check 375px, 768px and 1280px wide. No horizontal scroll at any width.
- Forms and flows: the shortest path to the main goal (for donation: pick slot, enter details, confirm), with
  validation messages in plain words and a confirmation screen.

## 5. The look-and-fix loop (mandatory for every screen you create or change)
1. Start the app, `browser_open` it, `browser_screenshot` (desktop width). Read the **style audit** in the result
   and fix every problem it lists.
2. `view_image` the screenshot and critique it honestly against sections 1-4: hierarchy, spacing, alignment,
   colour, type, empty areas, anything that looks like a default or a draft. Write down 3 concrete weaknesses.
3. Fix them in code, reload, screenshot again. Repeat until you would show it to a client. At least two passes for
   a new screen; stop only when the audit is clean and the weaknesses you can name are gone.
4. Repeat at phone width: `browser_screenshot` with `width: 375` (then `width: 1280` to switch back); the audit runs at that width too.
5. In the task_update `verification`, say what you looked at and what you improved ("audit clean at 1280 and 375;
   changed X, Y, Z after the first look").

When the user says the result looks bad: do not patch single classes. Re-read sections 0-2, redo the design
decisions, and rebuild the screen's structure and styles together.
