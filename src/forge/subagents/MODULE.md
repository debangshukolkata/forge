# subagents

Fresh-context helpers the main agent can delegate to: explore (read-only search), reviewer (second opinion on a
change), debugger (root cause of a failure), researcher (web research with sources, D-209), verifier (independent acceptance checks against the running app), design-critic (`critic.py`, D-249: an independent designer that looks at the running page at desktop and phone width, scores seven lines and ends with `VERDICT: SHIP|REVISE`; `task_update` for a UI task needs a SHIP after the last edit or three REVISE rounds), and custom agents from `<forge_home>/agents/`. Each runs its own
AgentLoop with a restricted toolset and returns one report. Also the `spawn_subagent` tool.

- **Depends on:** agent, config, context, errors, llm, parity, protocol, safety, toolkit, tools, workspace
- **Invariants:** A subagent never gets `spawn_subagent`, so subagents cannot nest. Subagents are read-only
  unless they are the debugger (which may run tests). Only the report returns to the main context.
- **Tests:** test_agent_loop.py, test_parity.py
- **Decisions:** docs/DECISIONS.md (subagents, reviewer); layering is enforced by tests/test_module_boundaries.py.

Keep this file in step with the code: the `Depends on` line is checked against the real imports.
- **Builders (X2, D-305):** `builder.py` (protocol: statuses, folders, ledger) and the `builder` agent type in `spawn_tool.py`: writes only below its folder (the write jail also covers move/delete), own shell session, own port, report saved to `.forge/builders/`; the agent loop runs builders with disjoint folders side by side (`limits.max_parallel_builders`, default 3). Tests: test_builders.py. Skill: `parallel-builders`.
- **Variants (D-380):** `variants_tool.py`: `build_variants(brief, variants)` starts one builder per variant at once (own folder, DESIGN.md and tokens, at most `limits.max_parallel_builders`), returns every report and marks the pages as unverified edits. Tests: test_build_variants.py.
