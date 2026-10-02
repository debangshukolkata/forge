# agent

The main agent core: the loop (model call -> tool calls -> results -> repeat), no scripted failure handling (D-155). Knows nothing about requirements, reports or subagents.

- **Depends on:** config, context, errors, learning, llm, protocol, safety, toolkit, tools, verify, workspace
- **Invariants:** Every tool call gets a result, in order, even on interrupt. The loop owns every tool call
  (providers never execute tools). No phase machine (D-128..132). Tool results are capped and redacted here.
- **Tests:** test_agent_loop.py, test_events.py
- **Decisions:** docs/DECISIONS.md (D-128..D-132 loop and cadence); layering is enforced by tests/test_module_boundaries.py.

Keep this file in step with the code: the `Depends on` line is checked against the real imports.
