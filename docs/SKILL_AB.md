# Skill A/B runs (C14, D-417)

### Skill `test-first`: with and without

| Condition | Tasks passed | Hidden tests | Model calls | Wall s | Cost |
|---|---|---|---|---|---|
| with the skill | 2/4 | 173/175 | 48 | 1140 | $1.57 |
| without the skill | 2/4 | 173/175 | 49 | 1305 | $1.83 |

| Task | with: tests / s / calls | without: tests / s / calls |
|---|---|---|
| t11_rate_limiter | 25/25 / 289 / 16 | 25/25 / 152 / 6 |
| t12_expr_calc | 68/69 / 241 / 6 | 68/69 / 292 / 14 |
| t13_todo_undo | 15/16 / 325 / 18 | 15/16 / 245 / 14 |
| t14_cron_next | 65/65 / 285 / 8 | 65/65 / 616 / 15 |

No difference in correctness. Calls -1, wall -165 s, cost -0.27 USD (with minus without).

## Arms experiment (C16)

Question: do the original Superpowers or mattpocock/skills sets beat DebCraft's own distilled skills, or no workflow skills at all, on the coding benchmark? `scripts/benchmark/run_skill_arms.py` runs `run_code_benchmark.py` once per arm on the same task list, one arm after the other.

| Arm | What the run sees |
|---|---|
| `baseline` | DebCraft with the workflow skills switched off (`FORGE_DISABLED_SKILLS`): test-first, debugging, verify-before-done, deep-modules, solution-thinking, parallel-builders, pytest-patterns, project-docs, eval-harness. The domain skills that carry assets (python-project, ui-design-quality, make-document and so on) stay available in every arm. |
| `distilled` | DebCraft as shipped (our own versions). |
| `superpowers` | The original obra/superpowers skills; DebCraft's workflow skills are off (except a name the external set also uses, which it replaces). |
| `mattpocock` | The mattpocock/skills set, likewise. |

External skills reach the isolated run through `FORGE_EXTRA_SKILLS_DIR` (read by `parity.skills.discover`; several folders are separated by `;` on Windows); the script sets it per arm. The script downloads nothing.

### Install the external skills (you do this)

DebCraft shows each skill's contents and asks before installing. Read them: they are instructions the model will follow.

```
.venv\Scripts\python -m forge.cli skill add https://github.com/obra/superpowers
.venv\Scripts\python -m forge.cli skill add https://github.com/mattpocock/skills
```

Both land in `<DebCraft home>\skills`, mixed with anything else installed there. For a clean arm, copy each set's skill folders into a folder of their own (for example `C:\Work\ForgeRuns\arms\superpowers` and `C:\Work\ForgeRuns\arms\mattpocock`, each holding `<skill>\SKILL.md`) and pass that folder.

### Commands

Check the arms first (no model call, no cost):

```
.venv\Scripts\python scripts\benchmark\run_skill_arms.py arms1 --preflight-only --superpowers-dir C:\Work\ForgeRuns\arms\superpowers --mattpocock-dir C:\Work\ForgeRuns\arms\mattpocock
```

The experiment (runs `arms1-baseline-1`, `arms1-distilled-1`, `arms1-superpowers-1`, `arms1-mattpocock-1`, and `-2` with `--repeat 2`):

```
.venv\Scripts\python scripts\benchmark\run_skill_arms.py arms1 --tasks t01_slugify,t02_durations,t04_paginate_bug,t11_rate_limiter,t12_expr_calc,t13_todo_undo,t14_cron_next --parallel 3 --repeat 2 --superpowers-dir C:\Work\ForgeRuns\arms\superpowers --mattpocock-dir C:\Work\ForgeRuns\arms\mattpocock --record
```

`--arms baseline,distilled` limits the arms; an external arm without its folder is skipped with the reason printed.

### What to read from the table

- Tasks passed and hidden tests per arm: the easy tasks are near the ceiling, so include harder ones (t11 onward) and read small differences as noise unless a repeat confirms them.
- Model calls, wall seconds and cost: what the process costs. A skill set that passes the same tests with twice the calls is worse for us (D-161: accuracy first, then speed).
- The slow-down note: wall time of t01, t02 and t04 against baseline. Heavy process on one-function jobs shows up here.
- Per-task rows: where an arm lost or won; open the delivered code of that task before drawing a conclusion.

### Caveats

- Style: the original Superpowers skills use capitalised commands ("YOU MUST", "NEVER") that were tuned for Claude. Our model may over-obey or ignore that style, so a poor Superpowers result says as much about the wording as about the method. That is also why `distilled` rewrites them.
- mattpocock/skills has a setup skill that asks to run a one-time setup per repository. A benchmark run cannot answer it: leave that skill out of the arm's folder (the pre-flight prints a warning for any skill with "setup" in its name).
- External skills whose names clash with a DebCraft skill replace it in that arm; the pre-flight lists such clashes.

### Cost estimate

cost = arms x tasks x repeats x per-task cost. docs/CODE_BENCHMARK.md gives about $0.16 per task on the easy ten and about $0.27 on the fourteen of `night-1` ($3.74); use about $0.30. Example: 4 arms x 7 tasks x 2 repeats x $0.30 = about $17, and roughly 4 x 7 x 2 x 5 minutes = 4.7 hours at `--parallel 1` (less in parallel). External skills usually raise the call count, so expect their arms above this.
