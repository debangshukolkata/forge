# engine

The session host: input queue, turn handling, slash commands, headless runs, run-log summary.

- **Depends on:** agent, config, context, db, diagnose, errors, kb, llm, memory, modeb, parity, protocol, safety, subagents, toolkit, tools, workflow, workspace
- **Invariants:** UI-agnostic; emits typed events only. The composition root: it wires agent, tools, protocol and learning together.
- **Tests:** test_agent_loop.py, test_db.py, test_frontend_smoke.py, test_kb.py, test_learning.py, test_live_agent.py, test_live_context.py, test_live_db.py (+16 more)
- **Decisions:** docs/DECISIONS.md (search the module's feature names); layering is enforced by tests/test_module_boundaries.py.

Keep this file in step with the code: the `Depends on` line is checked against the real imports.
