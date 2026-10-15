# Design benchmark (TODO DS5, D-352)

`scripts/benchmark/run_design_benchmark.py <run-name>` gives DebCraft two fixed briefs (`tests/benchmarks/design`: a children's science museum in Leeds, a
late-night ramen bar in Osaka), lets it build a one-page site on the real model, and scores the result:

- the page at desktop and phone width (sideways scroll, console errors, broken images);
- the style audit left on the finished page, and the DESIGN.md lint (errors and warnings);
- how many of six dimensions (tone, accent hue, display font, corners, density, layout energy) differ from the generic default;
- whether the design ladder was used (`.forge/design-rounds.json`);
- a blind judgement by the vision model on a desktop and a phone screenshot: typography, distinctiveness, hierarchy, harmony, fit, polish.

The judge's scale was made strict after the first run (see below): 5 is award-winning studio work, 3 is competent but template-like, 2 is the generic
machine-made look. Calibration: a deliberately dated bakery page scored 2-3, so the judge discriminates at the bottom; Forge's output now scores 3-4.

## Runs (one run per brief: noisy, compare conditions only with several runs)
| Run (2026-10-14/15) | What changed | Brief | Wall | Cost | Ladder | Lint err/warn | Differs from default | Audit left | Judge (type/dist/hier/harm/fit/polish) |
|---|---|---|---|---|---|---|---|---|---|
| design-1 | baseline: DS1-DS4 tools and skill available, nothing enforced; lenient judge | museum | 728 s | $1.08 | no | 0/7 | 1 | 2 | (judge then had no typography score) 5/4/5/5/5 |
| design-1 | same | ramen | 1116 s | $1.25 | no | 1/6 | 2 | 1 | 5/5/5/5/5 |
| design-2 | gate: a model-written DESIGN.md must be compared with candidates | museum | 1544 s | $2.00 | yes | 0/5 | 2 | 0 | 4/5/5/5/5 (lenient judge) |
| design-3 | tokens required, similar candidates refused, strict judge and typography score, system-font audit, concept and signature move in the skill | museum | 978 s | $1.40 | yes | 0/10 | 3 | 2 | 3/3/4/4/3/4 |
| design-3 | same | ramen | 1414 s | $1.38 | yes | 0/13 | 3 | 0 | 4/3/4/4/3/4 |
| design-4 | composition recipes, concept check, imagery audit, system-font blocker; a third brief (dashboard) | museum | 1541 s | $2.17 | yes | 0/15 | 3 | 4 | 4/3/4/4/3/4 |
| design-4 | same | ramen | 720 s | $1.03 | no (the gate was bypassed: see 6) | 0/9 | 2 | 0 | 4/4/5/5/5/5 |
| design-4 | same | dashboard | 1958 s | $2.81 | yes | 0/19 | 2 | 0 | 2/3/4/4/4/4 |

## What the runs showed
1. **The new tools were not used at all** in design-1: the model never called find_asset, the candidate tool, the linter or any font tool. Advice in a skill is
   not enough for this model; only gates change what it does (the same lesson as the DESIGN.md gate, D-312). The candidates gate (D-352) fixed this.
2. **The model ignored warnings and its own format.** In design-2 it wrote `palette:` and `type:` keys (not the token format) and its three "different"
   candidates were identical; the tool said so and it carried on. Now: a file with no tokens is a lint error, candidates that are too similar are refused
   (twice, then judged as they are), and the fingerprint reads any typography token.
3. **Every page was set in the system font stack** (system-ui, Segoe UI), even a Japanese ramen bar and a page whose DESIGN.md named Playfair Display and
   Baloo 2. No font tool was ever called. This is the strongest "machine-made" tell. Now: DESIGN.md system fonts warn, the audit reports a page whose text is all
   in the system stack as a BLOCKER that stops the task being marked done (lifted only when a brand guide says system fonts are required), and specimens
   embed the bundled fonts so a candidate is judged in its real type.
