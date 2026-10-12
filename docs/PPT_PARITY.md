# Presentations: the open tasks to match Claude's PowerPoint abilities

Goal (user, 2026-10-09): DebCraft should be able to make presentations the way Claude does: same range of skills, same quality of
result. Open tasks are tracked in [TODO.md](../TODO.md); this file is the background.

## Read this first: what "exactly" can and cannot mean

- **We cannot copy Claude's skill.** Anthropic's pptx skill is under a license that forbids keeping copies and making derivative
  works (checked 2026-10-09). DebCraft's version is our own work: same *capabilities*, own code, own wording.
- **Identical output is not possible and not the target.** The result depends on the model (DebCraft runs on the user's Azure
  deployment, Claude on Claude) as much as on the tooling. The target is **equivalent capability and equivalent quality**,
  proved by a benchmark (task P0.1), not by comparing files.
- Claude's skill is a bundle: a way to *create* decks (design from code), a way to *edit* decks at the file-format level, a way to
  *render and look* at every slide, a *validator* that catches files PowerPoint would refuse, and a long list of *design rules*.
  The open tasks below are grouped the same way.

## Done so far (D-240, D-241, D-242)

- [x] Own skill `make-presentation` (story first, outline, design rules, build / look / fix loop)
- [x] Build a real editable .pptx from an outline: 11 layouts incl. `freeform`, native charts and tables, 3 themes, speaker notes, alt text, text sized to fit
- [x] Free-form design: place text, shapes, lines, images, charts, tables anywhere; checks for off-slide, edge, collisions, fit, small text, contrast, alt text
- [x] Read an existing deck; edit it (replace text, set text, notes, delete / move / duplicate / add slides, update charts and tables) keeping formatting; use a template's layouts
- [x] Look at the result: PowerPoint exports a picture per slide (Windows with PowerPoint only), the model views them and fixes
- [x] Live-verified on the build machine with the real model (build, preview, edit, free-form)

## Decisions the user must make (they change the size of the work)

1. **Design engine.** (a) keep improving the free-form element list (cheaper, already built), or (b) add an HTML/CSS design path:
   the model writes a slide as HTML, a headless browser measures every element, and DebCraft writes the same boxes and styles into
   the .pptx (Claude's approach; much more design freedom, large job). Recommendation: do the cheap free-form helpers first (P1),
   decide on (b) after the benchmark shows where quality is lacking.
2. **Rendering without PowerPoint.** Today pictures need PowerPoint. Options: LibreOffice if present (needs an install, often
   needs admin rights), or our own approximate renderer from the HTML path. Matters for Mac/Linux, servers, CI and any
   laptop without PowerPoint. Recommendation: optional LibreOffice support, plus PowerPoint as now.
3. **Icons and images.** Icons need a licensed icon set (Lucide ISC, Material Symbols Apache-2.0 are candidates) turned into
   pictures or shapes. Generated images (photos, illustrations) need an image model: do we have one on the Azure side? Without it
   DebCraft can only use pictures the user supplies, draw shapes, and make charts.
4. **Reference decks.** Collect 5 to 10 decks (made by Claude or anyone) that the user likes. They become design targets and the
   benchmark's reference (P0.1).

## The task list moved

The P0 to P3 tasks (with sizes and what each needs) are now in [TODO.md](../TODO.md) section "4. Presentations", and the four decisions and the laptop check are in section "1. Waiting on you". This file keeps the background, the licence note, what is done and the suggested order. Task IDs (P0.1 ... P3.5) are unchanged.

## Sibling skills (not in this list, same method if wanted)

Claude also ships document skills for Word, Excel and PDF. They carry the same license restriction and would need their own clean builds.
Not planned; ask if wanted.

## Suggested order

1. P0.2 (laptop check, user) and P0.1 (benchmark) so every later change is measured.
2. P1.1 to P1.8 (small, mostly one session each): contact sheet, UI previews, layout helpers, rich text, generic-look fixes, validator.
3. P2.1 to P2.6 and P2.18 (design strength), then P2.10 to P2.12 (templates and editing, the biggest business value).
4. Decide 1 and 2 using benchmark scores, then P3.1 / P3.2, then the rest of P2.

Rough effort for everything: P1 about 2 to 3 days, P2 about 3 to 4 weeks, P3 about 2 to 3 weeks of focused work, plus the benchmark runs.
