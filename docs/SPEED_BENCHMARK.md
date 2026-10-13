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
(none recorded yet: the first baseline is `speed-1`)