4. **The first judge was too kind** (5/5/5/5/5 for pages the user called generic). With anchors and a typography score it now gives 3s and 4s and names the
   right problem ("a generic tasteful café rather than a late-night Osaka ramen bar").
5. **After fonts, the next gap is concept and composition.** design-3's ramen page loaded real fonts (Fraunces-style serif with DM Sans) but is a cream
   page with one text column: the safe candidate won, and nothing in it comes from a neon alley at 3 am. Added: a concept and a signature move for every
   candidate, an audit rule for pages with no imagery. Still open: composition recipes for plain HTML, real imagery by default, and a stronger design-role
   model (TODO DS7 to DS9).
6. **Fourth run (design-4): fonts now load, the rest is still bypassed.** Real fonts were fetched and used (find_font and fetch_font appear in the log; typography 4 on two
   pages). But (a) the ramen run skipped the candidate comparison by writing the page again straight after the one-time note: the gate now refuses three times;
   (b) none of the runs used the composition recipes (no find_asset), so a candidate must now name `composition:` or it is not usable; (c) the museum page ended with no
   imagery although the audit said so: on a marketing page (three or more sections, no table, few fields) that finding now blocks done, unless the DESIGN.md says
   imagery is not wanted; (d) the dashboard named a font that was never loaded and the audit let it through: a named font now counts only if it is loaded or installed
   (measured in the browser), otherwise the page is treated as set in the system stack. The judge's worst problems are now about identity, not craft:
   "a generic dark-theme digital product aesthetic", "a generic modern museum page, lacking imagery and visual cues about experiments".

## Run night-2 (2026-10-15, final code of the night, one run per brief)

| Brief | Wall | Cost | Audit left | Sideways scroll | Judge (type/dist/hier/harm/fit/polish) | App screen copied |
|---|---|---|---|---|---|---|
| d01_science_museum | 2,727 s | $2.82 | 1 | no | 4/4/4/4/5/4 | no (ds-playful-friendly only) |
| d03_ops_dashboard | 985 s | $1.79 | 1 | phone | 4/4/4/4/4/4 | **no** |
| d04_member_table | 1,160 s | $1.65 | 0 | no | 4/3/4/4/4/4 | yes (app-table-data) |
| d05_booking_wizard | 1,380 s | $1.89 | 0 | no | 4/3/4/4/4/4 | **no** (ds-clean-product only) |

What it showed:
- The first attempt (`night-1`) judged stale pages: `browser_screenshot` did not reload after edits, so the audit kept reporting a system-font blocker after the fonts were linked and d03 ended with 3 of 5 tasks blocked (D-391). With the reload every brief completes with 0 or 1 audit finding left.
- The dashboard brief took 985 s and $1.79 against 2,658 s and $3.24 in speed-6 (different brief version, same kind of page; 66k output tokens against 95k).
- Candidate refusals are down to a patch, not a rewrite: the three DESIGN.md candidates were changed with one `multi_edit` each (D-393). Writes still repeated: index.html twice in d03 and d04.
- AS1 did not work in two of three application briefs: the model named invented compositions (`app-northline-bright-logistics`, `app-kestrel-booking-wizard`, `lay-admin-table`) that are not in the catalogue, so the real screens (`app-dashboard-ops`, `app-form-wizard`) were never copied and the pages were written from a blank file. Fix: `design_candidates` now refuses a composition that is not a catalogue id (naming the nearest real ones) and tells the winner to `add_asset` it (D-406). The effect is measured in the next benchmark run.
- The judge's worst problem in d04 and d05 is the same in each: "generic SaaS" look that does not reflect the product's world; d01 "generic rounded cards and gradients". The pipeline makes pages competent, not yet characterful.

## Limits of this measurement
Two briefs, one run each, a vision model as judge (the same family as the builder, calibrated only at the bottom of the scale). Do not read small
differences as signal; read the tool-use facts (ladder used, fonts loaded) and the worst problem the judge names.
