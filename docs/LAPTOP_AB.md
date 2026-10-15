# The Gemini A/B on the office laptop (D-418)

Why on the laptop: only it has the Google credentials. What it decides: whether Gemini 4 Argon as the critic, the judge and the reviewer makes the pages better than the Azure models doing the same jobs, and
whether Argon or Gemini 3.1 Pro as the planner helps. Build is the same in every condition (the Azure coder, gpt-5.1), so the only change is who checks the work.

Do this in a PowerShell window in your DebCraft folder (`C:\Work\LocalDevelopment\forge-main`), after `git pull` and a start of DebCraft (so that the packages are current). The runs open Edge windows
and use the model keys of your `.env`; do not use the laptop for anything heavy while they run, and keep it awake (the runner does that). Replace the path of `FORGE_ENV_FILE` if your file is elsewhere.

## 1. A quick look first (about 25 minutes, two small briefs)

```
$env_file = "C:\Users\211258\.forge\.env"
.\.venv\Scripts\python scripts\benchmark\run_design_benchmark.py ab-mini-azure --mini --scorer-model gemini4argon --env FORGE_ENV_FILE=$env_file
.\.venv\Scripts\python scripts\benchmark\run_design_benchmark.py ab-mini-argon --mini --critic-model gemini4argon --scorer-model gemini4argon --env FORGE_ENV_FILE=$env_file
```

- First command: the Azure models check the work. Second: Gemini 4 Argon is the critic, the judge and the reviewer.
- `--scorer-model gemini4argon` makes Argon the scoring judge of both runs, so the same neutral eye (it built nothing) scores both conditions.
- Results appear in `C:\Work\ForgeRuns\designbench\ab-mini-azure\results.md` and `...\ab-mini-argon\results.md`: the judge's scores per brief (type, distinctiveness, hierarchy, harmony, fit, polish), the audit findings that were left, time and cost.

## 2. The full comparison (about 1.5 hours each, four briefs)

```
$briefs = "d01_science_museum,d03_ops_dashboard,d04_member_table,d05_booking_wizard"
.\.venv\Scripts\python scripts\benchmark\run_design_benchmark.py ab-azure --tasks $briefs --scorer-model gemini4argon --env FORGE_ENV_FILE=$env_file
.\.venv\Scripts\python scripts\benchmark\run_design_benchmark.py ab-argon --tasks $briefs --critic-model gemini4argon --scorer-model gemini4argon --env FORGE_ENV_FILE=$env_file
```

Run them one after the other, never together. One run per brief is noisy: a difference of one point on one brief means little; the same direction on three or four briefs means something.

## 3. What to send back

The two `results.md` files (or a photo of each), and tell whether the pages with the Argon critic looked better to you. Your eye is the final judge, so open `C:\Work\ForgeRuns\designbench\ab-azure\d03_ops_dashboard\project\index.html`
and the same file under `ab-argon` side by side.

## 4. Planner (optional, later)

In DebCraft, open a project, switch to plan mode and give it a large task twice: once with the Planner row set to gpt-5.1 and once to gemini-4-argon (Environment panel, then Save models). Compare the plans it returns:
are the tasks in a sensible order, does each have a check, are the risks real?

## 5. What I do with the answer

- Argon clearly better as critic and judge: it stays the proposed default for those roles (it already is).
- No difference or worse: the proposal for the critic, judge and reviewer goes back to the Azure models (gpt-5.2 for all three), and Argon stays selectable.
- Cost and time per condition are in the results: Argon as critic adds model calls, so look at wall time too.
