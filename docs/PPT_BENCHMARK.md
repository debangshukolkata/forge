# Presentation parity benchmark (TODO P0.1)

How it works: `scripts/benchmark/run_deck_benchmark.py <run-name>` runs DebCraft on each request in `tests/benchmarks/decks`
(20 requests; the aim is 20 to 30), then scores each delivered deck with automatic checks (opens, package valid,
PowerPoint-measured overflow, slide count, notes, native charts, titles, smallest font) and a judge: the real model looking at
PowerPoint's own pictures of every slide, scoring story, hierarchy, contrast, alignment, polish and fit from 1 to 5. The judge
is a model, so it is generous (a competent generic deck gets 4); use it to compare runs, and the user's own ratings of a few
decks as the final check. Results land in `C:\Work\ForgeRuns\deckbench\<run-name>`.

Ranges for slide counts and chart counts are guesses and are tuned as the requests are refined; the first baseline used
"min 1 chart" for three requests that did not ask for one.

## baseline-1 (2026-10-13, before the template-mode work)

### Run `baseline-1` (2026-10-13 11:59)

| Task | Slides | Auto | Overflow | Notes % | Story | Hier. | Contr. | Align. | Polish | Fit | Judge avg | Wall | Cost |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| d01_status_update | 6 | 4/6 | 0 | 100 | 4 | 4 | 5 | 4 | 4 | 5 | 4.3 | 322s | $0.42 |
| d02_investor_pitch | 11 | 4/6 | 4 | 100 | 4 | 4 | 5 | 5 | 4 | 5 | 4.5 | 161s | $0.30 |
| d03_training | 32 | 2/6 | 1 | 100 | 4 | 4 | 5 | 4 | 3 | 3 | 3.8 | 235s | $0.48 |
| d04_data_story | 9 | 5/6 | 0 | 100 | 4 | 4 | 5 | 4 | 4 | 5 | 4.3 | 356s | $0.52 |
| d05_design_review | 13 | 4/6 | 0 | 100 | 5 | 4 | 5 | 4 | 4 | 4 | 4.3 | 147s | $0.24 |
| d06_template_fill | 6 | 6/6 | 0 | 100 | 4 | 4 | 5 | 4 | 4 | 4 | 4.2 | 120s | $0.19 |
| d07_edit_deck | 6 | 5/6 | 0 | 100 | 3 | 4 | 5 | 4 | 3 | 3 | 3.7 | 87s | $0.10 |
| d08_redesign | 6 | 5/6 | 0 | 100 | 5 | 5 | 5 | 5 | 5 | 5 | 5.0 | 282s | $0.36 |
| d09_long_deck | 20 | 4/6 | 0 | 100 | 4 | 4 | 5 | 4 | 3 | 4 | 4.0 | 201s | $0.31 |
| d10_workshop | 24 | 4/6 | 0 | 100 | 4 | 4 | 5 | 5 | 4 | 5 | 4.5 | 208s | $0.30 |
| d11_product_launch | 9 | 4/6 | 0 | 100 | 4 | 4 | 5 | 5 | 4 | 4 | 4.3 | 101s | $0.17 |
| d12_document_deck | 13 | 4/6 | 0 | 100 | 4 | 4 | 4 | 4 | 4 | 4 | 4.0 | 267s | $0.35 |

Delivered: 12/12; mean judge score: 4.25.
- d01_status_update: The decision and amber status are not foregrounded enough, and the risks slide is text-heavy for busy executives.
- d02_investor_pitch: Too many dense bullet slides; the story would benefit from more visual storytelling and product imagery.
- d03_training: The deck is clear but feels generic and text-heavy, with limited interactive or visual elements for a 45-minute training session.
- d04_data_story: Too many dense bullet-only slides dilute the otherwise strong, visual data story.
- d05_design_review: Too many slides rely on dense bullets, and the 'Key risks and planned mitigations' slide lists risks without clearly stating mitigations.
- d06_template_fill: Content and design stay generic, with an extra invented Q4 initiative and bullet-heavy slides that feel more like a basic template than an executive-ready narrative.
- d07_edit_deck: The revenue chart still says FY24 and the decisions slide comes awkwardly after the thank-you, breaking both the brief and narrative flow.
- d08_redesign: Slides 2–3 are still plain bullet lists and could use more visual structure to match the polish of the later slides.
- d09_long_deck: Too many slides are plain bullet lists with little visual differentiation, making the deck feel generic rather than designed.
- d10_workshop: Too many slides rely on dense bullet lists, which makes the workshop feel more like a lecture than a hands-on session.
- d11_product_launch: The deck is clear but too text-heavy and generic for enabling sales/support to confidently sell Pulse.
- d12_document_deck: Content is still quite policy-heavy and text-dense for a 15‑minute staff briefing, with limited visual emphasis on actions and examples.
### What the baseline shows
- Mean judge score 4.25; nothing below 3.7. All 12 decks delivered and open cleanly.
- The same complaint on nearly every deck: **too many plain bullet slides**, not enough visual structure (cards, diagrams, big
  numbers, images). This is the biggest lever for the next runs (more layouts used by the model, the section library, icons).
- **Too many slides** for training (32), workshop (24) and the document briefing (13 for a 15-minute talk).
- **Edit a deck (d07):** a chart title still said FY24 after "replace every FY24"; the new slide was put after "Thank you" and styled
  differently. Fixes: `replace_text` should include chart titles and alt text; the skill should say where to add slides.
