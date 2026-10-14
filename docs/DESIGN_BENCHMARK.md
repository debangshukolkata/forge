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

## Limits of this measurement
Two briefs, one run each, a vision model as judge (the same family as the builder, calibrated only at the bottom of the scale). Do not read small
differences as signal; read the tool-use facts (ladder used, fonts loaded) and the worst problem the judge names.
