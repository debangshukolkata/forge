# TODO — DebCraft (the single list of open work)

Status: `[ ]` not started · `[~]` in progress · `[x]` done. **Every open task lives in this file and nowhere else** (consolidated 2026-10-12 from this file, `docs/PPT_PARITY.md` and `docs/TODO_LATER.md`). Add new tasks here, in the group they belong to. The other two files keep only background, decisions and sizing, and point back here. Finished work is in the history at the end.

## Contents (open items per group)
- 0. Build order (read this first): **0 open**
- 1. Waiting on you (your actions and decisions): **11 open**
- 2. Design upgrades for apps DebCraft builds (D-245..D-252): **19 open**
- 3. Parallel work and speed: **14 open**
- 4. Presentations (match Claude's PowerPoint abilities): **41 open**
- 5. Platform, runtime and coding competency: **30 open**
- 6. Parked (not started; your choice when): **3 open**
- **Total open: 118**

## 0. Build order (read this first)
How to take the work up in the best order. Each phase says what it needs and when it is done. IDs refer to the items below (`D` design, `L` libraries, `X` parallel, `S` speed, `C` coding competency, `W` documents, `P0.x/P1.x/P2.x/P3.x` presentations). Do not start a later phase's big items before the earlier phase's measurements exist.

**Phase A, measure and unblock** (small; needs your rerun and two laptop checks)
- Your actions in section 1: rerun the three-design task, the two reachability checks (GitHub raw, shadcn and Magic UI registries).
- `S1` timing breakdown, `S2` speed benchmark, `D2` cost and time per UI task, `C17` scrubbed run report (so you can send a run for scoring), `C1` coding benchmark (it tells us how far DebCraft is from Claude's code quality and which of the C items helps most).
- Done when: one real run has a "where did the time go" summary, the rerun is scored with the seven-line rubric, and we know whether the critic's SHIP bar is right.

**Phase B, foundation for scaling assets** (before any large library work)
- `L0` asset catalogue, `find_design_asset` and `add_design_asset` tools, asset standard, licence ledger, retrieval test.
- Migrate the existing recipes (motion kit, components, style directions, palettes, CSS techniques, component libraries) to the standard.
- Done when: the retrieval test passes (at least 90 %) on the real model and the three existing recipe sets are in the catalogue with previews.

**Phase C, cheap process wins** (no new assets; each is a small, testable change; can run alongside B)
- `D1` write whole files, `L7` section-by-section build, `L8` token lint, `L9` auto-fixers, `D7` second look on REVISE, `D3` variants-differ check, `D4` design-concept step.
- **First, before any item that cites Superpowers or mattpocock/skills: `C18` detailed study of both repositories and the decision on what to take (writes `docs/SKILLS_STUDY.md`). Blocked until done: `C4`, `C6`, `C7`, `C10`, `C13`, `C16`, `C19`, `C20`, `C21`, `D7`, the builder protocol in `X2`.**
- Coding: `C2` automatic quality gates, `C4` code-review rubric and gate, `C6` test-first skill, `C8` library-API correctness, `C13` skill style rewrite and Gotchas loop, `C12` harness parity audit (build the gaps it finds after `C1` shows which matter), `C16` A/B experiment with the original Superpowers once `C1` exists.
- Done when: a second rerun shows fewer drifting pages and fewer audit findings per screen than the first.

**Phase D, content libraries** (needs Phase B; build in this order, because later ones depend on earlier ones)
1. `L3` fonts, offline (templates need them).
2. `L2` animation library, with `L6` Magic UI-inspired effects.
3. `L1` templates and sections (the largest; start with 2 or 3 directions end to end, then widen).
4. `L4`/`L5` component-library docs and tested quickstarts (daisyUI templates, shadcn, opensourceui, Uiverse curation).
5. `D5` real imagery (needs your licence decision), `D6` visual regression.
6. Coding assets, after `L0`: `C3` skill library, `C5` skeletons, `C7` debugging, `C10` tests that prove something.
- Every asset meets the acceptance bar in `L12`. Done when: the library holds the target counts (20+ templates, 40+ effects, 40+ font families) and the retrieval test still passes.

**Phase E, model effort and parallel work** (needs the Phase A measurements)
- `L11` design role, best-of-N, gpt-4o critic; `S3` cache check, `S4` lean context, `S5` fewer round trips, `S6` faster tools.
- Parallel in this order: `X1` critic parallel (unique screenshot names first), `X3` run_parallel, `X4` verifier and critic together, `X5` background installs, then `X2` builder subagents, then `X7` automatic parallel planning; `X6` is low priority.
- `C9` tests as the judge (after `X2` and `C1`), `C11` repository outline only if `C1` shows lost context.
- `S7` and `S8` only with your OK and a benchmark. Done when: the speed benchmark improves without quality loss.

**Phase F, presentations and documents** (a parallel track; reuses Phase B, the critic and the audit)
- P0 first (benchmark, laptop check), then P1.1-P1.8, then P2.1-P2.6 and P2.18, then P2.10-P2.12; decide the engine and rendering from the benchmark; P3 and the rest of P2 last.
- Reuse for decks: the asset catalogue and tools (slide templates, palettes, fonts), a slide critic that scores the contact sheet, and the same acceptance bar.
- Documents (section 4b): `W0` clean-room protocol first (small), then the shared pieces together with the presentation items they share (P1.1 contact sheet, P1.8 validator) as `W4`, then `W2` Excel and `W1` Word, then `W3` PDF, then `W5` benchmark. Do not start `W1` to `W3` before `W0` is written.

**Phase G, later (lowest priority; take up after A to F show what is still weak)**
- `D8` token plan, wireframe and cliché list in the design skill (reconcile the conflicts with our reference page first).
- `C14` skill A/B evaluation loop (it also measures every other skill and library, so pull it forward if the retrieval test in `L0` is not enough).
- `C15` server-lifecycle helper for the verifier's browser scripts.

**Rules for every item**
- Write the test first or with the change; run the module's tests, the full suite for broad changes.
- Record each decision in `docs/DECISIONS.md`; tick the item here and update the counts below.
- UI work: look at the screenshots before reporting done (the browser tests write them to `test-artifacts/`).
- Anything that trades quality for speed or cost is rejected (D-161).

## 1. Waiting on you (your actions and decisions)
Things only you can do or decide. Everything else below can be built without you.

- [ ] **Run `scripts/dev/import_orchestrix_azure.py`** to fill the Azure values in `.env` (D-019)
- [ ] **Gemini live check on the office laptop** (D-150, D-205): run `scripts/dev/gemini_smoke.py` and the drawer's Gemini test (never called live from the build machine); `view_video` waits for the video probe. Code and unit tests are done and pushed.
- [ ] Re-run the three-design task (`designs/design-a..c`, ports 5171-5173) on the office laptop and score the result with the seven-line rubric; tune the critic's SHIP bar from real runs (too lenient / too harsh)
- [ ] Check that `raw.githubusercontent.com` is reachable from the office laptop (brand DESIGN.md fetch); if blocked, bundle five or six starter DESIGN.md files in our own words
- [ ] **Check that the shadcn CLI and the shadcn/Magic UI registries are reachable from the office laptop**: run `npx shadcn@latest --version`, then `npx shadcn@latest add button` and `npx shadcn@latest add "@magicui/marquee"` in a scratch Vite project; if npm or `ui.shadcn.com` is blocked, say so and DebCraft keeps using `components-native.tsx` and the daisyUI quickstart offline (daisyUI needs only npm).
- [ ] Optional: user installs taste-skill with `forge skill add https://github.com/Leonxlnx/taste-skill` if they want its full rule set (conflicts: it bans Inter, serifs, Lucide)
- [ ] **Presentations, decision 1: design engine.** Keep improving the free-form element list (cheaper, built) or add the HTML/CSS design path (P3.1; more freedom, large). Recommendation: P1 helpers first, decide after the benchmark.
- [ ] **Presentations, decision 2: rendering without PowerPoint.** Optional LibreOffice (often needs admin rights), or our own renderer from the HTML path. Recommendation: optional LibreOffice plus PowerPoint as now.
- [ ] **Presentations, decision 3: icons and images.** A licensed icon set (Lucide ISC, Material Symbols Apache-2.0) and whether an image model exists on the Azure side; without one DebCraft can only use supplied pictures, shapes and charts.
- [ ] **Documents: order and samples.** Which first, Word, Excel or PDF (my suggestion: Excel and Word first, PDF toolkit third), and 3 to 5 sample documents you like or that are typical for your work (they become design targets and the benchmark reference, `W5`); allow the optional `docs` extra (python-docx, openpyxl, pypdf, reportlab) to be installed through pip.
- [ ] **Presentations, decision 4: reference decks.** Collect 5 to 10 decks you like (made by Claude or anyone); they become design targets and the benchmark reference (P0.1).

## 2. Design upgrades for apps DebCraft builds (D-245..D-252)
Goal: world-class UI/UX from a model that is not as strong as Claude, by giving it less to invent and more to adapt: Claude authors design assets offline and ships them in the skill folder. Build the libraries after your rerun shows what the model still gets wrong.


### 2a. Verify, tune and small additions
- [~] `D1` **(rule added to the skill, section 5b, 2026-10-13, D-257; the 'flag a file edited more than N times' check and the rerun to see if the prompt needs it are open)** Write each screen as complete files in one pass, patch only afterwards (many tiny edits make pages drift). Add the rule to the `ui-design-quality` skill and, if the rerun shows uneven pages, to the prompt; consider a check that flags a UI file edited more than N times
- [ ] `D2` Measure cost and time per UI task now that the critic can run several times; limit to one round for small edits if it is too slow
- [ ] `D3` Code-level check that design variants differ (compare screenshots / DESIGN.md directions automatically), beyond the pixel-identical guard
- [ ] `D4` A "design concept" step in the engine before the first UI edit (design read, dials, direction written down) enforced like the other gates, if the model skips it
- [ ] `D5` Real imagery: a way to get licensed photos or generated illustrations when SVG drawings are not enough (needs a source and a licence decision)
- [ ] `D6` Visual regression check: keep the approved screenshots per screen and flag unplanned visual changes after later edits
- [ ] `D7` Try an automatic second look: when the critic returns REVISE, give the builder the screenshot and the fixes together in one message **When the critic returns REVISE the builder checks each suggestion against the page before applying it** (screenshot and audit), instead of applying everything blindly; the critic's concrete fixes stay the default. **Do not start before `C18` (the detailed study of both repositories) is done.**

- [ ] `D8` **Token plan, wireframe and cliché list in `ui-design-quality` (lowest priority; idea from Anthropic's `frontend-design` skill, written in our own words; its licence text was not readable, so nothing is copied).** Before building, the model writes a compact token plan (4 to 6 named colours, type roles, layout as an ASCII wireframe, alignment, principles), reviews it against the brief, revises the generic parts, then builds. Add a named list of AI-design clichés to avoid (cream-and-terracotta palettes, near-black with acid green, hairline broadsheet layouts, identical rounded card grids, eyebrow labels, middle-dot meta strings, arrows on links, accenting one headline word) and the rules "spend your boldness in one place", "visual structure is information" (numbers, borders and dividers only when they encode something real) and error copy that says what happened and how to fix it. **First reconcile the conflicts with our own references**: `recipes/landing-reference.tsx` and `index.css` use an all-caps eyebrow label and a warm off-white with a deep red accent, which that list calls clichés; decide which rules we adopt, then change the reference page and re-audit it (clean at 1280 and 375 px) so the recipes and the rules agree. Measure with the retrieval and A/B evaluation in `C14`.

### 2b. Libraries and workarounds for a weaker model
- [~] `L0` **(slice 1 built 2026-10-13, D-265: standard, validated catalogue, `find_asset`/`add_asset`, licence ledger, 32 assets migrated (11 directions, 15 effects, 6 components), deterministic retrieval test at 100 %. Open: previews (screenshots) per asset, splitting the big skill into routing skills (e), the live retrieval test with the real model (g), migrating palettes, CSS techniques and component-library notes, and generalising to coding assets)** **Asset catalogue, search and copy tools: the foundation for all libraries (agreed 2026-10-12).** Today a skill is one line in the model's context, `load_skill` lists at most 60 files and there is no search, so hundreds of assets would be invisible and the model would build from memory. Build: (a) an **asset standard** (design and coding assets alike, see C3 and C5): every template, section, effect, font pairing, component recipe, coding recipe and project skeleton is a file with front-matter (id, type, title, moods, product types, density, direction, dependencies, licence and source, size, preview image) and its own tested usage note; (b) a generated **catalogue** (`catalogue.json` plus a short `INDEX.md` per category) built by a script that validates the front-matter and fails on a missing licence, missing preview or dependency not in `package.json` terms; previews are screenshots taken by the same script (this is also the 'reference screenshots' item); (c) a **`find_design_asset` tool** (deterministic keyword/tag search, optionally filtered by type, mood, dependency-free, returns the best 3 to 5 with one-line descriptions and sizes, no model call); (d) an **`add_design_asset` tool** that copies the chosen file and its declared dependencies into the project (through the write jail), records the licence in the project's notices, and tells the model what to adapt; (e) split the one big skill into a few short routing skills (design basics, motion, fonts, templates and sections) so the always-loaded index stays small, and raise the 60-file listing cap or replace it with the catalogue pointer; (f) a **licence ledger** `recipes/LICENSES.md` generated from the front-matter; (g) a **retrieval test**: about 20 realistic prompts, each with the asset(s) we expect, run against the real model (`@pytest.mark.live`); target: the right asset is found and added in at least 90 % of the prompts, re-run whenever the library grows. Needs nothing from the user. Done when the retrieval test passes and the three existing recipe sets (motion, components, directions) are migrated to the standard.
- [ ] `L1` **(harness built 2026-10-13: `tests/vite_harness.py` builds a throwaway Vite + React + Tailwind v4 project from files using the packages already in ui-react/node_modules, type-checks it, builds it and audits it at 1280 and 375 px; the existing reference landing page passes through it. Next: write the sections and templates and test each through it)** **Template and section library, many choices.** Not 6-8 pages: 20+ complete tested page templates across 10+ visual directions (landing, dashboard, form flow, pricing, portfolio, docs, e-commerce, admin, event/campaign, onboarding, settings), built from a composable **section library** so choices multiply: 10+ hero variants, 8+ feature layouts, stats/steps/timeline/bento variants, 6+ form patterns, nav and footer variants, testimonial, FAQ, pricing, CTA bands. The model picks a direction and sections, supplies tokens and content, and adapts. Each template and section is built with Vite + Tailwind v4, passes the audit at 1280 and 375, and is looked at before it ships. Keep an index (`recipes/INDEX.md`) so the model can choose by mood, product type and density. **Needs L0 (catalogue and tools), L3 (fonts) and L2 (motion). Each template and section follows the asset standard.**
- [~] `L2` **(51 effects built 2026-10-13, D-269: the 15 of the first kit plus 36 new pure-CSS ones in `motion-more.css`, all catalogue assets, one Edge demo page checks every class, no console errors, reduced motion off. Open: React hooks for split-text/scramble/magnetic/number ticker/pinned sections, shared-element and route transitions, a screenshot preview per effect, the per-intensity effect budget table)** **Bigger animation library.** Grow `motion.css` / `motion.tsx` from ~15 to 40+ effects, grouped by purpose: entrances (fade, slide, scale, blur-in, clip-reveal, split-text word/letter stagger), scroll (progress bar, parallax layers, sticky stack, horizontal pan, pinned steps, number tickers), hover (magnetic button, glow follow, image zoom-pan, underline variants, icon nudges), ambient (aurora, gradient mesh, floating shapes, particles-lite, grid pulse, marquee variants), feedback (toast, success check draw, error shake, skeleton, progress ring), page (view transitions, shared-element morph, route fade), 3D-lite (tilt, card flip, cube hero, perspective stack), text (typewriter, gradient sweep, scramble, highlight marker). All pure CSS or tiny hooks, reduced-motion safe, one demo page per group verified in Edge (no console errors, audit clean). Document an effect budget per MOTION_INTENSITY level. **Follows the asset standard in L0; each effect gets a catalogue entry and a preview.**
- [~] `L3` **(first slice built 2026-10-13, D-268: 14 families bundled as variable woff2 (0.7 MB of the 1.5 MB budget), 12 pairings by mood, offline render test in Edge. Open: grow to 40+ families through the `npm i @fontsource-variable/<name>` command route, the audit warning when a page still renders in a fallback font, Bengali/Hindi pairing previews)** **Many fonts, offline.** A curated catalogue of 40+ font families with licence OFL/Apache only (display, serif, sans, rounded, mono, handwriting, condensed, slab; Latin plus Devanagari/Bengali options for Indian-language pages such as Noto Sans Bengali, Hind, Baloo), each with ready-made pairings by mood, size and weight guidance. Ship the woff2 files for the most used 12-15 inside the package (so a laptop with no internet still looks designed; check licences and size) and give the install command (`npm i @fontsource-variable/<name>`) for the rest; a `fonts.md` index plus a tested `@font-face`/Fontsource snippet per family. Audit check: warn when a page still renders in a fallback font. **Follows the asset standard in L0; decide the bundled-file size budget first (about 12-15 families).**
- [ ] `L4` **Component-library mode and sources (agreed 2026-10-12).** Done: decision guide plus tested daisyUI v5 (built-in and brand themes), MUI hard re-theme, shadcn/ui and Tabler notes in `recipes/component-libraries.md`; sources listed in `recipes/sources.md`. Open: (a) look at opensourceui's live previews and decide whether it feeds the section library (MIT notice kept); (b) curate about 40 Uiverse Galaxy micro-interactions (loaders, toggles, buttons, inputs, cards) into the animation library with attribution, restyled with tokens; (c) a Tabler-inspired dashboard template in Tailwind for the template library; (d) offer Tabler Icons beside lucide; (e) confirm the licence file of each package we recommend at the time of use; (f) a daisyUI-based template per theme family in the template library.
- [ ] `L5` **shadcn/ui quickstart and rules (agreed 2026-10-12).** (a) Build and test a shadcn quickstart for Vite + Tailwind v4 in `recipes/component-libraries.md`: `init`, add a handful of components (button, card, dialog, tabs, input, form), theme through its CSS variables from the project's DESIGN.md tokens, one dashboard block; run the audit and look at it. (b) Distil the useful rules of its agent skill into our `ui-design-quality` skill in our own words (do not copy the 3,000-word skill): use existing components before custom markup, semantic colour tokens never raw `bg-blue-500`, `gap-*` not `space-*`, `size-*` for equal sides, dialogs need titles, forms use field groups, edit the existing global CSS file instead of creating a new one, preview registry updates with `--dry-run`/`--diff`, never overwrite without approval, do not guess a registry. (c) Add a re-theme step so the default zinc look never ships. (d) Keep `components-native.tsx` as the offline fallback when the registry cannot be reached. (e) Optional: the user installs shadcn's own skill with `forge skill add https://github.com/shadcn-ui/ui` (the `skills/shadcn` folder) if the network allows; it is long and assumes the CLI. (f) Consider shadcn blocks (dashboards, sidebars, auth pages) as pattern sources for the template library.
- [~] `L6` **(parts a to c built 2026-10-13, D-270: eight showpiece effects in `motion-fancy.css` (orbiting circles, rainbow and shiny buttons, flickering grid, sparkles, warp, dock, avatar stack), notes on the real Magic UI in sources.md, customisation rules in the skill. Open: animated beam between two elements, particles-lite and globe-lite (need JavaScript or canvas), (d) verifying real Magic UI components in Vite plus Tailwind v4, which needs the registry reachable on the office laptop)** **Magic UI (agreed 2026-10-12; MIT, ~22k stars, registry via the shadcn CLI).** (a) Write our own CSS and hook versions, in our own words, of the effects we lack, inspired by its catalogue, and add them to `motion.css` / `motion.tsx` (offline, light, reduced-motion safe): word/letter text animation (text-animate, word-rotate, sparkles), blur-fade, animated grid and dot patterns, flickering grid, particles-lite, animated beam between elements, orbiting circles, dock, magic-card and bento-grid variants, number ticker, avatar circles, globe-lite (SVG/canvas) and warp background; shiny/rainbow button variants. (b) Document how to use the real Magic UI when the network allows: `npx shadcn@latest add "@magicui/<name>"`, the Tailwind v4 keyframes it needs in `@theme` (missing keyframes is its most common failure), the `@/` alias, and a reduced-motion wrapper (`MotionConfig reducedMotion="user"`) since its components do not all honour `prefers-reduced-motion`; note the extra runtime dependency (framer-motion/motion) and that the globe pulls in a 3D library. (c) Add its customisation rules to the skill in our own words: start with one core component and one supporting effect, never stack many high-motion effects in one viewport, customise through props and `className` instead of editing internals, check semantic HTML and keyboard access, verify mobile overflow. (d) Verify the pieces in a Vite + Tailwind v4 project (it is Next.js-first) with the audit and a screenshot before documenting them. (e) Optional: the user installs its own skill with `forge skill add https://github.com/magicuidesign/magicui` (the `skills/magic-ui` folder; it assumes the shadcn CLI and the network).
- [x] `L7` **(done 2026-10-13 as skill section 5b, D-257)** **Section-by-section build process.** Plan, then tokens (DESIGN.md), then one section at a time written whole, each with audit and screenshot, then assemble; stops the many-small-patches drift.
- [x] `L8` **(done 2026-10-13, D-260)** **Token lint.** Static check that flags hard-coded colours, font families and off-scale spacing not defined in DESIGN.md/the theme; shown in the screenshot audit.
- [~] `L9` **(contrast part done 2026-10-13, D-263: the audit names the nearest passing colour; overflow and missing-alt fixers open)** **Auto-fixers.** Contrast fixer (adjusts a colour until AA), overflow fixer, missing-alt fixer; the model reviews the diff instead of finding the problem itself.
- [ ] `L10` **Reference screenshots.** A screenshot per direction and per template so the model can match an image (it has vision); also let the user supply a screenshot of a site they like and extract palette, type and spacing from it. **Folded into L0: previews are generated by the catalogue script; keep this item only for the user-supplied-screenshot extraction.**
- [ ] `L11` **More model effort where it counts.** A separate design role with the highest reasoning effort; best-of-N candidates ranked by audit score plus critic; use the gpt-4o fallback as the critic so a different model reviews the builder's work (check the role config supports it). **Needs a real-run score first (D2, S2) so the effect is measured; the gpt-4o critic needs the role config to allow a different critic model.**
- [ ] `L12` **Claude authors offline.** Schedule sessions where Claude writes and tests the templates, sections, effects and font packs here and they ship in the repo; track licence notes per asset in `recipes/LICENSES.md`. **Every asset Claude writes must meet the asset standard in L0 and the acceptance bar: built with Vite + Tailwind v4, audit clean at 1280 and 375 px, screenshot reviewed, licence recorded, catalogue entry and preview present.**

## 3. Parallel work and speed
Today: consecutive read-only tool calls and `explore`/`reviewer` subagents (max 4) run in parallel (D-175); everything else is sequential. Measure first on your rerun: where does the wall time go?

### 3a. Parallel work
- [x] `X1` **(done 2026-10-13, D-256)** **Allow `design-critic` in `PARALLEL_SUBAGENT_TYPES`** (it only looks and screenshots). First make screenshot file names unique (timestamp to the second can collide when two critics shoot in the same second).
- [ ] `X2` **Parallel builder subagents** for independent folders or screens (for example the three design variants): a `builder` agent type with `write_only_under=<its folder>`, its own port, a shared-nothing rule, and a short report back; the parent verifies each result (audit, critic, tests) before it counts. Watch: concurrent `npm install` and approval prompts (queue approvals, one prompt at a time), Azure rate limits (429 retry exists; add a concurrency cap tied to the limit), shared files (package.json at the root, lock files), CPU. **Needs S1 (timing) to show it pays off, X1 and X3 first, and a queue for approval prompts.** **Protocol to use** (Idea from obra/superpowers, MIT, ~298k stars; no outcome data published, so measure on `C1`; write in our own words.): each builder gets a task brief file and a report-file path (artifacts pass as files, not pasted text) and only the context its task needs; it ends with DONE, DONE_WITH_CONCERNS, NEEDS_CONTEXT or BLOCKED, each with a defined response and never a blind retry; a reviewer returns spec and quality verdicts; a fix loop of at most five rounds, rounds 1 to 3 resume the same builder and rounds 4 and 5 use a fresh builder on the stronger model (the gpt-4o fallback or the best deployment); after round five a breaker step records a ruling for each open finding; a git-ignored ledger file records progress so the work survives compaction; the controller never fixes code itself. Parallel builders are allowed only in disjoint folders under the write jail (their skill forbids parallel implementers because of conflicts; ours avoids them by construction). **Do not start before `C18` (the detailed study of both repositories) is done.**
- [x] `X3` **(done 2026-10-13 on your go-ahead, D-271, option 1)** Consecutive `run_command` calls that only check or read (ruff, mypy, pyright, eslint, tsc, one pytest run, ls/cat/grep, `--check` formatters) run side by side, at most four, each still through the permission gate and sandbox; approval cards are asked one at a time; installs, builds, git, chained or redirected commands run alone.
- [ ] `X4` **Verifier and design critic together** on the same finished app (different ports or the same read-only app; the verifier may start it, so start it once first and pass the URL to both).
- [~] `X5` **(prompt hint added to both system prompts 2026-10-13, D-257; measuring the saving waits for S1/S2)** Start installs and scaffolding in the background** (`start_background` / `monitor`) while the model writes DESIGN.md or plans; add the hint to the prompt and the skill.
- [ ] `X6` **Two screenshots at once** (375 and 1280, several pages) with separate browser pages; small gain, low priority.
- [ ] `X7` **Automatic parallel planning.** From the user's request Forge decides what can run in parallel and runs it: (1) a planning step turns the request into a task graph: tasks, dependencies, what each task writes (folders or files), shared resources it needs (ports, database schema, npm cache, a package.json); (2) a scheduler marks tasks independent only when their write scopes are disjoint and they share no exclusive resource, and starts them as workers (subagents with a write jail) up to a concurrency cap, with approvals queued and one-at-a-time; (3) dependent tasks wait; (4) an integration step merges and verifies the whole (tests, build, audit, critic); (5) the Run map shows the parallel branches, cost and time per worker; (6) a safe fallback: any overlap, failure or rate-limit pressure serialises the rest and says why. Start conservative: only clear independent parts of one request (several variants, screens, services, documents, research questions), never edits to the same file. Record decisions and measured speed-ups; keep an off switch in `config.yaml`. **Needs X2 and S1; start conservative.** **Also (mattpocock/skills, `to-tickets`, `implement-spec`): represent the plan as blocking-aware tasks (which task blocks which) and run unblocked ones in parallel; one branch of work per spec.** **Do not start before `C18` (the detailed study of both repositories) is done.**


### 3b. Make DebCraft develop faster (agreed 2026-10-12)
Start by measuring: guess nothing. Related items elsewhere (not repeated here): the template, section, animation and font libraries in 2b make the model write less; "write each screen as complete files" in 2a cuts round trips; "Unattended runs" in section 5 removes waits for approvals.
- [~] `S1` **(engine and `forge log-summary` done 2026-10-13, D-258: model time, tool time, and waiting for you are now separate, `waited_s` is in the event; open: show it in the Run map and the end-of-run summary in the UI, and per-agent splits)** **Timing breakdown per run (do this first).** Record, per step and per agent, the time spent in model calls (time to first token and total), in tools (by tool name) and waiting for the user (questions, approvals); show it in the Run map next to the cost and as a short "where did the time go" summary at the end of a run. Add it to the events so reopened projects show it too.
- [ ] `S2` **Speed benchmark.** A few fixed tasks (the three-design task, a small CRUD app, a redesign of a bad page, a dependency install) timed before and after every speed change; results in `docs/SPEED_BENCHMARK.md`. A speed change that costs quality is rejected (D-161).
- [ ] `S3` **Prompt-cache check.** **First data point (2026-10-13, smoke run of benchmark task t01, 12 calls): 77 % of input tokens were cached; call 5 of 12 had 0 cached tokens although calls 4 and 6 had 17k and 18k, so something in the prefix changed or the cache was evicted once. The first call took 47 s (45 s to the first token, planning with `propose_plan`), a third of the whole 146 s run, for a 40-line module. Questions this raises: is the plan step worth 45 s on a one-function task, and what changed between calls 4 and 5?** DebCraft already records cached input tokens and keeps the changing block at the end of the prompt; measure the real hit rate on a long run, and check whether trimming old tool outputs or compaction in the middle of the history breaks the cached prefix too often (batch such changes, or trim from the oldest end only).
- [ ] `S4` **Keep the context lean.** Compact earlier where the timing data says long contexts slow the calls; cap tool output sizes; keep noisy work (search, logs, test output) in subagents; check what fills the window at 60% (one run showed 110 trimmed tool outputs).
- [~] `S5` **(prompt hint added 2026-10-13, D-257; the before/after count of model calls waits for S1/S2)** Fewer model round trips. Tell the model (prompt and skills) to put several independent tool calls in one turn, write whole files, and run related checks together; measure the number of model calls per task before and after.
- [ ] `S6` **Faster tools.** `npm install` with `--prefer-offline` and a shared cache folder (check the sandbox cache variables, D-223); downscale images before `view_image` (one call took 17 s); audit only the screens that changed; run only the affected tests while iterating and the full suite once at the end; start dev servers once and reuse them; measure the sandbox start-up cost per command.
- [ ] `S7` **Faster model for read-only subagents (needs your OK).** Use a smaller, faster deployment for explore and similar read-only agents. D-161 forbids trading quality for cost; this would be a speed trade only, so it needs your decision and a quality check on the benchmark. **Needs S2 (benchmark).**
- [ ] `S8` **Adaptive reasoning effort (needs your OK).** Lower effort for mechanical steps (file moves, installs, formatting) and the highest for planning and design; adopt only if the benchmark shows no quality loss (D-161: no low effort for convenience). **Needs S2 (benchmark).**

## 4. Presentations (match Claude's PowerPoint abilities)
Goal (2026-10-09): presentations the way Claude makes them, equivalent capability and quality (not identical files; we cannot copy Anthropic's skill, its licence forbids it). Background, the done list (D-240..D-242), the licence note and the suggested order are in `docs/PPT_PARITY.md`. Suggested order: P0 (measure) -> P1.1-P1.8 -> P2.1-P2.6 and P2.18 -> P2.10-P2.12 -> decide engine and rendering from the benchmark -> P3 and the rest of P2. Rough effort: P1 2-3 days, P2 3-4 weeks, P3 2-3 weeks. The web-design approach applies here too: a themed slide template library, a slide critic that scores the contact sheet, an audit, curated fonts and palettes, reference decks.

### P0 Measure first
- [ ] **P0.1 Parity benchmark.** 20 to 30 fixed requests across kinds (status update, pitch, training, data story, technical design
  review, template fill, edit-an-existing-deck, redesign-a-bad-deck, long deck, deck from a document). Each has a checklist
  (story, hierarchy, contrast, alignment, no overflow, file opens cleanly, notes present, charts native) scored by the real model
  as judge looking at the rendered slides, plus the user's own ratings of a sample. Re-run after every change; record scores in
  `docs/PPT_BENCHMARK.md`. Size M. Needs decision 4.
- [ ] **P0.2 Verify on the office laptop** (user action): python-pptx installs through pip; PowerPoint picture export works under company
  policy and Protected View; `Start-DebCraft.cmd` installs the `slides` extra. Size S.

### P1 Quick wins
- [ ] **P1.1 Contact sheet.** One picture of all slides in a grid (like Claude's thumbnail tool) so the model judges flow and
  consistency in one look instead of N calls. Size S.
- [ ] **P1.2 Show slides in the web UI.** After a build or edit, show the slide pictures inline in the chat and a slide viewer in the Files tab
  (download button for the .pptx). The user currently only gets file names. Size M.
- [ ] **P1.3 Layout helpers for free-form.** Row, column and grid containers (equal widths, gaps, alignment) so the model states intent
  ("three equal cards, 0.4 gap") instead of computing coordinates; fewer collisions. Size M.
- [ ] **P1.4 Rich text.** Mixed bold, colour and size inside one paragraph, links, line and letter spacing, vertical text. Size M.
- [ ] **P1.5 Fix our own template habits that look generic.** Remove the accent bar under titles, stop defaulting to one blue, vary
  layouts, give every slide a visual element, use dark/light "sandwich" structure; make `make-presentation` say so and the checks
  warn (same layout repeated, text-only slide, accent line). Size S.
- [ ] **P1.6 Title lint.** Warn when a title is a topic ("Search") instead of a takeaway ("Search is 4x faster"); count words. Size S.
- [ ] **P1.7 Safe fonts.** Prefer fonts that exist everywhere (Arial, Calibri, Cambria, Times New Roman, Courier New, Bookman, Century
  Schoolbook), warn on others, and say which fonts' fit estimates are unreliable. Our default Segoe UI / Georgia need review. Size S.
- [ ] **P1.8 Package validator.** Check a finished .pptx for faults PowerPoint refuses to open (bad chart XML, wrong element order,
  broken relationships, duplicate ids) and name the fix. Write our own validator from the OOXML spec; run it after every build and
  edit. Size M. This is what makes "opens cleanly" a guarantee.

### P2 Capability gaps
- [ ] **P2.1 Colour and type system.** 15+ curated palettes chosen from the topic (not blue by default), dominance rule (one main colour,
  one accent), font pairings, user brand kits (logo, colours, fonts) saved with the project. Size M.
- [ ] **P2.2 Gradients, shadows, transparency, background images** in free-form, plus rounded image frames, circles, masks. Size M.
- [ ] **P2.3 Icons.** An icon set turned into pictures or native shapes, placed in coloured circles, sized and recoloured. Needs decision 3. Size M.
- [ ] **P2.4 Charts to full strength.** Stacked, area, scatter, donut, combo with a second axis, data-label formats, axis titles, per-point
  colours, legends, number formats, quiet styling by default; charts straight from CSV/Excel data. Size M.
- [ ] **P2.5 Tables to full strength.** Merged cells, widths, borders, per-cell fill/bold/alignment, heat-map colouring, long-table splitting. Size M.
- [ ] **P2.6 Diagram toolkit.** Connectors that stay attached to shapes (straight and elbow), grouping, align and distribute operations,
  ready recipes (process, cycle, hierarchy, 2x2 matrix, timeline, funnel, roadmap). Size M.
- [ ] **P2.7 Real masters and theme.** Generate proper slide masters, layouts, placeholders, footer and slide-number fields and theme
  fonts/colours, so a DebCraft deck re-themes correctly in PowerPoint and new slides added by hand look right. Size L.
- [ ] **P2.8 Slide features.** Sections, hidden slides, transitions, basic entrance animations, slide numbers, comments (read and add). Size M to L.
- [ ] **P2.9 Accessibility pass.** Reading order, alt text everywhere, document language and title, colour-blind-safe palettes. Size S.
- [ ] **P2.10 Template-aware build.** `build_presentation` with a `template`: map our layouts onto the template's masters and
  placeholders, so a new deck takes the company look automatically. Today only `edit_presentation` can use a template. Size L.
- [ ] **P2.11 Template analysis.** Render each of a template's layouts to a picture, list placeholders, theme colours and fonts, and
  propose which layout fits which content; delete unused sample items cleanly (a slot with no data removes its whole group). Size M.
- [ ] **P2.12 Edit operations to full strength.** Replace a picture keeping crop and position; per-run formatting edits; global font and
  colour changes through the theme; table rows and columns add/remove; chart type change and formatting; headers and footers;
  bulk speaker-notes edits; find shapes by what they say. Size M.
- [ ] **P2.13 Copy slides that hold charts or embedded objects** by cloning the chart parts (today refused). Size M.
- [ ] **P2.14 Merge and import.** Bring slides from another deck keeping their design; combine decks; split a deck. Size L.
- [ ] **P2.15 Raw-file escape hatch.** Unpack a deck to its XML files, edit, validate against the format, repack, with the validator from
  P1.8. For anything python-pptx cannot do (comments, animations, SmartArt, odd masters). Needs a security review (zip bombs, external
  links). Size L.
- [ ] **P2.16 Read and analyse to full strength.** Text as Markdown, comments, notes, hidden slides, alt text, links, animations summary,
  extract embedded pictures, per-slide contact sheet; `.ppt` to `.pptx` and deck to PDF through PowerPoint when present. Size M.
- [ ] **P2.17 Review mode.** Critique a deck (story, density, consistency, contrast, font count, alignment, repeated layouts) and list fixes,
  or fix them. Size M.
- [ ] **P2.18 Reliable overflow detection.** With PowerPoint present, measure each text box's real text height through PowerPoint
  instead of our estimate; without it keep the estimate. Size M.
- [ ] **P2.19 Build from documents.** Read Word, Excel/CSV and PDF sources (DebCraft has PDF page rendering only) and turn them into a deck:
  summarise, pick charts, cite sources in notes. Size M.
- [ ] **P2.20 Storyline guides.** Short guides in the skill for common decks (board update, pitch, QBR, design review, training, project
  status), including slide counts, timing and speaker-note style. Size S.

### P3 Large or platform work
- [ ] **P3.1 HTML/CSS design path** (decision 1b): `build_presentation` accepts slides written as HTML/CSS and converts the measured result
  to native .pptx shapes (text boxes, shapes, images, charts as native objects where possible). Gives full design freedom with flexbox/grid
  layout, fonts, gradients and shadows. Uses the headless browser already in `forge[browser]`. Size L.
- [ ] **P3.2 Render without PowerPoint** (decision 2): optional LibreOffice rendering; or our own renderer from P3.1. Includes a font-substitution
  warning so fit checks are trusted only for fonts that render true-to-width. Size L.
- [ ] **P3.3 Performance and size.** Large decks (100+ slides), image downscaling and compression, file-size limits, time limits on preview. Size M.
- [ ] **P3.4 Security review of the presentation tools.** Untrusted decks (zip and XML bombs, external relationships/links, embedded
  objects), PowerPoint COM launch, files outside the workspace, Mode B (host-identifying terms in slide text). Size M.
- [ ] **P3.5 Documentation.** A user guide ("how to ask DebCraft for a deck"), examples gallery generated from the benchmark. Size S.


### 4b. Own Word, Excel and PDF skills (agreed 2026-10-12; clean-room builds, replaces the parked "sibling document skills" item)
Anthropic's `docx`, `pdf`, `pptx` and `xlsx` skills are source-available, not open source (the `pptx` licence forbids copies and derivative works, checked 2026-10-09; the other three were not read individually). DebCraft builds its own, as it did for presentations: same capabilities, own code and wording, made from public format specifications and permissively licensed libraries. Reuses the presentation work: package validator (P1.8), preview rendering and contact sheet (P1.1), palettes and brand kits (P2.1), the critic and the asset catalogue (`L0`).
- [ ] `W0` **Clean-room protocol and licence check (do first, small).** Write the rules into `docs/DOCUMENTS_CLEAN_ROOM.md`, covering **presentations as well** (the existing `make-presentation` skill and tools were built this way, D-240 to D-242; record that history there and check it against the rules): build from the ECMA-376 (Office Open XML) and PDF specifications, the libraries' own documentation and our own experience; do not fetch, read or keep the source skills' files or scripts; no close paraphrase of their wording; record in `docs/DECISIONS.md` which references each part used; record each library's licence (python-docx MIT, openpyxl MIT, pypdf BSD, pypdfium2 BSD/Apache, reportlab BSD) in the asset ledger. Also read the individual `LICENSE.txt` of `docx`, `pdf` and `xlsx` to learn whether they match `pptx` (for the record only; the plan does not depend on it).
- [ ] `W1` **Word documents (`make-document` skill plus `build_document` / `read_document` / `edit_document` tools).** Headings, paragraphs, lists, tables, images with alt text, headers and footers, page numbers, table of contents, styles and a company template, hyperlinks, footnotes; read an existing .docx (text as Markdown, comments, tracked changes), edit it keeping formatting (find and replace across runs, set text, add or remove rows and sections), add comments; typography and spacing rules (story first, hierarchy, readable line length, consistent styles), accessibility (language, title, heading order, alt text); preview through Word when present (like the PowerPoint picture export) and an optional LibreOffice path; package validation (shared with P1.8).
- [ ] `W2` **Excel workbooks (`make-spreadsheet` skill plus `build_workbook` / `read_workbook` / `edit_workbook` tools).** Real formulas, never pasted values; named ranges, number and date formats, tables, conditional formatting, data validation, freeze panes, column widths, native charts; read and edit an existing workbook keeping formulas and formatting; a recalculation and error check (`#REF!`, `#DIV/0!`, circular references, formulas that return text) through Excel when present or a formula engine otherwise; clean messy CSV/TSV into a proper sheet; modelling conventions (inputs, calculations and outputs separated, colour-coded inputs, no hard-coded constants in formulas, an assumptions sheet).
- [ ] `W3` **PDF toolkit (`pdf-toolkit` skill plus tools).** Extract text and tables with layout, merge, split, rotate, crop, watermark, stamp page numbers, fill forms, encrypt and decrypt, extract images, create a PDF from content (reportlab; check the licence of any HTML-to-PDF library before use), OCR a scanned PDF with the existing Tesseract path, and render pages with the existing `pdf_render`. Mode B rules apply to anything sent to a model.
- [ ] `W4` **Shared document engine.** One preview and contact-sheet path for Word, Excel, PDF and PowerPoint; one OOXML package validator (zip and XML safety, relationships, element order); one document critic that scores a rendered contact sheet on hierarchy, consistency, readability, tables and charts; document themes and brand kits shared with presentations (P2.1); catalogue entries for document templates under the asset standard in `L0`; the security review (P3.4) extended to documents (zip and XML bombs, external links, embedded objects, macros never executed, files outside the workspace).
- [ ] `W5` **Document benchmark.** About 15 fixed requests per type (Word: report, proposal, letter, edit-an-existing-document; Excel: budget, tracker, data clean-up, dashboard with charts, edit-an-existing-workbook; PDF: extract, merge, fill a form, OCR), scored by a judge model looking at the rendered result and by checklists (opens cleanly, formulas intact, no overflow); you supply 3 to 5 sample documents you like, and outputs made with Anthropic's skills may be used as a quality reference (their outputs, not their files); results in `docs/DOC_BENCHMARK.md`.

## 5. Platform, runtime and coding competency

### 5a. Older open items (platform, runtime, build quality)
- [ ] MCP review and security design (Mode B) before extending; LSP design
- [ ] Full test run after the revamp code steps; commit in logical parts
- [ ] Next campaign ideas: a project with a database and a REST API (verifier on an API), a CLI tool, a Mode A repo; watch whether the verifier is called on larger features
- [ ] Unattended runs: decide how a headless run may install dependencies (today always-ask)
- [ ] G3 Compaction robustness (summariser-failure fallback, image budget) — only if real runs need it
- [ ] G5 Task breakdown — decide only if the campaign shows lost steps (no build under D-155)
- [ ] Parallel pytest in built apps: Forge runs `python -m pytest` sequentially (no xdist, no `-n`). Add a prompt line to use pytest-xdist only for large suites (needs a pip install approval; beware shared ports and SQLite files) once a real project shows slow test runs.
- [ ] Campaign case: Forge builds a small MCP-using tool and tests it with a dummy stdio MCP server it writes itself (needs the `mcp` package via an approved pip install; the server is not wired into Forge's own `config.yaml`). Not yet run live.
- [ ] The full test suite takes ~6 min (browser tests); consider splitting browser tests into a marker run if it gets slower
- [ ] `write_secret_values` in config.py is no longer used by the web app; remove it. **Needs your OK (2026-10-13):** the auto-mode safety check refused my removal because five tests of it (including one that checks a typed key is masked at once) would be deleted. Say yes and I remove the function and those tests together.

### 5b. Python and software competency (agreed 2026-10-12; goal: code quality as close to Claude's as DebCraft's model allows)
Honest starting point: the model is weaker on deep reasoning, whole-codebase understanding, subtle bugs and clean architecture; DebCraft has the Claude Code loop, a test gate, a few narrow skills (pytest, Flask, LangGraph, SQL migrations) and reviewer, debugger and verifier subagents. Missing: broad skills, automatic quality gates on its own output, and any measurement. The same method as for design applies: reference patterns, independent review, automatic checks, a benchmark. Do the benchmark first.

**NOTE (2026-10-12): before taking up any item that cites obra/superpowers or mattpocock/skills, do `C18`: study both repositories in detail, write `docs/SKILLS_STUDY.md`, and decide what to take from each. Until then those items are blocked.**
- [~] `C1` **(10 tasks, runner and offline validation built 2026-10-13, D-262; see docs/CODE_BENCHMARK.md. First live baseline 2026-10-13: 10/10 tasks, $1.62, 21 min (docs/CODE_BENCHMARK.md); too easy to separate changes. Open: harder tasks, add REST API, Mode A, Mode B no-host-code and larger tasks up to 20 to 30, the judge rubric)** **Coding benchmark (first).** 20 to 30 fixed tasks with hidden tests, in tiers: single function, small module, bug fix in an existing repo, feature in an existing repo, refactor with tests kept green, performance fix, CLI tool, REST API service, data pipeline, async worker, a Mode A task (repo copy) and a Mode B task (no host code). Scored on the real model: hidden-test pass rate, a judge rubric (correctness, edge cases, error handling, tests, security, simplicity, readability), time and cost per task. Results in `docs/CODE_BENCHMARK.md`; re-run after every change in this section; tasks are fixtures under `tests/benchmarks/` (marker `live`). Needs nothing from the user except your ratings of a sample.
- [ ] `C2` **Automatic quality gates on DebCraft's own output.** After edits and before `task_update(done)`: ruff (lint and format), mypy or pyright when the project configures it (a sensible default otherwise), a security scan (bandit), coverage of the changed lines (a threshold the project can set), dependency audit (pip-audit; the Dependencies tab already has it) and a complexity warning; findings go back to the model like the UI audit does, with a per-project config and an off switch; only the project's own code is scanned.
- [~] `C3` **(first part built 2026-10-13, D-267: skill `python-project` with 4 skeletons and 12 tested recipes: errors, logging, settings, typing, async, pytest, SQL, security checklist, performance, refactoring, Python 3.11-3.14 idioms, CLI design. Open: Django, Flask extension, Typer/Click detail, pandas/polars, SQLAlchemy + Alembic, hypothesis, profiling helpers, differential review, CI-failure debugging, stack-trace fixing, threat-model skill; C7 and C10 content stays blocked on C18)** **Coding skill library, in our own words and tested.** FastAPI service, Django app, extending a Flask app, CLI (argparse, Typer, Click), async patterns, typing and protocols, packaging (`pyproject.toml`), logging, configuration and error handling, data work (pandas, polars), SQLAlchemy and plain SQL, pytest fixtures and property tests (hypothesis), refactoring recipes, profiling and performance, a security checklist, and Python 3.11 to 3.14 idioms. Also, as our own skills in our own words (other publishers' skill lists, e.g. Trail of Bits, OpenAI and Sentry, show the topics; their licences differ per skill; Anthropic's document skills docx, pdf, pptx and xlsx are source-available, not open source, and must not be copied, while many of its other example skills are Apache 2.0, to be checked per skill): a security code review and threat-model skill, static analysis and insecure-defaults checks, property-based testing, differential review of a diff, debugging a failing CI run, and fixing a production error from a stack trace. Each follows the asset standard in `L0` (catalogue entry, usage note, tested example) so `find_design_asset` (generalised to "asset") can find it. Needs `L0`.
- [ ] `C4` **Code-review rubric and gate.** Give the `reviewer` subagent a fixed rubric (correctness, edge cases, error handling, tests that prove something, security, simplicity, naming, no dead code), structured output with a `VERDICT: SHIP|REVISE` like the design critic, a fresh context, and an optional gate before a code task closes; use the gpt-4o fallback as the reviewer so a different model checks the builder. **Reviewer protocol** (Idea from obra/superpowers, MIT, ~298k stars; no outcome data published, so measure on `C1`; write in our own words.): one review returns two verdicts, spec compliance (did it build what was asked, nothing more) and quality; the builder's self-review never replaces it; and the rule for receiving a review: check each suggestion technically against the code before applying it, no performative agreement, push back with evidence when it is wrong. **Also (Idea from mattpocock/skills, MIT, ~287k stars, no outcome data published; own words.)** run the review as two parallel reviewers with separate contexts, one against the project's documented standards and one against the originating spec (DebCraft has the pinned requirement and the task list), each report capped at about 400 words, findings never merged or re-ranked, a closing line with counts and the worst issue per axis; a documented project standard beats a built-in baseline of common code smells, and smells are judgement calls, never hard violations; skip the spec reviewer when there is no spec and say so. **Do not start before `C18` (the detailed study of both repositories) is done.**
- [x] `C5` **(done 2026-10-13, D-266: new skill `python-project` with four skeletons (library, CLI, async worker, FastAPI service); each is checked on a fresh copy by ruff, mypy --strict and pytest. A task runner file was left out on purpose: the commands are in the README, Windows-first)** **Project skeletons and reference patterns.** Copy-in starting points through the asset tools: src-layout project with `pyproject.toml`, ruff, mypy and pytest config, a CI file, a task runner, a README skeleton; FastAPI, CLI and worker skeletons. Needs `L0`.
- [ ] `C6` **Plan, test first, small verified steps.** A skill and a nudge for non-trivial tasks: write the spec and the acceptance tests first, implement in small steps, run the tests after each, never weaken a test; measure on `C1` whether it helps before making it a gate. **Details** (Idea from obra/superpowers, MIT, ~298k stars; no outcome data published, so measure on `C1`; write in our own words.): write the spec first and record it without waiting for approval (DebCraft decides and keeps going; do not copy its stop-and-ask brainstorming); plans of small tasks with exact file paths, the test or check for each task and the expected result; test first as a softer rule than "delete code written before the test" (new functions and every bug fix get a failing test first, watched to fail for the right reason); finish by running the project's full test command and naming every failure, including ones not caused by us; measure the strict and soft variants on `C1`. **Also (Idea from mattpocock/skills, MIT, ~287k stars, no outcome data published; own words.)** vertical slices (one test, one implementation, repeat, each test a tracer bullet from what the last cycle revealed) instead of all tests first; tests assert behaviour through public interfaces, read like a specification and survive refactors; expected values come from an independent source, not from re-computing the code's logic; DebCraft picks the test seams itself (the original asks the user to confirm them). **Do not start before `C18` (the detailed study of both repositories) is done.**
- [ ] `C7` **Debugging competency.** A systematic-debugging skill (reproduce, minimise, form hypotheses, instrument, confirm, fix the cause, add a regression test), a better `debugger` subagent brief, a bisect helper over the workspace's local history, profiling helpers; measure on the bug-fix tier of `C1`. **Method to teach** (Idea from obra/superpowers, MIT, ~298k stars; no outcome data published, so measure on `C1`; write in our own words.): no fix before the root cause is found (read the whole error, reproduce, check recent changes, trace the data backwards to the source, compare working and broken code); state one hypothesis and test it with the smallest possible change; write a failing test, then one fix at the cause; verify; after three failed fixes stop and question the design instead of trying a fourth patch; never bundle several changes; supporting notes on root-cause tracing, validation at several layers, and waiting on conditions instead of fixed timeouts. This is a prompt-level skill, so it respects D-155 (no engine-level stuck detector). **Also (Idea from mattpocock/skills, MIT, ~287k stars, no outcome data published; own words.) The feedback loop is the skill:** before forming any theory build a fast, deterministic, pass/fail command that reproduces the exact symptom (a failing test, a script, a recorded replay, a minimal harness; a human-run script only as a last resort), tighten it for speed and signal, raise the reproduction rate for flaky bugs, then minimise the repro until every remaining element is necessary; rank three to five falsifiable hypotheses each with a prediction (one hypothesis anchors on the first idea); test one variable at a time; tag every debug log with a unique prefix so cleanup is one search; take a baseline measurement before fixing a performance issue; fix with a regression test at the right seam; remove all debug code and record the confirmed hypothesis in the commit message; redact secrets in shown output. **Do not start before `C18` (the detailed study of both repositories) is done.**
- [~] `C8` **(import check gate and prompt rule done 2026-10-13, D-264; open: a docs-fetch helper for the installed version, and attribute-level checks via mypy)** **Library-API correctness.** Reduce invented APIs: before using an unfamiliar library, read the installed version (`pip show`) and fetch the matching official documentation; a check that every import and called attribute exists (run it, or mypy); prefer the standard library when it is enough. Needs the network for the docs fetch; degrade gracefully when blocked.
- [ ] `C9` **Tests as the judge for hard tasks.** For a hard or ambiguous problem run several candidate solutions in parallel (builder subagents in separate folders) and keep the one that passes the tests and the review; the highest reasoning effort for algorithm and debugging steps. Needs `X2` and `C1` (to prove it pays off).
- [ ] `C10` **Tests that prove something.** A light mutation check on changed functions (does a deliberately broken version fail the tests?), warnings for tests with no assertions or that only mirror the implementation; optional, measured on `C1`. **Also (Idea from mattpocock/skills, MIT, ~287k stars, no outcome data published; own words.)** flag tautological tests (pass by construction), implementation-coupled tests (mocking internals, testing private methods) and tests whose expected values mirror the code under test. **Do not start before `C18` (the detailed study of both repositories) is done.**
- [ ] `C11` **Whole-repository understanding, only if the benchmark shows lost context.** An outline tool (signatures and structure of a file or package) and a cheap call-graph query; D-156 says no built index by default, so this is added only when `C1` shows the model misses code it should have found.

- [~] `C12` **(audit table written 2026-10-13, D-261; the gaps below are not built yet: (a) and (c) wait for `C1`, (b) and (e) are small and next in line)** **Harness parity audit against Claude Code (agreed 2026-10-12; source: the best-practice guides at shanraisshan/claude-code-best-practice).** List what Claude Code offers that DebCraft lacks, as far as the code shows, then build the gaps that matter, each with a test: (a) hooks beyond `post_edit`: a **before-tool** hook (policy checks, extra approvals), a **stop** hook that verifies the work before a turn may end (tests, `C2` gates) and a **session-start** hook; (b) **path-scoped rules**: instruction files that load only when files matching a glob are touched, so a big repo's rules do not fill the context (Mode A); (c) **forked skills**: a skill that runs in its own context and returns only its conclusion, for noisy work (also helps `S4`); (d) a visible **rewind** of a failed attempt in the UI (history and checkpoints exist; check the UI path); (e) context-usage warnings with a compaction hint before quality drops. Skip what DebCraft already has (plan mode, subagents, skills, memory, MCP, compaction, history). Record the audit table in `docs/DECISIONS.md`; each gap that is built gets its own decision.
- [ ] `C13` **Skill style rewrite and a Gotchas loop.** Rewrite every DebCraft skill (including `ui-design-quality`, `make-presentation`, `web-research`, `pytest-patterns`, `web-ui-verification`) so the front-matter description says WHEN to use it ("use when ...") instead of summarising, the main file stays short, and detail moves to subfolders loaded on demand; add a **Gotchas** section to each skill that grows from observed failures in real runs (the e2e campaigns, your reruns, the benchmarks); a small helper that appends a dated gotcha with the task it came from. Cheap, helps every skill, and improves skill selection by a weaker model; measure with the retrieval test in `L0`. **Add a skill-use rule to the system prompt** (Idea from obra/superpowers, MIT, ~298k stars; no outcome data published, so measure on `C1`; write in our own words.): before acting on any task, even a question, check the skill index; if there is a real chance a skill applies, load it; announce "Using <skill> to <purpose>"; a short table of common excuses ("it is just a simple question", "I remember this skill", "I will look afterwards") with the answer to each; user instructions override skills and skills override defaults; subagents running one specific task are exempt. Weaker models under-trigger skills, so measure the effect with the retrieval test in `L0` and `C14`, and watch that it does not slow trivial tasks. **Also (Idea from mattpocock/skills, MIT, ~287k stars, no outcome data published; own words.)** read its `writing-for-agents` guidance (how to write skills and instruction files) as input to the skill rewrite; keep skills small, editable and composable. **Do not start before `C18` (the detailed study of both repositories) is done.**

- [ ] `C14` **Skill A/B evaluation loop (lowest priority; method from Anthropic's `skill-creator`, own implementation).** For each DebCraft skill: write 2 to 3 realistic test prompts, run each with the skill and without it (or against the previous version), grade the outputs against assertions (the audit, the tests, the critic or a judge model), aggregate into a benchmark file, and review the difference; tune the skill's description on a train/test split of about 20 should-trigger and should-not-trigger queries and keep the best on the held-out set. Use DebCraft's own models and the existing `eval-harness` skill (the original needs `claude -p`, which DebCraft does not have). Principles to keep: descriptions a little pushy because models under-trigger skills, explain the why behind each rule, keep the main skill file under 500 lines with detail in subfolders. Feeds `C13` (skill style rewrite) and the retrieval test in `L0`; decide per skill whether it earns its place in the context.
- [ ] `C15` **Server-lifecycle helper for the verifier's browser scripts (lowest priority; idea from Anthropic's `webapp-testing`).** A small script in the `web-ui-verification` skill that starts one or more servers (backend and frontend, each with its own folder, port and ready pattern), waits until they answer, runs the Playwright script, and stops them, so the verifier's script holds only the browser logic; the skill also teaches "look first, then act" (wait for the page to settle, take a screenshot or read the DOM, choose selectors from what is rendered, then act) and to wait for `networkidle` before reading a dynamic page. Test it with a two-server fixture and the existing `live_server` pattern. Note: `start_background` already takes a `cwd` (D-248); reuse it.

- [ ] `C18` **PREREQUISITE: study the Superpowers and mattpocock/skills repositories in detail, then decide what to take (agreed 2026-10-12).** So far only summaries of four to five skills per repository were read. Before developing any item that cites them (`C4`, `C6`, `C7`, `C10`, `C13`, `C16`, `C19`, `C20`, `C21`, `D7`, and the builder protocol in `X2`), read both repositories properly: every skill and its reference files, scripts and templates, the philosophy and scope documents (`GLOSSARY.md`, `SCOPE.md`, `AGENTS.md`, `CLAUDE.md`, the README rationale), the changelogs (what they learned and changed), and the skill tests and evaluations (Superpowers' `tests/` and the drill harness in superpowers-evals). Deliverable: `docs/SKILLS_STUDY.md` with, per skill, what it does, the ideas worth taking, what to leave and why, conflicts with DebCraft's decisions (D-051 decide and keep going, D-155 no engine-level stuck detector, D-161 accuracy and speed before cost, the safety invariants), the licence note, and an estimated value; a comparison of the two (Superpowers: enforcement; mattpocock: small composable craft skills); then one decision in `docs/DECISIONS.md` and the dependent items updated to say exactly what they take. Write nothing derived from them until this is done; when writing, use our own words (both are MIT, but we distil to keep the context small and the wording tuned to our model).
- [ ] `C19` **Deep-module design skill and "design it twice" (Idea from mattpocock/skills, MIT, ~287k stars, no outcome data published; own words.)** **Do not start before `C18` (the detailed study of both repositories) is done.** Shared vocabulary (module, interface including invariants and error modes, seam, adapter, depth, leverage, locality); deep modules (much behaviour behind a small interface); the deletion test (if removing a module makes complexity vanish it was a pass-through); one adapter is a hypothetical seam, two make a real one; accept dependencies instead of creating them, return results instead of side effects; avoid shallow wrappers and speculative abstraction; "design it twice": explore two or three radically different interface designs in parallel (builder or explore subagents) and pick one with reasons; a scan for deepening opportunities for refactors in an existing repo (Mode A). Weaker models over-engineer and wrap; measure on the refactor and feature tiers of `C1`.
- [ ] `C20` **Project glossary and light decision records in the projects DebCraft builds (low priority) (Idea from mattpocock/skills, MIT, ~287k stars, no outcome data published; own words.)** **Do not start before `C18` (the detailed study of both repositories) is done.** For non-trivial or multi-session projects DebCraft keeps `docs/GLOSSARY.md` (the project's own terms, used consistently in code, tests and messages) and short decision records for design choices, decided by DebCraft and recorded without an interview (its original skills grill the user; ours decides and continues, D-051); read them first in a resumed session. Check against the existing project-state memory and `/handoff` so nothing is duplicated.
- [ ] `C21` **Guided script for steps only the human can do (low priority) (Idea from mattpocock/skills, MIT, ~287k stars, no outcome data published; own words.)** **Do not start before `C18` (the detailed study of both repositories) is done.** When a step needs the user (set up `.env`, install a tool, run a database request, approve something outside the sandbox), DebCraft can generate a small interactive PowerShell script that walks through it step by step, checks each result, and reports back, in line with safety invariant 6 (hand over what Forge cannot or must not do). Check the existing `request_user_action` card first and extend it rather than duplicate it; no secrets are printed or stored by the script.
- [ ] `C16` **A/B experiment with the original Superpowers (needs `C1`).** (Idea from obra/superpowers, MIT, ~298k stars; no outcome data published, so measure on `C1`; write in our own words.) Run the coding benchmark three ways: baseline DebCraft, DebCraft with the original skills installed through `forge skill add https://github.com/obra/superpowers` (you install it; DebCraft shows the contents and asks first), and DebCraft with our distilled versions (`C6`, `C7`, `C4`, `C13`). Compare pass rate, quality score, time and cost per task in `docs/CODE_BENCHMARK.md`; decide per skill what to keep. Watch for the shouting style ("YOU MUST", "NO CHOICE"), which was tuned for Claude and may be ignored or over-obeyed by another model, and for slow-downs on trivial tasks. Also read its skill-testing method (pressure scenarios) when doing `C14`. **Add a fourth arm: mattpocock/skills** (`forge skill add https://github.com/mattpocock/skills`, you install it; it asks to run a one-time setup per repository that DebCraft must skip or answer itself). Only after `C18`.
- [~] `C17` **(command done 2026-10-13, D-259: `forge run-report --workspace <folder>`; open: the download button in the UI, and per-step timeline once the Run map shows S1 data)** **Scrubbed session report you can send for analysis (small; useful early).** `forge diagnose` exists for delivered code; add a per-project "run report" export: events summary, step and tool timeline with durations (needs `S1`), model calls and cost per agent, errors and retries with their reasons, screenshots taken with their audit findings, critic scores and verdicts, gate refusals, task list; secrets and host-identifying terms redacted (Mode B rules), no source code unless asked, saved as a file and offered as a download in the UI. Lets you send a run for scoring and lets us measure `D2`, `S1` and `C1` from real runs. Idea from the `diagnosing-superpowers` skill (a session diagnostic that exports a scrubbed bug report).

## 6. Parked (not started; your choice when)
- [ ] PARKED (user, 2026-10-04): one-click install from the GitHub zip (starter script -> venv + pip install -> .env template -> `forge doctor` -> open UI -> shortcut).
  Waiting on the user's probe of what the office laptop allows (script run, pip reach, Python 3.13) and a choice: `.cmd` starter vs signed `.exe`, bundled embeddable Python or not.
- [ ] Optional: Azure AI Vision / Document Intelligence for handwriting OCR (user has no key yet; would need a yes in the drawer)
- [ ] **Internal rename `forge` -> `debcraft`** (package, `.forge` folders, `FORGE.md`, `FORGE_*` settings). The visible rename is done (D-244); this part needs a migration or a read-the-old-name fallback. Sizing and the recommended plan are in `docs/TODO_LATER.md`.


## 7. Completed work (history)
Kept for reference. Open items were moved up into sections 1-6.

### Step 1 — Pre-build review
- [x] Understanding, risks, ambiguities, order proposal
- [x] User answers recorded (DECISIONS D-001…D-015), spec amended (§0.2), docs created
- [x] Local Postgres `forge_dev` (D-018), Python 3.13 (D-006), D-008, D-013, D-016, D-017 settled
- [x] User approves M0 + M1 brief

### Milestones (order per D-002)
- [x] **M0** Scaffolding — pyproject, src layout, tooling, vendored tiktoken, fixture repo, docs
- [x] **M1** Foundations — config + per-role models, Azure adapter (Responses/Chat), event bus, tokens, retries, streaming, cost, REPL, doctor
- [x] **M2** Workspace — copy, baseline, write jail, redaction core, checkpoints, output generator
- [x] **M3** Core tools + loop — files, search, PowerShell shell, background procs, permission gate, shell classifier v1
- [x] **M4** Context management — §10 (+ sandbox D-050)
- [x] **M5** Knowledge Base — extractors, index, LLM docs, refresh
- [x] **M6** Orchestrator — phases, approvals, tasks, resume, restructure (original, phased design)
- [x] **M6 rework** Flat loop (D-128, D-129, D-130, D-131, D-132) — done 2026-09-29, see below
- [x] **M7** Database — local/remote targets, access levels, scratch per requirement, DB requests, guards
- [x] **M8** Verification & self-correction
- [x] **M9W** Web UI core
- [x] **M9** Diagnose mode
- [x] **M10** Web, browser, memory, UX
- [x] **M10B** Mode B standalone — done 2026-09-28 (D-096, D-102, D-105; live acceptance 1–3, see REMAINING_TASKS)
- [x] **M10C** Learning & self-improvement — done 2026-09-28 (D-089..D-094; live acceptance passed)
- [x] **M10E** Claude Code parity — done 2026-09-28 (D-095; offline gate 10 pass)
- [x] **M10D** Multimodal & evals (general) — done 2026-09-28 (D-097)
- [x] **M11** Hardening & packaging — done 2026-09-28 (D-098..D-106); open: "tables exist in scratch" check (SPEC_DEVIATIONS)
- [x] **UI** React web UI (only UI) — project form, uploads, live progress, cost counter, per-phase/task usage,
  Run map (task graph + timeline, failures drawer, waiting bars), stepper with cost/time per step, collapsible
  side panel — done 2026-09-28 (D-113..D-124)

### Open items
- **M6 rework — flat loop, cadence, judgment-based verification, Contracts store (D-128, D-129, D-130,
  D-131, D-132) — done 2026-09-29:**
  - `agent/orchestrator.py`/`state.py` rewritten: no `Phase` enum, no mandatory CLARIFY/PLAN/REVIEW gates.
    `propose_requirements`/`propose_plan` are optional, non-blocking tools. Verification (§13) is
    judgment-based — the mandatory full-suite-plus-reviewer gate and `MAX_REVIEW_FIX_ROUNDS` are gone.
  - Cadence (D-130) is a persisted `state.cadence` field, set by `detect_cadence()` recognising phrases
    like "go ahead, don't ask me" / "ask me before every step" in chat, or `/mode`; survives a restart
    (D-132). Never waives the always-ask/critical list (§14.2).
  - Resume is automatic and silent (D-132): `state.exported` (not a phase) tracks whether a workspace is
    resume-safe; the resume greeting is `state.resume_summary()`.
  - Wired through `session_host.py`, `cli.py`, `headless.py`, `slash_commands.py`, `console.py`,
    `web/server.py` (kept a backward-compat `phase` key in `/api/state`, mapped to `resume_summary()`, so
    the not-yet-rebuilt React UI degrades instead of breaking).
  - Mode B Contracts store (§6A.2A, D-129): `src/forge/modeb/contracts.py` (`ContractRegister`, per host
    profile), `contract_pin`/`contract_read` tools, `/contracts` command, pinned into context alongside
    profile essentials, and pinning proposes a lesson (scoped to the profile) so Forge recommends a known
    contract on a later requirement. The **web UI Contracts panel** (built 2026-10-03, D-194; the other half of the D-129 UI
    decision) is NOT built — chat/`/contracts` is the only interface today; deferred with the rest of the
    React UI work (below).
  - All 6 affected test files rewritten/fixed (`test_orchestrator.py` fully rewritten, `test_db.py`,
    `test_m10_wiring.py`, `test_live_orchestrator.py` updated, `test_web_e2e.py`'s two Run-map/stepper
    tests marked `@pytest.mark.skip` citing D-131) plus new `tests/test_contracts.py` (8 tests). ruff,
    mypy and `check_secrets.py` clean. Full non-live/non-pg suite (~400+ tests, `test_sandbox.py`/
    `test_hardening.py` excluded to save time, not for correctness) passes cleanly end to end in ~15
    minutes, exit code 0, only the two deliberate D-131 skips — a first pass mistakenly reported this as
    a "hanging" test-infrastructure issue because of timeouts (40–250s) too short for the fixtures' real
    filesystem/git I/O; corrected after a run with a realistic budget.
- UI: Run map/stepper redesign (D-133) — **milestones 1–3 done 2026-09-29.**
  - **M1** (`runmap.ts` + `RunMap.tsx`): `planGraph()`'s fixed phase skeleton replaced by `buildGraph()`, a
    live-growing DAG built purely from `RunModel` (start/task/agent/deliver nodes appear only once their event
    has fired; `depends_on` edges unchanged; agent nodes attach to their task or to start via a `spawned` edge;
    the `deliver` node appears once `task_list_updated.exported` is true — new field, D-133a). `ProgressHeader`
    (the stale phase stepper) and its dead plumbing (`STEPS`/`STEP_OF_PHASE`/`stepOf` in `activity.ts`,
    `PHASE_LABEL`/`phaseWorkMs`/`planGraph`/`Marker`/`Span`/lanes in `runmap.ts`) deleted, along with the
    separate SVG timeline pane (`Timeline`/`SpanBar`/`MarkerGlyph`/`Legend`); failure/stuck counts moved onto
    task-node badges (agent nodes show a failed-icon badge; no numeric per-agent count yet — no such signal
    exists today).
  - **M2** (`RunMap.tsx`, `index.css`): CSS-only animated relayout — `.react-flow__node` gets a `transform`
    transition so dagre's full relayout-on-structural-change glides instead of snapping; new nodes/edges get a
    fade/scale-in entrance (`prefers-reduced-motion`-aware). Auto-fit now gates on user interaction:
    `onMoveStart`'s `event` is null for programmatic moves (fitView) and non-null for real user gestures, so a
    manual pan/zoom disables further auto-fit until a new `ControlButton` ("Recenter", `data-testid
    ="run-map-recenter"`) re-fits and re-arms it. Along the way, fixed a bug where `AutoFit` was gated on
    `useNodesInitialized()`, which never became true in this app (nodes are sized via inline style, not
    measured) — silently meaning the effect never actually fired; removed that dependency since dagre already
    positions nodes before mount. Manually verified against a live server with a throwaway Playwright script
    (not committed): pan disables auto-fit, Recenter re-fits and re-arms it.
  - **M3** (`Activity.tsx`, `Composer.tsx`): `ActivityLine` gained a per-task cost/time badge
    (`by_task[current_task]` + elapsed derived from the first event where `where.task` matches, since M1's
    rewrite dropped the old per-task start-timestamp plumbing) and a new `RunTotals` strip (`cost.project.total`
    — already exposed, no manual summing needed — + `runStartedAt`), shown only while busy, styled quieter than
    the activity line. Call site added in `Composer.tsx` (not `Chat.tsx` — that's where `ActivityLine`/the old
    `ProgressHeader` actually lived).
  - `npm run build` (tsc -b + vite build) passes clean after all three milestones combined; targeted backend
    tests (`-k "orchestrator or task_list or publish_tasks"`) 15 passed for the `orchestrator.py` `exported`
    field.
  - **Still open:** `agent_finished` gaining `cost_usd` (documented fast-follow, backend — no per-agent cost
    number yet, only duration/ok). Re-enabling the two skipped `test_web_e2e.py` Run-map/stepper tests (D-131)
    — deferred; they target the old pre-D-133 DOM and need rewriting against the new graph structure, not just
    un-skipping. Also still needs: the Contracts panel (D-129, above). D-123 (phase-row-for-multi-day-runs) is
    folded into this redesign, not separate — the growing DAG loads pre-laid-out for old runs.
- UI: the chat column showed a horizontal scrollbar in the user's runmap-demo (some wide content); not yet
  investigated.
- Bug fixed 2026-09-29 (D-135): `propose_plan`/`update_plan` now end the turn so `_run_agent` can call
  `_start_task` right after a plan is (re)created — previously, if the model never naturally paused after
  `propose_plan`, `current_task` stayed `None` all session and every `task_update` was rejected (reproduced
  in the `new-demo` test run: all 5 tasks stuck `pending`, model gave up and reported itself blocked in chat).
- UI: still open — a requirement that finishes (or gets blocked) and correctly goes idle looks visually
  identical to a stuck session: "Idle", pending tasks, no cue either way. Needs a clear idle-with-a-final-
  reply state (vs. idle-and-actually-stuck) so this isn't mistaken for a hang again; surfaced by testing D-135.
- Feature done 2026-09-29 (D-136): project-creation setup now shows real phase labels ("Creating workspace
  folders…" → "Creating the Python environment…" → "Installing the test runner (pytest)…" for Mode B; file
  count + current path for Mode A's repo copy) instead of one static "Setting up…" string for the whole
  blocking call. New `GET /api/setup-progress`, polled by `Home.tsx` every 400ms while creating a project.
- M7: embedded-Postgres fallback (`pgserver`) not built (SPEC_DEVIATIONS); "every table the code touches
  exists in scratch before DB-backed runs" check not built; `db_schema` results not yet cached into the KB.
- New initiative, scoped 2026-09-29 (D-137): frontend support (React/Angular/CSS), so Forge can eventually
  build a 3-tier app. Deliberately scoped down to a first proving slice — **React support in Mode A only**
  (extending an existing repo's React app, not designing one from scratch), with headless-browser verification
  (Playwright) in scope from the start. Explicitly deferred, not decided: Angular, any other framework, Mode B
  for frontends (from-scratch design with no existing repo to read conventions from), and the general
  tech-agnostic abstraction the user originally asked for — each needs its own design pass once phase 1 is
  real. See D-137 for the full reasoning on why the full-scope request was scoped down first.
- D-138/D-139 (2026-09-29): phase 1 built — `workspace/nodeenv.py` (Node/React app detection: package
  manager from lockfile, node binary, real script names from the app's own package.json),
  `verify/react_ladder.py` (typecheck/lint/unit-tests/build rungs, each skipping when the repo doesn't
  configure that tool), and `verify/ladder.py`'s `VerifyLadder.run()` dispatcher (routes `.py` changes to the
  existing Python ladder and `.ts`/`.tsx`/`.js`/`.jsx`/`.css` changes to the new React ladder, combining
  reports; a Python-only workspace is unaffected — regression-tested).
- D-140 (2026-09-29): the browser smoke-check rung's call site is now built — `agent/frontend_smoke.py`
  (new), called from `Orchestrator._export()` only when `workspace.info.node_env is not None`. Starts the
  repo's own dev/start/preview script (new `NodeEnvironment.dev_command`, D-139's "read the repo's own
  scripts" rule extended) as a background process on a free port, loads it with the existing headless
  `BrowserSession` (tools/browser.py), checks for `[pageerror]` console entries and a non-blank body, and
  always stops the server afterward. Informational only (D-132): pass/fail/skip is appended as a
  `## Frontend smoke check` section in reports/final.md, mirroring the existing Restructure-check block, and
  never fails or blocks `_export()` — a Python-only workspace's export is untouched (regression-tested).
  **Phase 1 (D-137) is now complete** in the sense originally scoped: node detection, the React verify
  ladder, the dispatcher, and the checkpoint-only browser smoke check are all built. Still open, explicitly
  out of scope, carried forward to phase 2 or a later pass: `npm install` automation (left to the agent via
  the existing approved `run_command` tool), Angular, Mode B frontend support, monorepo auto-discovery of a
  frontend folder separate from the Python `app_subfolder`, real import-graph-based targeted-test selection
  for React (the ladder currently runs its whole test command, not a per-change selector), and the general
  tech-agnostic verify-rung/environment/contract abstraction (D-137) itself.
- D-141/D-142 (2026-09-29): phase 2 piece built — **Mode B frontend-from-scratch scaffolding.**
  `create_standalone_workspace` stays Python-only (lazy, not eager, per D-141); new `tools/frontend_setup.py`
  (`SetupFrontend`, tool name `setup_frontend`, Mode B only — registered via `tools/modeb.py`'s
  `modeb_tools()`, the same conditional-registration path as the Contracts panel tools) lets the model
  scaffold a frontend on demand via the real `npm create vite@latest` (or a free-form `create_command` for
  Angular/anything else), through the normal `run_command` shell/approval gate, then calls
  `detect_node_environment()` on the result and persists `WorkspaceInfo.node_env` — phase 1's React verify
  ladder then applies automatically, no further wiring needed. Idempotency: a second call is rejected
  (`node_env` already set, or the target folder non-empty) rather than clobbering — the model is told to work
  in the existing folder or ask the user first, not silently overwritten. Confirmed, not just assumed:
  redaction/sensitive-terms (`safety/redact.py`'s `flag()`, `ToolContext.sensitive_terms`) apply to every tool
  result at the `agent/loop.py` level regardless of which tool ran, so `setup_frontend`'s output needed no
  special handling. Still open for frontend-from-scratch: no UI-component-library scaffolding beyond whatever
  the chosen create-command's own template provides (e.g. no Tailwind/MUI auto-setup); no monorepo layout
  question arose in practice (frontend just becomes `project/<folder>/` beside the Python code, both under
  the same `project/` root the harness already expects); Angular's own CLI would go through the
  `create_command` escape hatch (untested with a real Angular CLI invocation, only unit-tested with a
  mocked shell call); real npm/network was not exercised (per the task brief, only the shell call is mocked).
- D-143/D-144 (2026-09-29): **Angular support built** (D-137's "Angular" deferred item, Mode A only, same
  scope as phase 1's React work). New `verify/angular_ladder.py` (`AngularVerifyLadder`, `is_angular_project`
  — detects via `angular.json` at the app root), separate from `react_ladder.py` for the same "rungs don't
  decompose the same way" reason that module isn't a `VerifyLadder` subclass. Typecheck now goes through
  `ng build` (with `--configuration=development` when declared) instead of bare `tsc`, since Angular has no
  typecheck-only CLI command and `ng build` is the only path that exercises template type-checking. Test
  framework detection recognises Karma+Jasmine (dependencies or a standalone `karma.conf.js`) and Jest.
  **The load-bearing fix**: a Karma-detected project's test rung always appends `--watch=false
  --browsers=<launcher>` (never runs the bare `test_command`, which would hang forever in `ng test`'s default
  watch-mode-against-a-real-browser) — the launcher prefers a custom name found in the repo's own
  `karma.conf.js` `customLaunchers` block (e.g. `ChromeHeadlessCI`), falling back to `ChromeHeadless`.
  Lint/build confirmed (not assumed) to need no special handling — both are ordinary npm scripts in a
  standard `ng generate` project. `workspace/nodeenv.py` confirmed to need no changes (detection is already
  generic over script names). `verify/ladder.py`'s dispatcher now picks Angular vs. React per-project via
  `is_angular_project()`; a plain React project (no `angular.json`) is regression-tested unaffected. New
  `tests/test_angular_ladder.py` (24 tests, all subprocess calls mocked). Still open, real gaps for a later
  pass if evidence calls for it: Angular's newer esbuild/Vitest-backed test runner and
  `@angular/build:karma`-vs-legacy-builder distinctions aren't builder-aware (only dependency/config-file
  detected); Nx monorepo conventions aren't handled (`is_angular_project` only checks a literal `angular.json`
  at the app root, so an Nx workspace falls through to the React ladder — no worse than before this pass, but
  still wrong); Mode B Angular support (only Mode A is in scope here, matching D-137's original React scoping);
  no real Angular CLI/npm was exercised (mocked throughout, per the task brief).

- D-145/D-146 (2026-09-29): **Guided first-run setup screen built** — the UI/backend piece of D-145.
  New `config.write_secret_values`, new `doctor.required_secret_names`/`missing_secret_names`, new endpoints
  `GET /api/setup` and `POST /api/setup/secrets`, `GET /api/doctor` gained `?offline=` (default unchanged),
  new `ui-react/src/components/Setup.tsx` shown by `App.tsx` before Home/Chat only when required secrets are
  missing (zero-flash on the already-configured path). No restart needed: confirmed `WebSessionManager` caches
  no `Secrets`/`LLMRouter` before a project is opened, so `load_secrets` re-reading `.env` from disk is already
  sufficient. Tests, ruff, mypy, `npm run build`, `check_secrets.py` all clean — see D-146 for full detail.
  **Done 2026-09-29 (D-147)**: `scripts/run_forge.ps1`, a new sibling script (not a rewrite of
  `install_forge.ps1`, kept separate on purpose — see D-147) — creates/reuses a `.venv` inside the unzipped
  folder itself (no PATH shim, no shared install location, so it can't shadow or be shadowed the way the
  triggering bug happened), installs from the unzipped source (or a bundled wheelhouse if present), and
  launches `forge ui` directly into D-146's setup screen. Actually run end-to-end against this build machine's
  repo, not just written: caught and fixed a real failure (a previous `forge ui` window locking its own
  `forge.exe` during reinstall) with a clear error message instead of a raw pip WinError.

- **RESUMED 2026-10-04 (user sent the office-laptop signatures)** (D-150, started 2026-09-30): **Gemini as a second model provider** (Vertex AI direct SDK,
  `google-genai`, no LangChain — assignable to any role, not just vision). Live-verified on the user's office
  laptop (this dev machine has no GCP credentials): ADC auth, text calls, tool-calling round-trip, streaming,
  image vision, video input, and which models are actually callable on the user's project (`gemini-2.5-pro`,
  `gemini-2.5-flash`, `gemini-2.5-flash-lite`; `2.0-flash`/`2.0-flash-lite`/`3-pro-preview` are 404 — listed
  in Model Garden but not provisioned). See D-150 for the full picture.
  - [x] `config.py`: `GeminiProviderConfig`, `ModelConfig.provider`/`model_name` generalized — done, mid-review.
  - [x] `doctor.required_secret_names`: provider-conditional (Azure vars only if Azure in use, Gemini's
    `project_env`/`location_env` only if Gemini in use) — done, mid-review.
  - [x] `llm/translate_gemini.py`: message/tool-call translation to/from `google-genai` types.
  - [x] `llm/gemini.py`: `GeminiProvider` (implements the same `LLMProvider` protocol as
    `AzureOpenAIProvider`), error mapping (`google.genai.errors` → Forge's `LLMError` subclasses, including
    `DefaultCredentialsError` → a clear ADC-setup `LLMAuthError`), `automatic_function_calling.disable=True`
    set explicitly (Forge's loop must own every tool call, never the SDK).
  - [x] `llm/router.py`: `_create_azure_provider` → a provider-dispatching factory reading `model.provider`.
  - [ ] `doctor.check_models` needs no change (already generic over every model in use) — a Gemini model
    assigned to any role gets the live "reply: ready" startup/connectivity check for free once the router
    can dispatch to it.
  - [x] `.env.example`: document `GOOGLE_CLOUD_PROJECT`/`GOOGLE_CLOUD_LOCATION` names only, no values.
  - [x] Unit tests for the translator (message/tool round-trip, image parts) with no live calls; a
    `@pytest.mark.live` round-trip test gated on ADC being present (skipped otherwise, same pattern as
    Azure's live tests) — can only really be run on the office laptop, not this dev machine.
  - [ ] **Blocked on the user**: `view_video` tool — whether Vertex AI video input goes through the Files
    API (`client.files.upload`, confirmed to exist on the SDK's Vertex client object, but unconfirmed
    whether the backend endpoint actually serves it — Vertex more commonly expects a `gs://` Cloud Storage
    URI instead) or inline bytes (works for small files on any backend, no upload step). Asked the user to
    run a two-path probe on the office laptop; the rest of this milestone doesn't depend on the answer and
    proceeds in parallel.

### Revamp (2026-10-02) — Forge replicates Claude Code (D-151..D-156)
- [x] D-151 run log: `llm_call` events + `forge log-summary`
- [x] D-152/D-154 modules: tiers, MODULE.md per module, boundary test; agent split into agent/subagents/workflow
- [x] D-153 a chat message answers open approval cards; build id in `forge --version` / `forge doctor`
- [x] D-155 no stuck detector or escalation ladder; the model improvises failure recovery
- [x] D-156 docs: spec §0.2 + banners, SPEC_DEVIATIONS, CLAUDE.md, MODULES.md, memory
- [x] D-156 code step 1 (D-158, 2026-10-03): `learning` retired; memory = FORGE.md + auto-memory (typed files + MEMORY.md, user and project scope). The empty Lessons panel was removed from the React UI on 2026-10-03 (D-198)
- [x] D-156 code step 2 (D-159, 2026-10-03): verify ladders, tools, test guard, export smoke check retired; Mode B harness kept (PYTEST_ADDOPTS)
- [x] D-156 code step 3 (D-160, 2026-10-03): `kb` retired; credential-table detection kept in `db`; `/init` now has the model explore and write FORGE.md
- [x] Timeline UI (D-189, D-190, D-192): narration, folded Read/Grep runs, Bash/Edit with output, inline diffs, nested subagents, failures open. The rail was dropped (superseded by the Conversation look).
- [x] Run map (D-193): the D-133 redesign was already built; its two skipped tests are rewritten (`test_web_runmap_e2e.py`) and per-agent cost added
- [x] **DROPPED (D-161)**: role-specific toolsets, lazy tool schemas, prompt fragments. Forge does not optimise token cost at runtime; accuracy and speed first

- [x] First Mode B end-to-end campaign (2026-10-03): attendance, bakery, invoice projects; D-162..D-170; report in docs/E2E_CAMPAIGN_2026-10-03.md

### Codex comparison gaps (2026-10-03) — spec in docs/SPEC_CODEX_GAPS.md
- [x] G1 Parallel subagents: first test whether concurrent `spawn_subagent` calls already run in parallel; parallel only for read-only agents; cap; subagent id in events
- [x] G2 `pre_compact` / `post_compact` hooks in `HooksConfig`
- [x] G4 Per-agent settings in custom agent files (max_steps, role, write folder)
- [x] G6 `todo_write` tool: lightweight model-kept todo list (no approval), event + UI, survives compaction
- [x] G7 `monitor` tool: wait on a background process for a pattern, exit or timeout (replaces poll loops)

### Later, only if real runs need it
- [x] (done 2026-10-03, D-189) UI: Claude Code layout for tool calls in the web chat (user chose option A, 2026-10-03): each call a card in order with the tool name, an IN block (command/path/arguments) and an OUT block, long output collapsed behind "show more" (about 15 lines), edits shown as diffs, failures open, reasoning summaries dim, subagent calls nested and collapsed (D-181). Redaction applies. Check with headless Edge screenshots.

### UI redesign (D-184..D-204, 2026-10-03 / 2026-10-04) — done
- [x] Login, home, project list with memory summary, account screen (change password), Apple-style design on the whole app (D-184..D-197)
- [x] Setup: first-run guide for the `.env` file (path, template, what is filled in), keys never typed into the app (D-204); Environment drawer with a test per
  connection incl. the Forge database and the read-only Development database; model plan to confirm; Tesseract/Gemini asked first (D-186, D-201)
- [x] Chat: welcome, Conversation look, tool-call blocks, diffs, folded read/search runs, nested subagents, todo strip, full tool output (D-188..D-192, D-195)
- [x] Run map tests rewritten and per-agent cost (D-193); Contracts panel (D-194); Learning tab removed (D-198); cleanups (D-199)
- [x] Shell: indirect `.env` reads always ask (D-187); Forge's own variables hidden from commands (D-202)
- [x] Tesseract: the `ocr_image` tool the model can call (D-203)
- [x] Gemini provider built and pushed (D-150, D-205): adapter, router dispatch, drawer real call + (i) steps; project/location optional
- [x] Mode B project folder may be non-empty (D-211)
- [x] Tavily through the company platform (D-210); direct Tavily key code removed; untested against the real platform (needs the user's token)
- [x] Web research chain (D-209): guard, PDF + Markdown extraction, headless-browser fallback, archive/snippet fallbacks, `researcher` subagent, `web-research` skill, SearXNG provider
- [x] Read grants (D-208): `/allow-read`, `/revoke-read`, typed paths, installed skills readable in both modes; no skill copies
- [x] `forge skill add/list/remove` (D-207): third-party skills like Claude Code; `load_skill` reads a skill's own files
- [x] gpt-4o on a second Azure resource as the optional fallback model (D-206), pushed 2026-10-04
- [x] Pushed 2026-10-04: the redesign (953e2c5 .. 38c6912, 24 commits) is on origin/main

### Design upgrades for apps DebCraft builds (D-245..D-251, 2026-10-12) — goal: world-class UI/UX without a stronger model
Done and pushed:
- [x] Style audit on every screenshot, Tailwind setup check, look-before-done gate (D-245)
- [x] Retry/fallback reason shown in the chat; no design-style questions (D-246)
- [x] show_app tries 127.0.0.1, localhost and [::1]; start_background `cwd` (D-247, D-248)
- [x] Reference recipes, independent `design-critic` with a SHIP/REVISE gate, stricter audit, identical-screenshot guard (D-249)
- [x] DESIGN.md workflow, taste checks, redesign protocol, on-demand brand references (D-250)
- [x] Tested library: style directions, modern CSS, motion kit, native components, vetted sources (D-251)