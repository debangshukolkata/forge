# Work order: pydantic settings in the settings report (DB3) and a second test bed (RS8)

Written 2026-11-13. Decided by the user 2026-11-13: both go to a builder (the split of CLAUDE.md memory:
the analysis model writes, a smaller model builds, the analysis model reviews as `DB3`/`RS8` closure).
Items: TODO.md `DB3` (section 0i) and `RS8` (section 0j). **Build DB3 first (small), then RS8.**
Rules for the builder: `docs/SPEC_HARNESS_WASTE.md` section 2 applies (read CLAUDE.md and the MODULE.md of
the module you change, no commit, no push, no prompt/skill/UI change, no new dependency unless a part below
names it, quick check while working, full non-browser run plus ruff, ruff format and mypy at the end, stop
and report instead of guessing). Append `## 4. Builder's report` to this file with `git status --short` from
before you start, per item what was built, the real test output, and every place you were unsure.

## 1. DB3: environment names from pydantic settings classes

**Why:** FastAPI services keep their settings in a `pydantic_settings.BaseSettings` class. The names it
reads (`env_prefix` plus the field name) never appear as `os.getenv(...)`, so `code_map` action `env` (the
settings report, D-567) misses them and DebCraft guesses.

**Files:** `src/forge/knowledge/python_file.py` (function `env_reads` and its caller that fills the file
record's `env`, `env_lines`, `env_required`), `src/forge/tools/code_map_tool.py` (`settings_report`; change
only if the new names need a different line), tests in the file that tests `env_reads` (search `tests/` for
`env_reads` or `env_required`).

**Build:** in `env_reads`, also find classes whose bases include `BaseSettings` (by the last dotted part of
the base, as `MODEL_BASES` in `knowledge/code_map.py` does) and for each annotated class-level field
(`name: type` or `name: type = default`):
1. The environment name is `PREFIX + field_name` upper-cased, where `PREFIX` is the `env_prefix` given in
   `model_config = SettingsConfigDict(env_prefix="X_")`, in `model_config = {"env_prefix": "X_"}`, or in an
   inner `class Config: env_prefix = "X_"`. No prefix: empty. Only a string literal counts; anything else
   means "no prefix known" and the field is recorded with its bare upper-cased name.
2. A field with `Field(alias="NAME")`, `Field(validation_alias="NAME")` or `Field(env="NAME")` (a string
   literal) uses that exact name instead (no prefix added).
3. **Required** (read without a default) when the field has no `= value` and no `Field(default=...)`,
   `Field(default_factory=...)` and its first positional argument of `Field(...)` is not given or is `...`.
   `Optional[...]`/`X | None` without a default is still required in pydantic v2: keep it required.
4. Skip: names starting with an underscore, `model_config`, and `ClassVar` annotations.
5. The recorded line is the field's line; merge with names read by `os.getenv` in the same file the way
   `note` does today (earliest line, required if either is).
6. Never record a value; names only.

**Tests (direct, parse a small source string):** a prefix via `SettingsConfigDict`; via a dict; via inner
`Config`; a field with an alias; `Field(default_factory=list)` is not required; `x: str` is required;
`x: str | None` is required; `ClassVar` and `_private` are skipped; a class that is not `BaseSettings` is
ignored; a file with both `os.getenv("A")` and a settings class gives both names. One test through
`code_map` action `env` on a tiny workspace: the settings-class name appears with its file and line and is
marked as required when no env file sets it.

**Done when:** tests pass; the TODO line `DB3` is `[~]`; add a short decision to `docs/DECISIONS.md` (next
free number). Update `src/forge/knowledge/MODULE.md` if it lists what is read.

## 2. RS8: a second test bed with a real model, tools in PostgreSQL, and a prompt-change case

**Why:** the first test bed (`tests/fixtures/agent_platform`, AgentHub, SQLite, a hand-written agent) proved
the running-system loop. The real target (WisdomNext) is a LangChain agent with a real model whose tools
live in PostgreSQL. The test bed must exercise `db_copy_table` and `use_scratch_database` inside a live run
and include a requirement whose right fix is a **prompt change**, not a tool change (so DebCraft is not
trained to always patch a tool).

