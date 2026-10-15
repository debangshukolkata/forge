# Overnight 2026-10-15: what was done, what to do in the morning

Work is in local commits (nothing pushed). The list was TODO.md section 0c. This file is updated as items finish; the section "Status" at the end says where it stopped.

## Done (each with tests and a D-note)
| Item | Result |
|---|---|
| 6 Progress for tool-made model calls and Gemini | `ToolContext.ask_model` heartbeat for view_image, design_candidates, critique_document; Gemini stream progress (D-367) |
| 7 S6 rest | Measured: tools are not the bottleneck (browser_screenshot 2.2 s, run_command 1.4 s); `spawn_subagent` is 34 % of the wall time; the verifier no longer scripts a static page (D-368) |
| 8 L9 | Audit findings name what sticks out (with the cause) and which images lack alt text (D-369) |
| 9 D1, D2 | A note when one UI file is changed 6, 10, 14 ... times (D-370); D2 closed with measurements |
| 12 Document extras | True PDF redaction `redact_pdf` (D-373); PDFs in Bengali, Devanagari and other scripts through the browser engine (D-374); document themes shared with decks `theme:<name>` (D-375) |
| 13 (part) | `save_brand`: the company look saved once in `brand.json` (D-378) |
| 14 Platform housekeeping | `browser` test marker for a fast run; parallel pytest prompt line (D-371) |
| 15 C8 | `library_api`: the installed library's real names, signatures, nearest matches (D-372) |
| 11 AS1 React | Five app screens as React with an HTML-to-JSX converter (D-377); build and type-check pass |
| 18 C15 | `with_servers.py` helper for the verifier's browser scripts (D-376) |
| 1/3 findings | From the log of the first X8 serial run: control characters in file writes refused with the fix (a mangled en dash made a page 'binary'), no test-run gate for tasks that only changed pages, `.forge/candidates` importable by `design_md_import` (D-379) |
| 10 (part) | Design gallery `docs/DESIGN_GALLERY.md` (every composition, screen, design system, template with pictures) |
| 17 (part) | shadcn/ui rules and re-theme notes in our own words (L5 b, c, d) |
| 20 prepared | Eight approach challenges and a time-boxed runner (`scripts/benchmark/run_challenges.py`), seeds checked by tests |

## Waiting on the benchmark runs (1 to 5 of the list)
X8 is finished (parallel builders 46 percent faster, 18 percent cheaper, docs/SPEED_BENCHMARK.md, D-380). The design benchmark and the coding benchmark wait until the end (see Status).

## For you in the morning
1. `git push` (say "push"). The work is on branch `night` in the worktree `../Forge-night` and is merged into `main` at the end of the night.
2. On the office laptop: `git pull`, then `.venv\Scripts\python scripts\dev\gemini_probe.py --out gemini2.txt` (the Gemini 3 decision, TODO section 1).
3. The new gates and behaviour changes to review are listed under "Gates added" below.

## Gates added (for your review)
- D1 note (not a refusal) after 6 edits of one UI file (D-370).
- The verifier skips the script on a static page (D-368).
- File writes that would add control characters are refused with the place and the fix (D-379).
- The test-run gate of `task_update` counts code edits only: pages, stylesheets, notes, pictures and fonts do not trigger it (D-379).
- `browser_screenshot` reloads the page when files changed since it was opened (D-391).
- (more are listed here as the coding challenges add them)

## Not done / open
- Items 1 to 5, 10, 13 (logo, font pairings), 16, 17, 18 (C14), 20: see Status.

## Status (2026-10-15, about 09:30 IST, machine restarted by the user)
- `main` and `night` are the same commit (D-391); nothing is pushed since `c109109`. Nothing is running.
- **Design benchmark:** `night-1` was stopped after d03 and 12 screenshots of d04, because the audit judged stale pages (D-391: `browser_screenshot` did not reload after edits, so a fixed font was still reported as a system-font blocker; d03 ended with 3 of 5 tasks blocked). A rerun `night-2` was started and stopped again by the user's choice: benchmarks and the coding challenges run **at the end**, on the final code, when nothing else needs the machine. Rerun d01 (museum), d03, d04, d05 on the fixed code; d02 passed its audit on the old code.
- **Edge tests still failing** (run 2026-10-15 on main): `tests/test_micro_effects.py` reduced-motion test fails for about 40 effects ("transitions still run under reduced motion"; the test reads `1e-05s` as 5 s, a test bug in `longest_seconds`, and some effects may also need `transition: none` in `motion-micro.css`); `tests/test_motion_hooks.py::test_the_five_assets_are_in_the_catalogue`; `tests/test_motion_canvas.py::test_under_reduced_motion_they_are_drawn_once_and_stay_still`. Not yet investigated. `tests/test_sections.py` (3 new templates + `tpl-pricing-invoicing`) and `tests/test_app_screens_react.py` not yet run after the merge.
- **Built since the last status:** brand-kit logo in Word and PDF headers (D-388), pricing page template (D-389, Vite build and audit pending), font pairings (D-390), reload after edits (D-391), `scripts/dev/night_status.py`, stale ticks D1, D2, L9 closed.
- **Order for what is left:** fix the three failing Edge tests, run test_sections and test_app_screens_react, full suite, then benchmarks (design rerun, C1), then the coding challenges (command in `tests/benchmarks/challenges/README.md`), then the morning summary.
