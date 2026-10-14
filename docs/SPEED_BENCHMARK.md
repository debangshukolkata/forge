# Speed benchmark (TODO S2)

`scripts/benchmark/run_speed_benchmark.py <run-name>` runs three fixed tasks (`tests/benchmarks/speed`) on the real model and reports
where the time went, with a quality check per task. Run it alone (not next to another benchmark) so the numbers are not skewed by
shared rate limits or CPU. Compare two runs with `--compare <before> <after>`: a run whose quality dropped is rejected whatever its
speed (D-161).

| Task | What it measures | Quality check |
|---|---|---|
| s01_crud_api | a small FastAPI + SQLite app with `pip install`: model time, install time, test runs | 10 hidden tests |
| s02_install_and_test | environment set-up and a missing requirement: tool time dominates | hidden test run in the workspace's own environment |
| s03_page_redesign | redesign of a bad page with a browser look at desktop and phone width | 7 checks in headless Edge (no sideways scroll, no broken image, content kept, viewport meta, no obsolete tags, ...) |

Columns: Wall (first to last event), Model (sum of model call times), Tools (tool time without the time spent waiting for you),
Waited (questions and approvals), Other (engine work and overlap), First tool (seconds before the first tool call), Calls, input
tokens, cost. The "three-design task" and a Vite/npm install are not in this set yet: they need the node tooling to be verified on
the office laptop first.

## What the existing coding runs already show
In every coding benchmark run so far the model calls are 90 to 98 percent of the wall time (for example t13: 217 s of 223 s in model
calls, 5 s in tools). So the levers for speed are fewer and shorter model calls (parallel tool calls in one turn, less re-reading,
the verifier and critic running together) and not faster tools. Tool-side work only matters for installs and builds.

## Runs

### speed-1 (2026-10-13, the first baseline, before any speed change)

| Task | Quality | Wall | Model | Tools | Waited | Other | First tool | Calls | Tokens in | Cost |
|---|---|---|---|---|---|---|---|---|---|---|
| s01_crud_api | 10/10 | 236s | 189s | 45s | 0s | 1s | 29s | 22+23 | 588409 | $0.29 |
| s02_install_and_test | 2/2 | 81s | 72s | 8s | 0s | 0s | 12s | 7+11 | 106645 | $0.07 |
| s03_page_redesign | 6/7 | 1487s | 610s | 945s | 0s | -68s | 10s | 40+55 | 1991092 | $1.51 |

- s01_crud_api: tool time by tool {'run_command': 44, 'task_update': 1}; slowest: run_command 30s: python -m pip install fastapi uvicorn; run_command 5s: python -m pip install httpx2; run_command 2s: python -m pytest
- s02_install_and_test: tool time by tool {'run_command': 8}; slowest: run_command 7s: python -m pip install -r requirements.txt; run_command 1s: python -m pytest; edit_file 0s: edit requirements.txt
- s03_page_redesign: tool time by tool {'spawn_subagent': 680, 'start_background': 127, 'monitor': 60, 'view_image': 55, 'browser_screenshot': 15}; slowest: spawn_subagent 204s: subagent verifier: Verify the Sunrise Bakery one-page site a; spawn_subagent 127s: subagent design-critic: Fourth review of Sunrise Bakery page; spawn_subagent 84s: subagent design-critic: Second review of Sunrise Bakery page
### What speed-1 shows
- **The page redesign is the slow, dear task: 1487 s (25 minutes) and $1.51**, 15 times the small tasks. Tool time is 945 s and almost all of it is
  subagents: one verifier run (204 s) and four rounds of the design critic (84 to 127 s each), plus background dev server (127 s) and monitor
  (60 s). Model time is another 610 s over 40 calls. The checks inside the loop (D-249 critic gate) are what take the time.
- Quality was 6/7 (one check missed), so there is room to also gain quality, not only speed.
- Small tasks are quick: 236 s for the API (30 s of it one `pip install fastapi uvicorn`), 81 s for install-and-test.
- First tool call comes after 10 to 29 s: the model reads and plans first; a prompt that starts reading in parallel would save a little.

### Candidate speed changes to try (each judged on quality first, D-161)
1. Run the verifier and the first critic round in parallel, and stop after the second critic round when it ships (X1 exists for verifier + critic; check it fires in this flow).
2. Give the critic a smaller job on later rounds: only re-check the fixes it listed, not a full review.
3. Start the dev server in the background as soon as the files exist (X5 hint added; verify it does).
Compare each with `--compare speed-1 <new run>`.

