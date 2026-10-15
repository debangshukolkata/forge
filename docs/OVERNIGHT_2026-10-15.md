# 2026-10-15: what was done, what was measured, what to do next

Written for the person who owns DebCraft, not for a programmer. Everything below is pushed to `main` (the last push was `46a16a5`; later local commits are listed in `git log`). The list of work was TODO.md section 0c;
every decision has a number in docs/DECISIONS.md (D-362 to D-430).

## What to do next (about 30 minutes, then the A/B when you have an hour free)

1. **Update the laptop:** `git pull` in `C:\Work\LocalDevelopment\forge-main` (or copy the folder over), then double-click `Start-DebCraft.cmd`. It now runs the doctor first (one line per check, saved in `doctor-report.txt`).
2. **Check the `.env`** (`C:\Users\211258\.forge\.env`): the second Azure resource needs `AZURE_FALLBACK_ENDPOINT`, `AZURE_FALLBACK_API_KEY`, `AZURE_FALLBACK_API_VERSION`, `AZURE_FALLBACK_DEPLOYMENT`, `AZURE_STRONG_DEPLOYMENT="aicloud-gpt-5.4"` and `AZURE_GPT52_DEPLOYMENT="aicloud-gpt-5.2"`. You did this; the doctor showed all models OK.
3. **Environment panel:** answer Yes to Gemini, press **Test all** (the model lists stay locked until every test has finished), look at the proposals and press **Save models**. The proposals are: coder gpt-5.1, knowledge builder, summariser and vision gpt-5.1; planner, design critic, judge and reviewer Gemini 4 Argon (else Gemini 3.1 Pro, else gpt-5.2); fallback Gemini 3.1 Pro (else gpt-5.4, gpt-5.2). Rows you change by hand are remembered; the others follow later proposals.
4. **The Gemini A/B** (docs/LAPTOP_AB.md): two small briefs first, about 25 minutes. It tells whether Argon as critic and judge makes the pages better. Send me the two `results.md` files and say which pages you like more.

## What was built and measured

| Area | Result |
|---|---|
| **Speed** | Parallel design builders (`build_variants`): three throwaway designs 46 percent faster and 18 percent cheaper than one after the other (D-380). Where time goes was measured: subagents are 34 percent of the wall time. |
| **Benchmarks** | Design: all four briefs complete on the final code with 0 or 1 audit findings (docs/DESIGN_BENCHMARK.md); a bug found on the way (the audit judged a stale page) is fixed (D-391). Coding: 13 of 14 tasks, 309 of 310 tests, no regression; gpt-5.4 as coder gave the same results, 39 percent slower and 2.9 times the cost (D-414). Approach challenges: ten, three rounds (docs/CODE_BENCHMARK.md). |
| **Design material** | 24 application screens, each also as React; 7 page compositions, also as React; 40 small animations, 5 React effects, 3 canvas effects; shop, conference, docs and pricing templates with pictures; a picture for every section and direction; font pairings with Bengali and Hindi pictures; the gallery `docs/DESIGN_GALLERY.md`. |
| **Documents and decks** | True PDF redaction; PDFs in Bengali, Devanagari and other scripts; company look saved with the project (`brand.json`), logo in Word, PDF and decks; six font pairings; 670 real decks from open repositories swept through the readers (one defect fixed, D-399). |
| **Models** | Gemini 3 models and Gemini 4 Argon answer on your project from the `global` region (the earlier failure was a certificate error plus the wrong region). New roles: design critic and planner. The "independent" design critic had been running on the builder's own model; now it is a separate role (D-409). A rate limit or outage falls back to a model of another provider (D-411). gpt-5.2 added (D-413). |
| **shadcn and certificates** | `shadcn_setup` does the whole setup (Tailwind, alias, init, components) and was run against the real network; a certificate failure is recovered by exporting the Windows certificates for Node (D-401, D-402). Verified on your laptop. |
| **Environment panel and start-up** | Models list every model with its state; the lists unlock only after a full test (D-415); saved choices no longer freeze old proposals (D-416); a Node row; the doctor runs at every start; `Debcraft-Doctor.cmd`. |
| **Everyday tools** | `scripts/dev/quick_check.py` (lint plus only the tests that touch what changed), `--mini` design briefs, `night_status.py`, the skill A/B loop `run_skill_ab.py` (D-417), the reference-deck sweep. |