- PowerPoint measured 4 overflows in the pitch deck and 1 in the training deck that the build estimate did not catch.
- The smallest font in nearly every deck is the 11 pt footer the builder draws; the check now allows 10 pt.

## baseline-2 (2026-10-13, after P2.22: length and bullet-run lint, layout guidance, replace_text reach)

### Run `baseline-2` (2026-10-13 13:43)

| Task | Slides | Auto | Overflow | Notes % | Story | Hier. | Contr. | Align. | Polish | Fit | Judge avg | Wall | Cost |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| d01_status_update | 6 | 6/6 | 0 | 100 | 4 | 4 | 5 | 4 | 4 | 5 | 4.3 | 120s | $0.13 |
| d02_investor_pitch | 10 | 6/6 | 0 | 100 | 5 | 4 | 5 | 5 | 4 | 5 | 4.7 | 169s | $0.21 |
| d03_training | 15 | 5/6 | 0 | 100 | 4 | 4 | 5 | 4 | 3 | 4 | 4.0 | 283s | $0.50 |
| d04_data_story | 7 | 6/6 | 0 | 43 | 4 | 4 | 5 | 5 | 5 | 5 | 4.7 | 698s | $0.87 |
| d05_design_review | 13 | 6/6 | 0 | 100 | 5 | 4 | 5 | 4 | 4 | 5 | 4.5 | 274s | $0.42 |
| d06_template_fill | 7 | 6/6 | 0 | 71 | 4 | 3 | 5 | 4 | 2 | 2 | 3.3 | 127s | $0.18 |
| d07_edit_deck | 6 | 6/6 | 0 | 100 | 3 | 3 | 5 | 4 | 2 | 4 | 3.5 | 218s | $0.29 |
| d08_redesign | 3 | 4/6 | 0 | 0 | 4 | 3 | 5 | 4 | 2 | 5 | 3.8 | 117s | $0.16 |
| d09_long_deck | 20 | 6/6 | 0 | 100 | 4 | 4 | 4 | 4 | 4 | 5 | 4.2 | 349s | $0.56 |
| d10_workshop | 22 | 5/6 | 0 | 100 | 4 | 4 | 5 | 4 | 3 | 3 | 3.8 | 198s | $0.22 |
| d11_product_launch | 10 | 6/6 | 0 | 90 | 4 | 4 | 5 | 4 | 3 | 5 | 4.2 | 95s | $0.10 |
| d12_document_deck | 10 | 6/6 | 0 | 100 | 4 | 4 | 5 | 4 | 4 | 4 | 4.2 | 171s | $0.19 |

Delivered: 12/12; mean judge score: 4.10.
- d01_status_update: The exec ask and amber status are repeated and buried in text instead of being surfaced visually and once, upfront.
- d02_investor_pitch: Dense bullet slides and a cluttered ARR chart hold back an otherwise strong, investor-ready narrative.
- d03_training: Too many dense bullet slides make the 45-minute training feel templated rather than engaging and interactive.
- d04_data_story: Slides 6–7 are dense bullet walls that weaken the otherwise strong narrative and visual focus.
- d05_design_review: Diagram slides have cramped text and awkward connector lines that make the architecture and risks harder to scan quickly.
- d06_template_fill: The deck only partially uses the company template, creating an inconsistent and unbranded experience for leadership.
- d07_edit_deck: The new 'Decisions needed' slide is stylistically inconsistent and oddly placed after the closing 'Thank you' slide.
- d08_redesign: The deck keeps a basic bullet-list look instead of a visually redesigned, modern layout, so it still feels like a template wall of text.
- d09_long_deck: Too many dense bullet slides and a placeholder-style financial chart weaken engagement and clarity.
- d10_workshop: Too many slides are plain bullet lists with neutral titles, so the narrative feels generic and lacks visual and rhetorical punch for a 90‑minute workshop.
- d11_product_launch: Too many slides rely on plain bullet lists rather than more visual, sales-oriented storytelling.
- d12_document_deck: Too many dense bullet-list slides reduce impact and make it harder to see what changes in behaviour are most important.


### baseline-1 to baseline-2
- Mean judge 4.25 -> 4.10: within the judge's noise (one run each, a model judge); read the structure, not the decimals.
- Slides: training 32 -> 15, workshop 24 -> 22, document briefing 13 -> 10: the length rule works. Overflow measured by PowerPoint: 5 -> 0.
  Automatic checks passed 6/6 on 9 of 12 decks (the font check now allows the builder's 11 pt footer, so the two runs differ there).
- Still the same complaint on 9 of 12: too many plain bullet lists. The lint and the skill text did not change the model's habit enough.
- d07 (edit a deck) still put the new slide after "Thank you" and styled it differently: the skill text is not followed. A rule inside the
  tool is needed (`add_slide` without `at` inserts before a closing slide and copies the deck's body-slide formatting).
- d06 (template fill) scored lowest, 3.3: it only partly used the template. This is the case P2.21 (sample slides) was built for; baseline-3
  runs the new corporate-template request (d13) and d06 again with that code.
- d08 (redesign) kept a bullet-list look; d04 took 698 s ($0.87), the slowest and dearest, worth a look in the speed work.

Next: baseline-3 on all 20 requests with `--parallel 4`, after the fixes above.
