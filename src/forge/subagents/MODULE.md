# subagents

Fresh-context helpers the main agent can delegate to: explore (read-only search), reviewer (second opinion on a
change), debugger (root cause of a failure), and custom agents from `<forge_home>/agents/`. Each runs its own
AgentLoop with a restricted toolset and returns one report. Also the `spawn_subagent` tool.

- **Depends on:** agent, config, context, errors, llm, parity, protocol, safety, toolkit, tools, workspace
- **Invariants:** A subagent never gets `spawn_subagent`, so subagents cannot nest. Subagents are read-only
  unless they are the debugger (which may run tests). Only the report returns to the main context.
- **Tests:** test_agent_loop.py, test_parity.py
- **Decisions:** docs/DECISIONS.md (subagents, reviewer); layering is enforced by tests/test_module_boundaries.py.

Keep this file in step with the code: the `Depends on` line is checked against the real imports.