### speed-2 (2026-10-13, after the critic change: judged against the brief, follow-up reviews check only earlier fixes, round notes)
Page redesign only: wall **1487 -> 975 s (-34 %)**, cost **$1.51 -> $0.73 (-52 %)**, model calls 40 -> 34, quality **6/7 -> 7/7**. The critic ran
twice instead of six times (68 s and 66 s) and the page no longer grew a contact form nobody asked for. One run each: the direction is
clear, the exact figures are not. Accepted (quality did not drop). What is left in the 975 s: model 486 s, tools 487 s of which
`start_background` 125 s (two starts of a plain static server of 63 s each, see S6), `monitor` 120 s, `browser_open` 49 s, `view_image` 46 s.

### speed-3 (2026-10-13, after D-302: servers ready when the port answers; unbuffered output; C2 quality gates also merged by then)
| Task | speed-1 | speed-2 | speed-3 |
|---|---|---|---|
| s01 crud api | 236 s, $0.29, 10/10 | - | 269 s, $0.33, 10/10 |
| s02 install and test | 81 s, $0.07, 2/2 | - | 134 s, $0.15, 2/2 |
| s03 page redesign | 1487 s, $1.51, 6/7 | 975 s, $0.73, 7/7 | 865 s, $1.06, 6/7 |

- `start_background` in the page redesign fell from 125 s to 6 s: D-302 works. The critic ran fewer rounds than in speed-1 (the verifier took 292 s this time).
- s01 and s02 look slower but those are one run each with a different model path (22 -> 34 and 7 -> 16 model calls). One real cause found in the s01
  events: the new quality gate (C2) sent the task back for `B008` on FastAPI's `db = Depends(get_db)`, a false positive for the idiom: B008 is
  removed from the gate's default rules. Run-to-run noise on short tasks is large; a fair comparison needs three runs each (not done yet).

### S8 experiment: lower reasoning effort after read-only steps (2026-10-13, D-307)
Switch under test: `FORGE_ADAPTIVE_EFFORT=low` (a step that follows only read-only tool results, such as reading, listing or searching, runs at low effort instead of the configured medium). The coding benchmark t01-t14, three tasks at a time, one run per arm.

| | hidden tests | tasks fully passed | wall (sum of tasks) | model time | model calls | cost |
|---|---|---|---|---|---|---|
| control | 309 / 310 | 13 / 14 | 3136 s | 2859 s | 182 | $3.68 |
| low effort | 307 / 310 | 12 / 14 | 2570 s (-18 %) | 2272 s (-21 %) | 185 | $3.10 (-16 %) |

The only difference in quality: t01 (slugify) lost two hidden tests, `max_length` cutting at word boundaries (`one two three four` at 7 and 13 characters): an edge case the control got right. Per task the times are noisy in both directions (t10 took 28 calls instead of 4 with low effort, t11 9 instead of 19), so the speed gain is real on the sum but one run is not proof.
Verdict under D-161 (a speed change that lowers the quality score is rejected): **not adopted as the default**; the switch stays an environment experiment. Next step would be three runs per arm on the tasks where an edge case matters before reconsidering; S7 (a smaller model for read-only subagents) is still waiting for a deployment name.

### speed-4 (2026-10-14, after the DESIGN.md gate and the visual-diff merge; s03 only)
| Task | speed-1 | speed-3 | speed-4 |
|---|---|---|---|
| s03 page redesign | 1487 s, $1.51, 6/7 | 865 s, $1.06, 6/7 | 509 s, $0.62, 6/7 |

Wall time fell 41 % from speed-3 at the same quality score (6/7). Tool time 288 s, of which three design-critic subagent reviews took 253 s (100 + 80 + 73); `start_background` 6 s, `view_image` 15 s. One run only: noise is large. The remaining cost is the critic rounds, which are the quality mechanism (D-161: not trimmed).

### speed-5: the Claude Code style changes (D-360), dashboard brief, run side by side on the same machine (2026-10-15)
Two worktrees started at the same minute, same brief (`d03_ops_dashboard`, the design benchmark), same model (gpt-5.1): the code before the changes (`7334a7a`) and after (`7da5a95`).

| | before | after | change |
|---|---|---|---|
| wall time | 1228 s | 1188 s | -3 % |
| model calls | 37 | 29 | -22 % |
| tool calls | 55 | 58 | +5 % (more calls per step) |
| model time | 987 s | 894 s | -9 % |
| input tokens | 3.10 M | 2.10 M | -32 % |
| cost | $2.01 | $1.88 | -7 % |
| reviews | critic twice, 158 s, no verifier | verifier and critic together, 216 s | one extra check, in parallel |
| judge (type/dist/hier/harm/fit/polish) | 4/3/4/4/4/4 | 4/4/4/5/5/4 | higher |
| audit findings left | 0 | 5 | worse (contrast, imagery, small text left unfixed) |

