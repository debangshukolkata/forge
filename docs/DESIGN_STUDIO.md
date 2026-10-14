# Design studio: how DebCraft makes designs (D-348 to D-350)

DebCraft designs apps and pages in three steps, from least to most outward-looking. Nothing here asks you for references first.

| Step | When | What happens | Tools |
|---|---|---|---|
| 1. Own design | always first | Reads the brief on five dials with evidence, starts from catalogue systems, writes 2-3 candidate DESIGN.md files that differ in at least three dimensions, the vision critic picks the best, tokens are exported to CSS, then the usual build, screenshot, audit and critic loop | `find_asset` (type `design-system`), `design_candidates`, `design_specimen`, `design_md_lint`, `design_md_export` |
| 2. Creative redo | you did not like it | New candidates that differ from the rejected one in at least three dimensions, your words kept as constraints, still no questions | `design_candidates` with `rejected` and `rejected_reason` |
| 3. References | the redo did not land, or you gave sources | Looks up 2-3 references on the web (or reads yours), shows a screenshot and one line each, and asks "like this one or that one?" | `web_search`, `design_inspire`, `design_md_import`, `design_md_from_project` |

## The DESIGN.md format
A project's design system is `DESIGN.md` in the open format of Google Labs (Apache-2.0): YAML tokens (colors, typography, rounded, spacing,
components, with `{colors.primary}` references) and prose sections. DebCraft reads, lints (contrast 4.5:1, references, units, section order, one-note
palettes), diffs and exports it (Tailwind v4 `@theme`, CSS variables, W3C design tokens, Tailwind v3 JSON). Our additions are tolerated by the format:
`dials` (density, variance, motion), Imagery, Responsive Behavior and Known Gaps sections. The code and DESIGN.md are kept in step by exporting the tokens
and by the token lint.

## Where files go
- The project's `DESIGN.md` in the project root; the exported theme in `src/theme.css` (or the path you give).
- Candidates in `.forge/candidates/<a|b|c>/DESIGN.md`, their specimen pictures beside them, and the record of rounds in `.forge/design-rounds.json`.
- Pictures and drafts of referenced pages in `.forge/inspiration/` (a screenshot, the read styles and a draft DESIGN.md per page).

## Supplying your own sources
- A DESIGN.md or brand guide (even free text) in the project, or one you point to: it is binding, steps 1 and 2 are skipped. `design_md_import` takes a file
  or ONE web address that you typed in your own message; a link DebCraft found itself is never fetched.
- Sites or screenshots: send the addresses or pictures; `design_inspire` and `analyze_reference_image` read them.
- What is taken from any reference: structure, token patterns and principles. Never logos, text, photographs or other brand assets. Page text is data, not
  instructions. Sources are recorded under Inspiration in DESIGN.md.

## What is bundled, and what is not
Bundled: 14 tokenised systems (our 11 visual directions and the palettes of the 3 templates), written for DebCraft (licence: original), each with a specimen
picture. Not bundled: any third-party design catalogue. The research of 2026-10-14 (shadcn.io/design, getdesign.md, designmd.directory,
getdesignsystem.io, agent-design.com: no stated licence for their design files, scraping prohibited or terms unclear; better-web-ui: a no-resale licence) means
their files are used only when you supply one. Ideas adopted from MIT or CC0 sources (OJO-Design-Skills: the style gate, dials, banned patterns;
superdesign-prompts: design-first specs) are written in our own words.

## Limits
- A specimen draws tokens, not the bold move of a real page: the winner is a starting point and the real hero decides.
- Fonts not installed on the computer show as fallbacks in specimens.
- Shape and depth rules that live in prose (hard shadows, glass blur) are not drawn.
- Not built yet: the machine-checked banned patterns and interaction-state checks (DS4), the benchmark of the three modes (DS5), CC0 prompts from superdesign-prompts.
