# The design taste test: Gemini 4 Argon against gpt-5.1 (TODO DIE8)

Why it exists: Argon is planned only as critic, judge and planner. This test shows whether it should also **design**. Argon is not available on the build machine, so the Argon runs happen on the office laptop; everything
else is already in the repo. Models are not asked to score the pages (a model prefers its own family): you choose, blind.

## The three arms (same briefs, same recipes, skill and audit; only who designs and who builds changes)

| Arm | Designs (writes DESIGN.md) | Builds the page | Run name |
|---|---|---|---|
| A | gpt-5.1 | gpt-5.1 | `taste-a` |
| C | Argon | Argon | `taste-c` |
| B | Argon (the DESIGN.md of arm C) | gpt-5.1 | `taste-b` |

A against B: the same builder, so a difference is the design. B against C: the same design, so a difference is the building.

## Commands (PowerShell in the DebCraft folder on the office laptop, after `git pull`)

```
$env_file = "C:\Users\211258\.forge\.env"
$briefs = "d01_science_museum,d03_ops_dashboard,d04_member_table,d05_booking_wizard"
$critic = "gemini31pro"   # the same neutral critic and judge in every arm, so Argon never judges its own pages
.\.venv\Scripts\python scripts\benchmark\run_design_benchmark.py taste-a --tasks $briefs --critic-model $critic --scorer-model $critic --env FORGE_ENV_FILE=$env_file
.\.venv\Scripts\python scripts\benchmark\run_design_benchmark.py taste-c --tasks $briefs --coder-model gemini4argon --critic-model $critic --scorer-model $critic --env FORGE_ENV_FILE=$env_file
.\.venv\Scripts\python scripts\benchmark\run_design_benchmark.py taste-b --tasks $briefs --design-from taste-c --critic-model $critic --scorer-model $critic --env FORGE_ENV_FILE=$env_file
.\.venv\Scripts\python scripts\benchmark\blind_gallery.py first A=taste-a B=taste-b C=taste-c
```

Run them one after another, never together. About 1.5 hours each. `taste-b` needs `taste-c` finished first (it reads the DESIGN.md files `taste-c` wrote). If you prefer a quick look, add `--mini` and leave out `--tasks`.
An optional fourth arm, Gemini 3.1 Pro as designer (`--coder-model gemini31pro`, run name `taste-d`), tells whether a difference is Argon's or Gemini's in general.

## Judging

Open `C:\Work\ForgeRuns\designbench\gallery-first\gallery.html`. For each brief the pages are called Page 1, Page 2, Page 3 in a random order. Write down the page you like most for each brief, and the one you like least. Only then open
`key.md` in the same folder, which says which arm each page was. Send me the list and `key.md`; the audit counts are in each run's `results.md`.

## How to read it

- B beats A on most briefs: Argon's design decisions are better. Add a designer-model setting (Argon writes DESIGN.md, gpt-5.1 builds).
- C beats A but B does not: Argon builds better than it designs; consider Argon as coder for design work only.
- A wins or no pattern: Argon stays critic, judge and planner. Four briefs show a pattern, not a proof; a different result on one brief means little.