What it shows, honestly:
- **The earlier 45 minutes (2728 s) was mostly contention**: the same brief alone ran in 20 minutes. Another benchmark and a document run were using the same machine and the same Azure quota at the time. Never read timings from overlapping runs.
- **Batching works** (22 % fewer model calls, 32 % fewer input tokens, 7 % cheaper) but the wall time barely moved: each call now does more, so the model time fell only 9 %.
- **Reviews are not faster in parallel**: the verifier (not used before, now asked for together with the critic) took as long as the critic; both ran in parallel and finished together at about 215 s. The run is more thoroughly checked, not faster.
- **The time is spent writing**: calls over 45 s are the ones that write 7,000 to 9,000 output tokens (a whole CSS and HTML file). More speed needs less to write: start from a composition recipe and a tokenised DESIGN.md (copy, then edit) instead of writing 500 lines of CSS from nothing, and smaller first drafts.
- **One run each**: differences of a few percent are noise.


### speed-6: where the output tokens went, and two fixes (D-365, 2026-10-14)
Reading the event log of the speed-5 "after" run (`llm_call` events: output tokens and latency per call): 29 calls, 894 s of model time, 61,800 output tokens (19,500 of them reasoning); the ten calls over 30 s hold 44,900 tokens and 550 s. Most of that is whole files written.

**Finding 1, pages written for nothing.** `index.html` (274 lines) and `style.css` (497 lines) were written twice and refused twice by the DESIGN.md and candidates gates before a third write was accepted: about 16,700 output tokens and two minutes, a third of the run's output. The model produced the whole page before the refusal could be known. Fix: the order (DESIGN.md, three candidates and `design_candidates`, then the page) is now stated in both system prompts and at the top of the ui-design-quality skill, with the cost of ignoring it.
**Finding 2, one gate at a time.** A `task_update` was refused for tests, then for the browser, then for the critic: one model call per refusal (five refusals in the speed-6 run, about 15 s each). Fix: each refusal now also lists every other check still missing.

Run `speed-6` (dashboard brief, machine otherwise idle, after fix 1 only): 2658 s wall, 77 model calls, 95,000 output tokens, $3.24; judge 4/3/4/4/4/4; 1 audit finding (no imagery). **Worse than speed-5 and not comparable**: this run took the plan and task path (`propose_plan`, tasks with gates, a 515 s verifier, a failed image generation, a wrong dev-server port) that the speed-5 run did not. One run per arm cannot separate a change from the model choosing another route (1188 s against 2658 s on the same brief). What the log does show is that finding 1 did not happen: no page file was refused before DESIGN.md existed. Finding 2's fix came after this run and is untested live.
Not concluded: a wall-time gain. To measure it, three runs per arm (see TODO X8).

### Where the tool time goes (D-368, 2026-10-15)
From the event logs of the dashboard brief: tool time is almost all `spawn_subagent` (speed-6: 5 runs, 904 s of 2,658 s; speed-new: 2 runs, 426 s of 1,188 s). Everything else is small: `browser_screenshot` 2.2 s, `browser_open` 3.4 s, `run_command` 1.4 s, `start_background` 2.2 s, `view_image` 24 s (a vision call), `design_candidates` 22 s (a vision call). The 515 s verifier wrote a Playwright script twice and installed Playwright (99 s) for a static page; the verifier prompt now skips the script when there is no behaviour to exercise.

### X8: three throwaway designs, serial against parallel builders (D-380, 2026-10-15)
Brief: three designs of the home screen of a blood donation app (tests/benchmarks/parallel/three_designs.md). Arms: `limits.max_parallel_builders` 1 (builders one after another) against 3. Same code and prompts in both arms (commit `b030af7`: `build_variants` available), alternating runs, idle machine, runner `scripts/benchmark/run_parallel_designs.py`.

**First attempt (x8-1, stopped after one pair).** Serial 2,788 s with 100 main-agent model calls; "parallel" 1,441 s with 64: the model never spawned a builder in either arm (it loaded the parallel-builders skill, then reasoned "treat this as a single-agent job to minimise coordination errors"), so the 1.9x difference was route variance, not parallelism. That is why the route became a tool (D-380). Lesson: one run per arm, with the arms behaving alike, shows nothing.

**Second attempt (x8-2), interim after the first pair** (the main agent's model calls only; the builders' own calls are in their subagent logs):
| Arm | Wall | Main-agent calls | Input tokens | Cost | Agents (peak at once) | 429 notices | Designs | Audit findings left | Sideways scroll |
|---|---|---|---|---|---|---|---|---|---|
| serial 1 | 1,914 s | 40 | 2.68 M | $2.44 | 4 (1) | 0 | 3, all different | 4 | 0 |
| parallel 1 | 750 s | 17 | 0.74 M | $1.99 | 4 (3) | 0 | 3, all different | 0 | 0 |
The parallel arm was 2.6x faster and 18 % cheaper with no 429s from Azure at three builders at once. One pair is one pair: the table is completed with runs 2 and 3 of each arm.
