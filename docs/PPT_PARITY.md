# Presentations: the open tasks to match Claude's PowerPoint abilities

Goal (user, 2026-10-09): Forge should be able to make presentations the way Claude does: same range of skills, same quality of
result. This file lists everything still open, in order, with size and how we will know it is done. Nothing below is started
unless marked. Status: `[ ]` open, `[~]` in progress, `[x]` done.

## Read this first: what "exactly" can and cannot mean

- **We cannot copy Claude's skill.** Anthropic's pptx skill is under a license that forbids keeping copies and making derivative
  works (checked 2026-10-09). Forge's version is our own work: same *capabilities*, own code, own wording.
- **Identical output is not possible and not the target.** The result depends on the model (Forge runs on the user's Azure
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
   the model writes a slide as HTML, a headless browser measures every element, and Forge writes the same boxes and styles into
   the .pptx (Claude's approach; much more design freedom, large job). Recommendation: do the cheap free-form helpers first (P1),
   decide on (b) after the benchmark shows where quality is lacking.
2. **Rendering without PowerPoint.** Today pictures need PowerPoint. Options: LibreOffice if present (needs an install, often
   needs admin rights), or our own approximate renderer from the HTML path. Matters for Mac/Linux, servers, CI and any
   laptop without PowerPoint. Recommendation: optional LibreOffice support, plus PowerPoint as now.
3. **Icons and images.** Icons need a licensed icon set (Lucide ISC, Material Symbols Apache-2.0 are candidates) turned into
   pictures or shapes. Generated images (photos, illustrations) need an image model: do we have one on the Azure side? Without it
   Forge can only use pictures the user supplies, draw shapes, and make charts.
4. **Reference decks.** Collect 5 to 10 decks (made by Claude or anyone) that the user likes. They become design targets and the
   benchmark's reference (P0.1).

## P0 Measure first (so "equivalent" is a number, not a feeling)

- [ ] **P0.1 Parity benchmark.** 20 to 30 fixed requests across kinds (status update, pitch, training, data story, technical design
  review, template fill, edit-an-existing-deck, redesign-a-bad-deck, long deck, deck from a document). Each has a checklist
  (story, hierarchy, contrast, alignment, no overflow, file opens cleanly, notes present, charts native) scored by the real model
  as judge looking at the rendered slides, plus the user's own ratings of a sample. Re-run after every change; record scores in
  `docs/PPT_BENCHMARK.md`. Size M. Needs decision 4.
- [ ] **P0.2 Verify on the office laptop** (user action): python-pptx installs through pip; PowerPoint picture export works under company
  policy and Protected View; `Start-Forge.cmd` installs the `slides` extra. Size S.

## P1 Quick wins (small, high value)

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

## P2 Capability gaps (medium)

Create / design
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
  fonts/colours, so a Forge deck re-themes correctly in PowerPoint and new slides added by hand look right. Size L.
- [ ] **P2.8 Slide features.** Sections, hidden slides, transitions, basic entrance animations, slide numbers, comments (read and add). Size M to L.
- [ ] **P2.9 Accessibility pass.** Reading order, alt text everywhere, document language and title, colour-blind-safe palettes. Size S.

Existing decks and templates
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

Looking at the result
- [ ] **P2.18 Reliable overflow detection.** With PowerPoint present, measure each text box's real text height through PowerPoint
  instead of our estimate; without it keep the estimate. Size M.

Input and workflow
- [ ] **P2.19 Build from documents.** Read Word, Excel/CSV and PDF sources (Forge has PDF page rendering only) and turn them into a deck:
  summarise, pick charts, cite sources in notes. Size M.
- [ ] **P2.20 Storyline guides.** Short guides in the skill for common decks (board update, pitch, QBR, design review, training, project
  status), including slide counts, timing and speaker-note style. Size S.

## P3 Large or platform work

- [ ] **P3.1 HTML/CSS design path** (decision 1b): `build_presentation` accepts slides written as HTML/CSS and converts the measured result
  to native .pptx shapes (text boxes, shapes, images, charts as native objects where possible). Gives full design freedom with flexbox/grid
  layout, fonts, gradients and shadows. Uses the headless browser already in `forge[browser]`. Size L.
- [ ] **P3.2 Render without PowerPoint** (decision 2): optional LibreOffice rendering; or our own renderer from P3.1. Includes a font-substitution
  warning so fit checks are trusted only for fonts that render true-to-width. Size L.
- [ ] **P3.3 Performance and size.** Large decks (100+ slides), image downscaling and compression, file-size limits, time limits on preview. Size M.
- [ ] **P3.4 Security review of the presentation tools.** Untrusted decks (zip and XML bombs, external relationships/links, embedded
  objects), PowerPoint COM launch, files outside the workspace, Mode B (host-identifying terms in slide text). Size M.
- [ ] **P3.5 Documentation.** A user guide ("how to ask Forge for a deck"), examples gallery generated from the benchmark. Size S.

## Sibling skills (not in this list, same method if wanted)

Claude also ships document skills for Word, Excel and PDF. They carry the same license restriction and would need their own clean builds.
Not planned; ask if wanted.

## Suggested order

1. P0.2 (laptop check, user) and P0.1 (benchmark) so every later change is measured.
2. P1.1 to P1.8 (small, mostly one session each): contact sheet, UI previews, layout helpers, rich text, generic-look fixes, validator.
3. P2.1 to P2.6 and P2.18 (design strength), then P2.10 to P2.12 (templates and editing, the biggest business value).
4. Decide 1 and 2 using benchmark scores, then P3.1 / P3.2, then the rest of P2.

Rough effort for everything: P1 about 2 to 3 days, P2 about 3 to 4 weeks, P3 about 2 to 3 weeks of focused work, plus the benchmark runs.
