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