## Gates added (for your review): each is one reminder, never a trap, only in real sessions

1. Before the first edit of existing code the tests must have run (or a test been written): refused once, with the reason (D-408).
2. Replacing most of an existing file of 30 lines or more in one write is refused once until a test has been written (D-410).
3. Before a turn ends, the loop asks once for the risks found in the files it read (unsafe loading, committed secrets, SQL built from strings, shell commands from strings, eval, certificate checks off) if the reply does not name them (D-410).
4. `design_candidates` refuses a composition that is not a catalogue id (D-406).
5. A control character in a file write is refused with the place and the fix (D-379).

## Later the same day: the Design Intelligence Engine (D-415 to D-429)

| Item | What it is now |
|---|---|
| Pages that looked machine-made (D-419) | The audit finds controls in the browser font, text running together, uneven cards, grooved fieldsets, and a booking page with no pictures; recipes fixed. |
| DIE1 discovery (D-422) | `design_inspire` also measures the type scale and the sections; each page gets a reference note (principles to reuse, the brand's own not to copy); the design skill starts with a look at the field for brand pages. Not proven to help yet. |
| DIE2 blueprint (D-421) | `design_md_lint` notes missing Page Composition, Imagery, Motion, Responsive and Accessibility sections and decisions with no reason; the template and the drafts carry the sections. |
| DIE3 knowledge base (D-426) | `design_kb_add`, `design_kb_search`; references and the last designs' palette, fonts and composition live in your profile folder. |
| DIE4 art director (D-427) | A read-only subagent on the planner role returns a complete DESIGN.md; it is one of the design candidates. |
| DIE5 gate (D-425, D-428) | Card density in the audit; a note when a design resembles one of the last five. |
| DIE6 imagery (D-423, D-429) | Your `brand-assets` folder first; the bundled CC0 Open Doodles recoloured to the accent; unDraw only as files you download by hand (D-420). |
| DIE8 taste test (D-424) | Runbook docs/DESIGN_TASTE_TEST.md: Argon against gpt-5.1 in three arms, a blind gallery. Waits for the office laptop. |
| Candidates shown to you (D-430) | When the look is open, DebCraft asks which candidate design you want, with each specimen picture in the question card. Skipped when you supplied a DESIGN.md or brand guide, the brief names the style, or you said not to ask. |
| Live check (DIE9) | Two `--mini` briefs on the new code: both delivered, 0 audit findings. The model ignored the knowledge base, art director and candidate question at first; the steps were then moved into the system prompt and tool results and re-checked (`live-check-2`). |

## What is still open

- **Measuring Gemini on your laptop** (docs/LAPTOP_AB.md): Argon as critic and judge, and as planner. This machine has no Google credentials. Nothing about Gemini inside a long agent session has been verified, only short calls.
- **Prices in the config** for Gemini and gpt-5.2/5.4 are placeholders; replace them with your contract prices for correct cost numbers.
- **The skill A/B** (C14) is built; its first measurements (for example `test-first` on the four hard coding tasks) are cheap and not run yet.
- **A real company template** would still test the template mode better than 670 public test decks; only if you want it.
- **Not built on purpose:** best-of-N design candidates (no run-to-run variance seen), per-task routing between gpt-5.1 and gpt-5.4 (loses the cache and the reasoning thread; the benchmark gave no reason), a built hero per candidate, the ask-me-first setting, a logo for workbooks.

## Mistakes worth knowing

- I stopped every Python process once (it killed your `forge ui` on port 8765). I stop only the processes I started now.
- The first design benchmark judged stale pages (fixed, D-391) and was rerun.
- The gpt-5.4 benchmark first failed in seconds because the deployment name was not passed in; fixed and rerun.
