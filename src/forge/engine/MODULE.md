# engine

The session host: input queue, turn handling, slash commands, headless runs, run-log summary.

- **Depends on:** agent, config, context, db, diagnose, environment, errors, llm, memory, modeb, parity, protocol, safety, subagents, toolkit, tools, workflow, workspace
- **Invariants:** UI-agnostic; emits typed events only. The composition root: it wires agent, tools, protocol and learning together.
- **Tests:** test_agent_loop.py, test_db.py, test_live_agent.py, test_live_context.py, test_live_db.py (and others; see tests/)
- **Decisions:** docs/DECISIONS.md (search the module's feature names); layering is enforced by tests/test_module_boundaries.py.

Keep this file in step with the code: the `Depends on` line is checked against the real imports.
- **Conversations (D-582):** `history_store.py` (the model's history as `history.json`, redacted on write and on load, cut back to valid call/result pairs) and `session_conversations.py` (restore at open, save after every finished step, title from the first message, the pinned line about other conversations, the `history_not_restored` notice).
- **`forge laptop` (D-615):** `laptop.py` (plan, check, live, report), `laptop_pages.py` (pages of at most 30 lines x 100 characters, verdicts, `verdicts.json`, the summary page), `laptop_report.py` (the facts from the conversations, the run notes and the field log), `laptop_probe.py` (the program run with the application's own Python, once per database driver, against the relay). Files under `<DebCraft Home>/laptop_report/`. Tests: test_laptop.py.
