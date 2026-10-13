# Overnight 2026-10-14: what was done, what to do in the morning

Nothing was pushed. All work is in local commits on `main` (last pushed: `a69f1fe`). Say "push" when you have looked.

## Done tonight (each with tests and a D-note)
| Item | Result |
|---|---|
| Merge `web-design`, one speed rerun | Merged (D-312, D-313). Speed-4, page redesign: 509 s, $0.62, 6/7 checks (speed-1 was 1487 s, $1.51) |
| Template imitation for tests | A 10-slide infographic-style test template (dark/light twins, sticky "Delete before using" note, shape-drawn infographic); DebCraft removes the notes, picks matching dark/light samples, fits text, fills picture frames (D-334, D-335) |
| P2.24 | `describe_design`: reads the design of any deck (D-336) |
| P2.25 | `analyze_reference_image` / `compare_to_reference`: a design shown as a picture is measured and scored (D-337). Skill now says: judge essence over an exact copy, and say plainly what was kept or changed |
| P2.19 | `read_source_document`: Word, Excel, CSV, PDF into a digest for a deck (D-338) |
| W0 | `docs/DOCUMENTS_CLEAN_ROOM.md` |
| W2 | Excel: `build_workbook`, `read_workbook`, `edit_workbook`, `check_workbook`, skill `make-spreadsheet`; Excel recalculation checked live on this machine (D-339) |
| S6 (part) | npm uses its cache, no audit/fund calls (D-340) |
| C17 | "Run report" download button in the Files panel (D-341) |

## For you in the morning
1. `git push` (say "push").
2. On the office laptop, pull and run: `scripts/dev/reach_smoke.py`, `scripts/dev/template_look.py`, `forge template-probe <your template>` (see `docs/TEMPLATE_PROBE.md`); send the report back.
3. Send reference pictures of designs you want matched (P2.25) and a few sample Word/Excel/PDF files.
4. Still owed from before: S7 deployment name, the three-design web task rerun, the `npx shadcn` test, optional Pexels/Unsplash/Pixabay keys.

## Not done / open
- Word (W1), PDF (W3), shared pieces (W4), document benchmark (W5); Excel: messy-CSV cleaning and modelling-convention checks.
- S6: audit only changed pages; sandbox start-up measure.
- Nothing has been verified on your real company template yet: only on the test template.