**Files (all new):** `tests/fixtures/agent_platform_pg/` (the application), `tests/test_live_running_system_pg.py`
(live test), `tests/test_agent_platform_pg.py` (offline checks of the fixture itself). Reuse helpers from
`tests/test_http_request.py` (`copy_fixture`, `free_port`, `start_hub`) and the structure of
`tests/test_live_running_system.py`; do not edit those two files except to make a helper importable.

**The application (`agenthub_pg`):**
- Same surface as AgentHub: `GET /api/agents`, `POST /api/agents/<name>/run` with `{"question": ...}`,
  `Authorization: Bearer <token>` (SHA-256 check, token from the same `TOKEN` constant the first test bed
  uses), every run appended to `logs/runs.jsonl`, the answer `{"status": "ok"|"error", "answer": ...}`,
  reason of a failure only in the run log.
- Agents and tools are rows in PostgreSQL tables (`agents`, `tools`, `agent_tools`); database URL from
  `HUB_DATABASE_URL` in `.env`; schema from `HUB_SCHEMA` (default `public`). The schema file `seed.sql`
  creates and fills them. **Tests use the local Postgres** (`LOCAL_PG_URL` in `.env`, marker `pg`, skipped
  when unset), creating only `forge_*` schemas and dropping them afterwards (CLAUDE.md, testing rules).
- The agent is a LangChain tool-calling agent with a **real Azure OpenAI model** built from the same
  `AZURE_OPENAI_*` names DebCraft's `.env` uses (the app's own model; `request_app_keys` exists for this,
  D-466). LangChain is a dependency **of the fixture, not of DebCraft**: the fixture's own requirements
  file lists it and `scripts/dev/setup_fixture_venv.ps1` installs it; DebCraft's `pyproject.toml` does not
  change. If LangChain is not installed in the fixture venv the live test skips with that reason.
- Settings in a pydantic `BaseSettings` class (so DB3 is exercised too), with an `APP_` prefix.

**The two requirements (two live scenarios, both in the test file):**
1. `tool_fix`: "The ops agent should be able to list the names of the deployments." A tool returns a response
   larger than the agent's context (as in AgentHub). The right fix is in the tool or its API answer.
   DebCraft must copy the tool tables from the read-only database with `db_copy_table`, run the app with
   `use_scratch_database`, reproduce through the API, find the cause in the run log, fix, run again.
2. `prompt_fix`: "The support agent answers in English when the customer writes German. It must answer in
   the customer's language." The tool and API are fine; the cause is the agent's system prompt (a row in
   the `agents` table). The right fix is a changed prompt **in the copied data and in the seed that creates
   it**, nothing else. A run that edits a tool or the code instead fails the check "the prompt row changed
   and no tool file changed".

**Pass check (the test's own, after the run, on the changed copy, as in the first test):**
- scenario 1: the ops agent answers with the three deployment names, another agent still answers;
- scenario 2: the support agent answers a German question in German (check with a fixed list of German
  words in the answer and none of a fixed English list), another agent unchanged;
- both: the token is not in any event or the model's text, `db_copy_table` and `use_scratch_database` were
  called (`row["used_scratch_database"]`), the user's read-only database was never written to (compare row
  counts before and after).
- Each run writes one JSON line to the file named by `RUNNING_SYSTEM_LOG` (same keys as the first test plus
  `scenario`, `used_scratch_database`, `changed_files`, `prompt_row_changed`).

**Offline tests of the fixture (`tests/test_agent_platform_pg.py`, no model, run by default):** the schema
loads into a `forge_*` schema; the API refuses a missing token (401) and a wrong one; `GET /api/agents`
lists the agents; a run with a stub model object injected through a settings flag
`APP_FAKE_MODEL=1` (fixture-only, for these offline tests: it is not a fake of DebCraft's model, CLAUDE.md
"No FakeLLM" is about DebCraft) logs a run and returns the documented shape; the two seeded defects exist
(the tool really returns more than the context; the support prompt really says to answer in English).

**Do not run the live scenarios more than once each.** Report the two results exactly as printed; do not
tune the fixture, the skill or DebCraft to make them pass (the reviewer decides what the result means).

**Done when:** the offline tests pass, the live test file collects and skips cleanly without credentials, one
live run of each scenario is in the report (or the reason it could not run), the TODO line `RS8` is `[~]`,
`tests/fixtures/agent_platform_pg/README.md` explains the start and the two defects (without naming the
fixes), and a decision entry is in `docs/DECISIONS.md`.
